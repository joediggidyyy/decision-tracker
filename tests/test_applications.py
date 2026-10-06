"""Application lifecycle, confinement and recovery using disposable ledgers."""
import json
import sqlite3
from dataclasses import replace
from pathlib import Path
from uuid import uuid4
from concurrent.futures import ThreadPoolExecutor
import pytest
from conftest import change
from decision_tracker import store,cli,applications
from decision_tracker.models import Change,ProjectChange
from decision_tracker.service import Service
from decision_tracker.artifacts import Artifacts,bundle
from decision_tracker.approval_api import upgrade,Upgrade
from decision_tracker.errors import Fault

def document(path):
    value={'schema_version':'codesentinel.canonical-document/v1','document_id':'execution-plan','metadata':[{'label':'Version','value':'1.0'}],
           'sections':[{'id':'execution','heading':'Execution','blocks':[{'id':'execution-p0','type':'paragraph','text':'Use the approved approach.'}]}]}
    path.write_text(json.dumps(value),encoding='utf-8');return path

def policy(s,p,u,roots=None,required=None,revision=0,request_id=None):
    req=applications.PolicyChange(expected_policy_revision=revision,request_id=request_id or uuid4(),reason='Owner registers planning custody',planning_roots=roots,anchor_required=required)
    return applications.set_policy(s,'alpha',u,replace(p,id='local-owner',auth_method='os_owner'),req)

@pytest.fixture
def ready(ledger,tmp_path):
    s,p,u=ledger
    change(s,p,u,[{'op':'decision.create','data':{'title':'Approach','question':'Which approach?'}}])
    change(s,p,u,[{'op':'decision.close','key':'D000001','data':{'answer':'Use the approved approach','rationale':'It meets requirements'}}],1,{'D000001':1},authority_refs=['Owner approval'])
    upgrade(Artifacts(s),'alpha',u,p,Upgrade(expected_revision=2,request_id=uuid4()))
    root=tmp_path/'planning';root.mkdir();path=document(root/'plan.json')
    policy(s,p,u,[str(root)])
    return s,p,u,path

def request(s,p,u,path=None,section='execution',**data):
    detail=s.detail('alpha',u,p,'D000001');d=detail['data']
    fields={'expected_policy_revision':d['application_policy_revision'],'expected_resolution_id':d['planning_application']['resolution_id'],**data}
    if path:fields.update(planning_document=str(path),planning_section=section)
    return Change(expected_ledger_uuid=u,expected_revision=detail['revision'],expected_decision_revisions={'D000001':d['revision']},request_id=uuid4(),reason='Applied approved resolution to execution plan',operations=[{'op':'decision.apply','key':'D000001','data':fields}])

def test_apply_replay_reopen_reclose_history_and_recovery(ready):
    s,p,u,path=ready;req=request(s,p,u,path);before=s.detail('alpha',u,p,'D000001')['data']
    result=s.change('alpha',p,req);receipt=result['application_receipts'][0]
    assert result['revision']==3 and receipt['anchor']['document_id']=='execution-plan' and receipt['anchor']['version']=='1.0'
    assert receipt['anchor_status']=='found' and receipt['anchor']['generator_verification']=='not_checked'
    assert s.change('alpha',p,req)['replayed']
    applied=s.detail('alpha',u,p,'D000001')['data'];assert applied['planning_application']['applied']
    for k in ('answer','rationale','authority_refs','latest_resolution_approval','status','locked'):assert applied[k]==before[k]
    assert s.list_decisions('alpha',u,p)['data'][0]['applied']
    with pytest.raises(Fault,match='already applied'):s.change('alpha',p,request(s,p,u,path))
    change(s,p,u,[{'op':'decision.reopen','key':'D000001','data':{'impact':'Reconsider'}}],3,{'D000001':3},authority_refs=['Owner authorization'])
    assert s.detail('alpha',u,p,'D000001')['data']['planning_application'] is None
    change(s,p,u,[{'op':'decision.close','key':'D000001','data':{}}],4,{'D000001':4},authority_refs=['Owner reapproves'])
    fresh=s.detail('alpha',u,p,'D000001')['data']['planning_application'];assert not fresh['applied'] and fresh['resolution_id']!=receipt['resolution_id']
    s.change('alpha',p,request(s,p,u,path,'execution-p0'))
    assert s.detail('alpha',u,p,'D000001',3)['data']['planning_application']['receipt']==receipt
    assert s.detail('alpha',u,p,'D000001',4)['data']['planning_application'] is None
    objects=Artifacts(s);assert objects.verify('alpha',u,p)['ok']
    backup=objects.create('alpha',u,p,'backup')['data'];assert not objects.restore_check('alpha',u,p,backup['artifact_id'])['data']['activated']
    with s.catalog.project('alpha',u,p) as (db,_):native=bundle(db)
    assert native['schema_version']==3 and len(native['application_receipts'])==2
    other=Service(s.root.parent/'restored');objects=Artifacts(other);candidate=objects.import_native(p,native,True)['data']
    other.catalog.mutate(p,ProjectChange(kind='register',project_id='alpha',name='Restored',relative_path=candidate['relative_path'],expected_catalog_revision=0,request_id=uuid4()))
    assert objects.verify('alpha',u,p)['ok']
    assert other.detail('alpha',u,p,'D000001')['data']['planning_application']['applied']
    with other.catalog.project('alpha',u,p) as (db,_):
        with pytest.raises(Fault,match='CLI administration'):applications.read_document(other,db,str(path))
    path.unlink();assert objects.verify('alpha',u,p)['ok']  # Historical receipt does not depend on live files.

@pytest.mark.parametrize('failure',['missing','unavailable','outside','unsupported','changed','resolution','policy'])
def test_failed_application_never_advances_revision(ready,tmp_path,failure):
    s,p,u,path=ready;req=request(s,p,u,path);data=req.operations[0].data
    if failure=='missing':data['planning_section']='absent';code='ANCHOR_NOT_FOUND'
    elif failure=='unavailable':data['planning_document']=str(path.parent/'absent.json');code='DOCUMENT_UNAVAILABLE'
    elif failure=='outside':data['planning_document']=str(document(tmp_path/'other.json'));code='FORBIDDEN'
    elif failure=='unsupported':data['planning_document']='https://example.com/plan';code='UNSUPPORTED_ANCHOR'
    elif failure=='changed':data['expected_document_sha256']='0'*64;code='DOCUMENT_CHANGED'
    elif failure=='resolution':data['expected_resolution_id']='approval:other';code='RESOLUTION_CHANGED'
    else:policy(s,p,u,required=False,revision=1);code='POLICY_CHANGED'
    with pytest.raises(Fault) as error:s.change('alpha',p,req)
    assert error.value.code==code
    detail=s.detail('alpha',u,p,'D000001');assert detail['revision']==2 and detail['data']['revision']==2 and not detail['data']['planning_application']['applied']
    with s.catalog.project('alpha',u,p) as (db,_):assert db.execute('SELECT count(*) FROM application_receipts').fetchone()[0]==0
    change(s,p,u,[{'op':'decision.create','data':{'title':'Independent progress','question':'Next?'}}],2)
    assert Artifacts(s).verify('alpha',u,p)['ok']

def test_required_optional_and_policy_replay(ready):
    s,p,u,path=ready
    with pytest.raises(Fault,match='Select a planning'):s.change('alpha',p,request(s,p,u))
    id=uuid4();first=policy(s,p,u,required=False,revision=1,request_id=id)
    assert policy(s,p,u,required=False,revision=1,request_id=id)['data']['replayed']
    with pytest.raises(Fault,match='different content'):policy(s,p,u,required=True,revision=1,request_id=id)
    assert first['data']['recorded_by']=='local-owner'
    with pytest.raises(Fault,match='not found'):s.change('alpha',p,request(s,p,u,path,'missing'))
    receipt=s.change('alpha',p,request(s,p,u))['application_receipts'][0]
    assert receipt['anchor_status']=='omitted' and receipt['anchor'] is None and receipt['policy_revision']==2
    assert Artifacts(s).verify('alpha',u,p)['ok']

def test_protected_apply_dry_run_permissions_and_concurrency(ready):
    s,p,u,path=ready
    change(s,p,u,[{'op':'decision.lock','key':'D000001','data':{'baseline':'v1'}}],2,{'D000001':2},authority_refs=['Protect approved baseline'])
    req=request(s,p,u,path);req.validate_only=True
    assert s.change('alpha',p,req)['validated'];assert not s.detail('alpha',u,p,'D000001')['data']['planning_application']['applied']
    req.validate_only=False
    with pytest.raises(Fault,match='capability'):s.change('alpha',replace(p,capabilities=frozenset({'read'})),req)
    with ThreadPoolExecutor(2) as pool:results=list(pool.map(lambda _:s.change('alpha',p,req),range(2)))
    assert sorted(r['replayed'] for r in results)==[False,True]
    assert s.detail('alpha',u,p,'D000001')['data']['locked']
    assert Artifacts(s).verify('alpha',u,p)['ok']

def test_immutable_receipt_and_corruption_detection(ready):
    s,p,u,path=ready;s.change('alpha',p,request(s,p,u,path))
    with s.catalog.project('alpha',u,p,True) as (db,_):
        with pytest.raises(sqlite3.IntegrityError):db.execute('DELETE FROM application_receipts')
        with pytest.raises(sqlite3.IntegrityError):db.execute('UPDATE application_policy_events SET policy_revision=99')
        db.execute('DROP TRIGGER immutable_application_update');r=json.loads(db.execute('SELECT receipt_json FROM application_receipts').fetchone()[0]);r['recorded_by']='Forged'
        db.execute('UPDATE application_receipts SET receipt_json=?,receipt_sha256=?',(store.encode(r),store.digest(r)))
    with pytest.raises(Fault,match='inconsistent'):Artifacts(s).verify('alpha',u,p)

@pytest.mark.parametrize('stage',['backup','restore','ddl','validation'])
def test_schema3_upgrade_atomic_failures(ledger,monkeypatch,stage):
    s,p,u=ledger;objects=Artifacts(s)
    with s.catalog.project('alpha',u,p) as (db,_):before=bundle(db)
    def fail(*a,**k):raise RuntimeError('injected application upgrade failure')
    if stage=='backup':monkeypatch.setattr(objects,'create',fail)
    elif stage=='restore':monkeypatch.setattr(objects,'restore_check',fail)
    elif stage=='ddl':monkeypatch.setattr(store,'APPLICATION_SQL',store.APPLICATION_SQL+'\nINVALID DDL;\n')
    else:
        from decision_tracker import approval_api
        real=approval_api.validate_history
        def validate(db):
            if store.metadata(db)['schema_version']==3:fail()
            return real(db)
        monkeypatch.setattr(approval_api,'validate_history',validate)
    with pytest.raises(Fault if stage=='ddl' else RuntimeError):upgrade(objects,'alpha',u,p,Upgrade(expected_revision=0,request_id=uuid4()))
    with s.catalog.project('alpha',u,p) as (db,_):assert bundle(db)==before

def test_schema3_upgrade_replay_and_initialization(ledger,tmp_path):
    s,p,u=ledger;objects=Artifacts(s);req=Upgrade(expected_revision=0,request_id=uuid4())
    assert upgrade(objects,'alpha',u,p)['data']['to_version']==3
    result=upgrade(objects,'alpha',u,p,req);assert result['schema_version']==3 and result['revision']==0
    assert upgrade(objects,'alpha',u,p,req)['data']['replayed']
    assert not upgrade(objects,'alpha',u,p)['data']['upgrade_required']
    fresh=tmp_path/'fresh.sqlite';store.initialize(fresh,str(uuid4()),schema_version=3)
    with store.connect(fresh) as db:assert __import__('decision_tracker.artifacts',fromlist=['validate_history']).validate_history(db)['integrity']=='ok'

def test_open_replacement_supersedes_question_without_resolution(ledger):
    s,p,u=ledger
    change(s,p,u,[{'op':'decision.create','data':{'title':'Old question','question':'Old?'}},{'op':'decision.create','data':{'title':'Replacement question','question':'New?'}}])
    change(s,p,u,[{'op':'decision.deprecate','key':'D000001','data':{'kind':'superseded','replacement_key':'D000002'}}],1,{'D000001':1,'D000002':1},authority_refs=['Owner supersedes question'])
    assert s.detail('alpha',u,p,'D000001')['data']['status']=='deprecated'
    assert s.detail('alpha',u,p,'D000002')['data']['status']=='open'
    assert Artifacts(s).verify('alpha',u,p)['ok']

def test_cli_stays_compact_and_apply_builds_form_fields(monkeypatch,capsys):
    root=cli.parser();groups=next(a for a in root._actions if isinstance(a,__import__('argparse')._SubParsersAction))
    assert set(groups.choices)=={'service','auth','project','decision','option','reference','link','query','change','data'}
    monkeypatch.setenv('DT_OPERATOR_TOKEN','synthetic-application-cli-credential-12345');seen=[]
    def send(self,method,path,data=None,uuid=None,download=None):seen.append((method,path,data));return {'ok':True,'data':[]}
    monkeypatch.setattr(cli.Client,'request',send)
    assert cli.main(['decision','apply','--project','alpha','--ledger-uuid',str(uuid4()),'--key','D000001','--record-revision','2','--expected-revision','2','--expected-policy-revision','1','--request-id',str(uuid4()),'--reason','Apply approved resolution','--planning-document','C:/planning/plan.json','--planning-section','execution','--json'])==0
    capsys.readouterr();assert seen[0][2]['operations'][0]['data']=={'expected_policy_revision':1,'planning_document':'C:/planning/plan.json','planning_section':'execution'}
    assert cli.main(['decision','applications','--project','alpha','--ledger-uuid',str(uuid4()),'--key','D000001','--json'])==0
    assert seen[-1][0]=='GET' and '/applications?' in seen[-1][1]

def test_policy_set_routes_only_to_owner_administration(monkeypatch,tmp_path,capsys):
    from decision_tracker import local_cli
    seen=[]
    def admin(path,operation,**args):seen.append((operation,args));return {'ok':True,'data':{}}
    monkeypatch.setattr(local_cli,'local_admin',admin)
    def denied(*a,**k):pytest.fail('Policy set must not use bearer HTTP')
    monkeypatch.setattr(cli.Client,'request',denied)
    assert cli.main(['project','policy','set','--project','alpha','--ledger-uuid',str(uuid4()),'--expected-policy-revision','0','--request-id',str(uuid4()),'--reason','Owner configures anchor policy','--anchor-required','false','--planning-root',str(tmp_path),'--json'])==0
    capsys.readouterr();assert seen[0][0]=='project-policy-set' and seen[0][1]['request']['anchor_required'] is False

def test_http_policy_is_read_only_and_anchor_discovery_is_bound(client,tmp_path):
    c=client;project=c.post('/api/v1/projects',json={'project_id':'alpha','name':'Alpha','request_id':str(uuid4()),'expected_catalog_revision':0}).json()['data'];u=project['ledger_uuid'];headers={'X-Ledger-UUID':u}
    upgrade(c.app.state.artifacts,'alpha',u,c.app.state.auth.bearer(c.token),Upgrade(expected_revision=0,request_id=uuid4()))
    root=tmp_path/'plans';root.mkdir();path=document(root/'plan.json');p=c.app.state.auth.bearer(c.token)
    policy(c.app.state.service,p,u,[str(root)])
    assert c.get('/api/v1/projects/alpha/policy',headers=headers).json()['data']['anchor_required']
    assert c.post('/api/v1/projects/alpha/policy',headers=headers,json={'anchor_required':False}).status_code==405
    preview=c.get('/api/v1/projects/alpha/planning-document',headers=headers,params={'locator':str(path)}).json()['data'];assert preview['anchors'][0]['id']=='execution'
    assert c.get('/api/v1/projects/alpha/planning-document',headers={'X-Ledger-UUID':str(uuid4())},params={'locator':str(path)}).status_code==409

def test_commit_rechecks_document_and_protect_preserves_application(ready,monkeypatch):
    s,p,u,path=ready;req=request(s,p,u,path)
    real=applications.prepare
    def raced(*args):
        receipts=real(*args);path.write_text(path.read_text()+'\n',encoding='utf-8');return receipts
    monkeypatch.setattr(applications,'prepare',raced)
    with pytest.raises(Fault,match='Document changed'):s.change('alpha',p,req)
    assert s.detail('alpha',u,p,'D000001')['revision']==2
    monkeypatch.setattr(applications,'prepare',real);s.change('alpha',p,request(s,p,u,path))
    receipt=s.detail('alpha',u,p,'D000001')['data']['planning_application']['receipt']
    change(s,p,u,[{'op':'decision.lock','key':'D000001','data':{'baseline':'v1'}}],3,{'D000001':3},authority_refs=['Protect baseline'])
    assert s.detail('alpha',u,p,'D000001')['data']['planning_application']['receipt']==receipt
    assert Artifacts(s).verify('alpha',u,p)['ok']

def test_generated_markdown_companion_and_stale_projection(ready):
    import hashlib
    s,p,u,path=ready;md=path.with_suffix('.md')
    sha=hashlib.sha256(json.dumps(json.loads(path.read_text()),ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
    md.write_text('<!-- CODESENTINEL-GENERATED: canonical-markdown/v1\nsource-sha256: '+sha+'\nschema: codesentinel.canonical-document/v1\n-->\n## Execution\nApproved approach\n',encoding='utf-8')
    with s.catalog.project('alpha',u,p) as (db,_):preview=applications.read_document(s,db,str(md))
    req=request(s,p,u,md,expected_document_sha256=preview['sha256'],expected_projection_sha256=preview['projection']['sha256'])
    receipt=s.change('alpha',p,req)['application_receipts'][0];assert receipt['anchor']['projection']['source_marker_sha256']==sha
    assert receipt['anchor']['generator_verification']=='not_checked' and Artifacts(s).verify('alpha',u,p)['ok']
    path.write_text(path.read_text().replace('1.0','2.0'),encoding='utf-8')
    with s.catalog.project('alpha',u,p) as (db,_):
        with pytest.raises(Fault,match='Regenerate'):applications.read_document(s,db,str(md))

def test_junction_escape_and_oversized_document(ready,tmp_path):
    import subprocess
    s,p,u,path=ready;outside=tmp_path/'outside';outside.mkdir();document(outside/'secret.json')
    junction=path.parent/'linked'
    result=subprocess.run(['cmd','/c','mklink','/J',str(junction),str(outside)],capture_output=True,text=True,timeout=10)
    assert result.returncode==0,result.stderr
    with s.catalog.project('alpha',u,p) as (db,_):
        with pytest.raises(Fault,match='symbolic links'):applications.read_document(s,db,str(junction/'secret.json'))
        oversized=path.parent/'large.json';oversized.write_bytes(b' '*(4*1024*1024+1))
        with pytest.raises(Fault,match='4 MiB'):applications.read_document(s,db,str(oversized))
    # Retain the contained junction as test evidence; no recursive deletion of it.

def test_schema2_reads_unapplied_and_apply_requires_upgrade(ledger):
    s,p,u=ledger;change(s,p,u,[{'op':'decision.create','data':{'title':'Closed legacy','question':'Which?'}}])
    change(s,p,u,[{'op':'decision.close','key':'D000001','data':{'answer':'A','rationale':'R'}}],1,{'D000001':1},authority_refs=['Owner'])
    assert not s.detail('alpha',u,p,'D000001')['data']['planning_application']['applied']
    with pytest.raises(Fault,match='Upgrade'):s.change('alpha',p,request(s,p,u))

def test_same_record_application_batch_rejects_atomically(ready):
    s,p,u,path=ready;req=request(s,p,u,path);req.operations.append(__import__('decision_tracker.models',fromlist=['Operation']).Operation(op='decision.reopen',key='D000001',data={'impact':'Review'}));req.authority_refs=['Owner']
    with pytest.raises(Fault,match='separately'):s.change('alpha',p,req)
    assert s.detail('alpha',u,p,'D000001')['revision']==2

def test_policy_frame_bound_rejects_before_commit(ready):
    s,p,u,path=ready;req=applications.PolicyChange(expected_policy_revision=1,request_id=uuid4(),reason='x'*8192)
    with pytest.raises(Fault,match='administration capacity'):applications.set_policy(s,'alpha',u,p,req)
    with s.catalog.project('alpha',u,p) as (db,_):assert applications.policy(db)['policy_revision']==1

def test_policy_superseded_replay_cannot_activate_imported_access(ready):
    s,p,u,path=ready;id=uuid4();policy(s,p,u,required=False,revision=1,request_id=id);policy(s,p,u,required=True,revision=2)
    applications.binding_path(s,u).unlink()
    assert policy(s,p,u,required=False,revision=1,request_id=id)['data']['replayed']
    assert not applications.binding_path(s,u).exists()

@pytest.mark.parametrize('boundary',['before-commit','after-commit'])
def test_schema3_process_exit_and_upgrade_replay(ledger,boundary):
    import subprocess,sys
    s,p,u=ledger;id=str(uuid4())
    script="""
import os,sys
from decision_tracker.service import Service
from decision_tracker.artifacts import Artifacts
from decision_tracker.auth import Principal
from decision_tracker import approval_api,store
s=Service(sys.argv[1]);p=Principal('operator',frozenset({'*'}),frozenset({'read','maintain'}))
real=approval_api.validate_history
def validate(db):
    if store.metadata(db)['schema_version']==3:os._exit(71)
    return real(db)
if sys.argv[4]=='before-commit':approval_api.validate_history=validate
approval_api.upgrade(Artifacts(s),'alpha',sys.argv[2],p,approval_api.Upgrade(expected_revision=0,request_id=sys.argv[3]))
os._exit(72)
"""
    proc=subprocess.run([sys.executable,'-c',script,str(s.root),u,id,boundary],capture_output=True,timeout=20)
    assert proc.returncode==(71 if boundary=='before-commit' else 72),proc.stderr
    with s.catalog.project('alpha',u,p) as (db,_):assert store.metadata(db)['schema_version']==(2 if boundary=='before-commit' else 3)
    result=upgrade(Artifacts(s),'alpha',u,p,Upgrade(expected_revision=0,request_id=id))
    assert result['data']['replayed']==(boundary=='after-commit') and Artifacts(s).verify('alpha',u,p)['ok']
