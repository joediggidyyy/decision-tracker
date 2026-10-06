"""Planning-link lifecycle, confinement and recovery using disposable ledgers."""
import json,os,subprocess
import sqlite3
from dataclasses import replace
from pathlib import Path
from uuid import uuid4
from concurrent.futures import ThreadPoolExecutor
import pytest
from conftest import change
from decision_tracker import store,cli,planning_links
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
    req=planning_links.PolicyChange(expected_policy_revision=revision,request_id=request_id or uuid4(),reason='Owner registers planning custody',planning_roots=roots,anchor_required=required)
    return planning_links.set_policy(s,'alpha',u,replace(p,id='local-owner',auth_method='os_owner'),req)

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
    fields={'expected_policy_revision':d['planning_link_policy_revision'],'expected_resolution_id':d['planning_link']['resolution_id'],**data}
    if path:fields.update(planning_document=str(path),planning_section=section)
    return Change(expected_ledger_uuid=u,expected_revision=detail['revision'],expected_decision_revisions={'D000001':d['revision']},request_id=uuid4(),reason='Linked incorporated resolution to execution plan',operations=[{'op':'decision.link','key':'D000001','data':fields}])

def test_link_replay_reopen_reclose_history_and_recovery(ready):
    s,p,u,path=ready;req=request(s,p,u,path);before=s.detail('alpha',u,p,'D000001')['data']
    result=s.change('alpha',p,req);receipt=result['planning_link_receipts'][0]
    assert result['revision']==3 and receipt['anchor']['document_id']=='execution-plan' and receipt['anchor']['version']=='1.0'
    assert receipt['anchor_status']=='found' and receipt['anchor']['generator_verification']=='not_checked'
    assert s.change('alpha',p,req)['replayed']
    applied=s.detail('alpha',u,p,'D000001')['data'];assert applied['planning_link']['recorded']
    for k in ('answer','rationale','authority_refs','latest_resolution_approval','status','locked'):assert applied[k]==before[k]
    assert s.list_decisions('alpha',u,p)['data'][0]['linked']
    with pytest.raises(Fault,match='already has a planning-link record'):s.change('alpha',p,request(s,p,u,path))
    change(s,p,u,[{'op':'decision.reopen','key':'D000001','data':{'impact':'Reconsider'}}],3,{'D000001':3},authority_refs=['Owner authorization'])
    assert s.detail('alpha',u,p,'D000001')['data']['planning_link'] is None
    change(s,p,u,[{'op':'decision.close','key':'D000001','data':{}}],4,{'D000001':4},authority_refs=['Owner reapproves'])
    fresh=s.detail('alpha',u,p,'D000001')['data']['planning_link'];assert not fresh['recorded'] and fresh['resolution_id']!=receipt['resolution_id']
    s.change('alpha',p,request(s,p,u,path,'execution-p0'))
    assert s.detail('alpha',u,p,'D000001',3)['data']['planning_link']['receipt']==receipt
    assert s.detail('alpha',u,p,'D000001',4)['data']['planning_link'] is None
    objects=Artifacts(s);assert objects.verify('alpha',u,p)['ok']
    backup=objects.create('alpha',u,p,'backup')['data'];assert not objects.restore_check('alpha',u,p,backup['artifact_id'])['data']['activated']
    with s.catalog.project('alpha',u,p) as (db,_):native=bundle(db)
    assert native['schema_version']==3 and len(native['application_receipts'])==2
    other=Service(s.root.parent/'restored');objects=Artifacts(other);candidate=objects.import_native(p,native,True)['data']
    other.catalog.mutate(p,ProjectChange(kind='register',project_id='alpha',name='Restored',relative_path=candidate['relative_path'],expected_catalog_revision=0,request_id=uuid4()))
    assert objects.verify('alpha',u,p)['ok']
    assert other.detail('alpha',u,p,'D000001')['data']['planning_link']['recorded']
    with other.catalog.project('alpha',u,p) as (db,_):
        with pytest.raises(Fault,match='CLI administration'):planning_links.read_document(other,db,str(path))
    path.unlink();assert objects.verify('alpha',u,p)['ok']  # Historical receipt does not depend on live files.

@pytest.mark.parametrize('failure',['missing','unavailable','outside','unsupported','changed','resolution','policy'])
def test_failed_planning_link_never_advances_revision(ready,tmp_path,failure):
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
    detail=s.detail('alpha',u,p,'D000001');assert detail['revision']==2 and detail['data']['revision']==2 and not detail['data']['planning_link']['recorded']
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
    receipt=s.change('alpha',p,request(s,p,u))['planning_link_receipts'][0]
    assert receipt['anchor_status']=='omitted' and receipt['anchor'] is None and receipt['policy_revision']==2
    detail=s.detail('alpha',u,p,'D000001')['data']
    assert detail['planning_link']['recorded'] and not detail['planning_link']['linked']
    row=s.list_decisions('alpha',u,p)['data'][0]
    assert row['planning_link_recorded'] and not row['linked'] and row['applied']
    with pytest.raises(Fault) as error:s.change('alpha',p,request(s,p,u,path))
    assert error.value.code=='ALREADY_RECORDED'
    assert Artifacts(s).verify('alpha',u,p)['ok']

def test_protected_link_dry_run_permissions_and_concurrency(ready):
    s,p,u,path=ready
    change(s,p,u,[{'op':'decision.lock','key':'D000001','data':{'baseline':'v1'}}],2,{'D000001':2},authority_refs=['Protect approved baseline'])
    req=request(s,p,u,path);req.validate_only=True
    assert s.change('alpha',p,req)['validated'];assert not s.detail('alpha',u,p,'D000001')['data']['planning_link']['recorded']
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

def test_cli_stays_compact_and_link_builds_form_fields(monkeypatch,capsys):
    root=cli.parser();groups=next(a for a in root._actions if isinstance(a,__import__('argparse')._SubParsersAction))
    assert set(groups.choices)=={'service','auth','project','decision','option','reference','link','query','change','data'}
    monkeypatch.setenv('DT_OPERATOR_TOKEN','synthetic-application-cli-credential-12345');seen=[]
    def send(self,method,path,data=None,uuid=None,download=None):seen.append((method,path,data));return {'ok':True,'data':[]}
    monkeypatch.setattr(cli.Client,'request',send)
    assert cli.main(['decision','link','--project','alpha','--ledger-uuid',str(uuid4()),'--key','D000001','--record-revision','2','--expected-revision','2','--expected-policy-revision','1','--request-id',str(uuid4()),'--reason','Link incorporated resolution','--planning-document','C:/planning/plan.json','--planning-section','execution','--json'])==0
    capsys.readouterr();assert seen[0][2]['operations'][0]['data']=={'expected_policy_revision':1,'planning_document':'C:/planning/plan.json','planning_section':'execution'}
    assert cli.main(['decision','planning-links','--project','alpha','--ledger-uuid',str(uuid4()),'--key','D000001','--json'])==0
    assert seen[-1][0]=='GET' and '/planning-links?' in seen[-1][1]

def test_legacy_apply_retry_receipts_and_mixed_history_remain_valid(ready):
    from decision_tracker import applications
    s,p,u,path=ready
    assert applications is planning_links
    req=request(s,p,u,path);req.operations[0].op='decision.apply'
    first=s.change('alpha',p,req);receipt=first['application_receipts'][0]
    assert first['planning_link_receipts']==first['application_receipts']
    old=s.detail('alpha',u,p,'D000001')['data']
    assert old['planning_application']['applied'] and old['planning_link']['linked']
    assert old['planning_application']['receipt']==old['planning_link']['receipt']==receipt
    change(s,p,u,[{'op':'decision.reopen','key':'D000001','data':{'impact':'Fresh cycle'}}],3,{'D000001':3},authority_refs=['Owner'])
    change(s,p,u,[{'op':'decision.close','key':'D000001','data':{}}],4,{'D000001':4},authority_refs=['Owner'])
    s.change('alpha',p,request(s,p,u,path))
    replay=s.change('alpha',p,req)
    assert replay==first|{'replayed':True}
    assert s.detail('alpha',u,p,'D000001',3)['data']['planning_link']['receipt']==receipt
    assert Artifacts(s).verify('alpha',u,p)['ok']
    with s.catalog.project('alpha',u,p) as (db,_):native=bundle(db)
    assert native['application_receipts'][0]['receipt_json']==receipt
    assert [t['request_json']['operations'][0]['op'] for t in native['transactions'] if t['request_json']['operations'][0]['op'] in ('decision.link','decision.apply')]==['decision.apply','decision.link']
    other=Service(s.root.parent/'mixed-restored');objects=Artifacts(other)
    candidate=objects.import_native(p,native,True)['data']
    other.catalog.mutate(p,ProjectChange(kind='register',project_id='alpha',name='Mixed history',relative_path=candidate['relative_path'],expected_catalog_revision=0,request_id=uuid4()))
    assert objects.verify('alpha',u,p)['ok']
    assert other.change('alpha',p,req)==first|{'replayed':True}
    assert other.detail('alpha',u,p,'D000001',3)['data']['planning_link']['receipt']==receipt
    with other.catalog.project('alpha',u,p) as (db,_):assert bundle(db)==native

def test_api_discovery_and_cross_alias_history_cursor(client,tmp_path):
    c=client;s=c.app.state.service;p=c.app.state.auth.bearer(c.token)
    project=c.post('/api/v1/projects',json={'project_id':'alpha','name':'Alpha','request_id':str(uuid4()),'expected_catalog_revision':0}).json()['data']
    u=project['ledger_uuid'];headers={'X-Ledger-UUID':u}
    change(s,p,u,[{'op':'decision.create','data':{'title':'Approach','question':'Which?'}}])
    change(s,p,u,[{'op':'decision.close','key':'D000001','data':{'answer':'A','rationale':'R'}}],1,{'D000001':1},authority_refs=['Owner'])
    upgrade(c.app.state.artifacts,'alpha',u,p,Upgrade(expected_revision=2,request_id=uuid4()))
    root=tmp_path/'planning';root.mkdir();path=document(root/'plan.json');policy(s,p,u,[str(root)])
    old=request(s,p,u,path);old.operations[0].op='decision.apply'
    response=c.post('/api/v1/projects/alpha/changes',headers=headers,json=old.model_dump(mode='json'))
    assert response.status_code==200
    change(s,p,u,[{'op':'decision.reopen','key':'D000001','data':{'impact':'Review'}}],3,{'D000001':3},authority_refs=['Owner'])
    change(s,p,u,[{'op':'decision.close','key':'D000001','data':{}}],4,{'D000001':4},authority_refs=['Owner'])
    fresh=request(s,p,u,path)
    response=c.post('/api/v1/projects/alpha/changes',headers=headers,json=fresh.model_dump(mode='json'))
    assert response.status_code==200 and response.json()['planning_link_receipts']==response.json()['application_receipts']
    url='/api/v1/projects/alpha/decisions/D000001/'
    first=c.get(url+'applications',headers=headers,params={'limit':1}).json()
    assert not first['complete']
    second=c.get(url+'planning-links',headers=headers,params={'limit':1,'cursor':first['next_cursor']}).json()
    assert second['complete'] and first['data'][0]['receipt_id']!=second['data'][0]['receipt_id']
    canonical=c.get(url+'planning-links',headers=headers).json();legacy=c.get(url+'applications',headers=headers).json()
    assert {k:v for k,v in canonical.items() if k!='request_id'}=={k:v for k,v in legacy.items() if k!='request_id'}
    schema=c.get('/api/v1/schema').json();cap=schema['x-decision-tracker']
    assert 'planning_links_v1' in cap['capabilities'] and 'planning_applications_v1' in cap['capabilities']
    assert cap['planning_link_input']==cap['application_input']
    assert cap['planning_link_policy_write']=='os_owner_cli_only'
    assert schema['paths'][url.replace('alpha','{project_id}').replace('D000001','{key}')+'applications']['get']['deprecated']

def test_cli_old_names_remain_explicit_compatibility_calls(monkeypatch,capsys):
    monkeypatch.setenv('DT_OPERATOR_TOKEN','synthetic-link-compatibility-token');seen=[]
    def send(self,method,path,data=None,uuid=None,download=None):seen.append((method,path,data));return {'ok':True,'data':[]}
    monkeypatch.setattr(cli.Client,'request',send)
    u=str(uuid4());flags=['--project','alpha','--ledger-uuid',u,'--key','D000001','--json']
    assert cli.main(['decision','apply',*flags,'--record-revision','2','--expected-revision','2','--expected-policy-revision','1','--request-id',str(uuid4()),'--reason','Retry legacy planning receipt','--planning-document','C:/plan.json','--planning-section','execution'])==0
    assert seen[-1][2]['operations'][0]['op']=='decision.apply'
    assert cli.main(['decision','applications',*flags])==0
    assert '/applications?' in seen[-1][1]
    assert cli.exit_code({'ok':False,'error':{'code':'ALREADY_LINKED'}})==3
    assert cli.exit_code({'ok':False,'error':{'code':'ALREADY_RECORDED'}})==3
    capsys.readouterr()

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
    docs=c.get('/api/v1/projects/alpha/planning-documents',headers=headers).json()['data'];assert docs['entries'][0]['path']==str(path)
    assert c.get('/api/v1/projects/alpha/planning-documents',headers={'X-Ledger-UUID':str(uuid4())}).status_code==409

def test_document_pool_and_nested_browse_preserve_custody(ready,tmp_path):
    s,p,u,path=ready;nested=path.parent/'details';nested.mkdir();other=document(nested/'detail.json')
    (path.parent/'ordinary.json').write_text('{}');(path.parent/'private.txt').write_text('Synthetic unrelated text')
    with s.catalog.project('alpha',u,p) as (db,_):
        pool=planning_links.document_inventory(s,db);assert [d['path'] for d in pool['documents']]==[str(path)]
        listing=planning_links.document_inventory(s,db,str(path.parent));assert listing['folders']==[{'path':str(nested),'name':'details'}] and listing['parent'] is None
        listing=planning_links.document_inventory(s,db,str(nested));assert listing['parent']==str(path.parent) and listing['documents'][0]['path']==str(other)
        with pytest.raises(Fault,match='outside'):planning_links.document_inventory(s,db,str(tmp_path))
    s.change('alpha',p,request(s,p,u,other))
    with s.catalog.project('alpha',u,p) as (db,_):assert {d['path'] for d in planning_links.document_inventory(s,db)['documents']}=={str(path),str(other)}
    assert path.exists() and other.exists() and s.detail('alpha',u,p,'D000001')['revision']==3
    planning_links.binding_path(s,u).unlink()
    with s.catalog.project('alpha',u,p) as (db,_):
        with pytest.raises(Fault,match='CLI administration'):planning_links.document_inventory(s,db)

def test_document_browse_rejects_redirects_and_bounds_enumeration(ready,tmp_path):
    s,p,u,path=ready;root=path.parent
    for n in range(1001):(root/f'.entry-{n}').touch()
    with s.catalog.project('alpha',u,p) as (db,_):
        with pytest.raises(Fault,match='1000 entries'):planning_links.document_inventory(s,db)
    if os.name=='nt':
        link=root/'redirect';outside=tmp_path/'outside';outside.mkdir()
        subprocess.run(['cmd','/c','mklink','/J',str(link),str(outside)],capture_output=True,check=True)
        try:
            with s.catalog.project('alpha',u,p) as (db,_):
                with pytest.raises(Fault,match='junctions'):planning_links.document_inventory(s,db,str(link))
        finally:link.rmdir()

def test_document_inventory_cursor_rejects_file_changes(client,tmp_path):
    c=client;project=c.post('/api/v1/projects',json={'project_id':'alpha','name':'Alpha','request_id':str(uuid4()),'expected_catalog_revision':0}).json()['data'];u=project['ledger_uuid'];headers={'X-Ledger-UUID':u};p=c.app.state.auth.bearer(c.token)
    upgrade(c.app.state.artifacts,'alpha',u,p,Upgrade(expected_revision=0,request_id=uuid4()))
    root=tmp_path/'plans';root.mkdir();one=document(root/'one.json');document(root/'two.json');policy(c.app.state.service,p,u,[str(root)])
    first=c.get('/api/v1/projects/alpha/planning-documents',headers=headers,params={'limit':1}).json();assert not first['complete'] and first['next_cursor']
    v=json.loads(one.read_text());v['metadata'][0]['value']='2.0';one.write_text(json.dumps(v))
    response=c.get('/api/v1/projects/alpha/planning-documents',headers=headers,params={'limit':1,'cursor':first['next_cursor']});assert response.status_code==409

def test_document_pool_pages_fit_response_with_unicode_roots(client,tmp_path):
    c=client;project=c.post('/api/v1/projects',json={'project_id':'alpha','name':'Alpha','request_id':str(uuid4()),'expected_catalog_revision':0}).json()['data'];u=project['ledger_uuid'];headers={'X-Ledger-UUID':u};p=c.app.state.auth.bearer(c.token)
    upgrade(c.app.state.artifacts,'alpha',u,p,Upgrade(expected_revision=0,request_id=uuid4()))
    roots=[]
    for n in range(8):
        root=tmp_path/(str(n)+'计划'*25);root.mkdir();roots.append(str(root))
        for m in range(8):
            path=document(root/(str(m)+'.json'));v=json.loads(path.read_text());v['document_id']='计划'*80;v['metadata'][0]['value']='版本'*80;path.write_text(json.dumps(v),encoding='utf-8')
    policy(c.app.state.service,p,u,roots);cursor=None;seen=set();pages=0
    while True:
        response=c.get('/api/v1/projects/alpha/planning-documents',headers=headers,params={'limit':200,**({'cursor':cursor} if cursor else {})});assert response.status_code==200 and len(response.content)<=65536
        value=response.json();seen.update(x['path'] for x in value['data']['entries']);pages+=1;cursor=value['next_cursor']
        if value['complete']:break
        assert pages<10
    assert len(seen)==64 and pages>1

def test_inventory_counts_actual_bytes_when_stat_underreports(ready,monkeypatch):
    s,p,u,path=ready
    for n in range(6):
        large=document(path.parent/(str(n)+'.json'));value=json.loads(large.read_text());value['sections'][0]['blocks'][0]['text']='x'*(3*1024*1024);large.write_text(json.dumps(value),encoding='utf-8')
    real=Path.stat
    def small(self,*a,**kw):
        result=real(self,*a,**kw)
        if self.suffix=='.json' and self.parent==path.parent:
            values=list(result);values[6]=1;return os.stat_result(values)
        return result
    monkeypatch.setattr(Path,'stat',small)
    with s.catalog.project('alpha',u,p) as (db,_):
        with pytest.raises(Fault,match='inventory exceeds 16 MiB'):planning_links.document_inventory(s,db)

def test_commit_rechecks_document_and_protect_preserves_planning_link(ready,monkeypatch):
    s,p,u,path=ready;req=request(s,p,u,path)
    real=planning_links.prepare
    def raced(*args):
        receipts=real(*args);path.write_text(path.read_text()+'\n',encoding='utf-8');return receipts
    monkeypatch.setattr(planning_links,'prepare',raced)
    with pytest.raises(Fault,match='Document changed'):s.change('alpha',p,req)
    assert s.detail('alpha',u,p,'D000001')['revision']==2
    monkeypatch.setattr(planning_links,'prepare',real);s.change('alpha',p,request(s,p,u,path))
    receipt=s.detail('alpha',u,p,'D000001')['data']['planning_link']['receipt']
    change(s,p,u,[{'op':'decision.lock','key':'D000001','data':{'baseline':'v1'}}],3,{'D000001':3},authority_refs=['Protect baseline'])
    assert s.detail('alpha',u,p,'D000001')['data']['planning_link']['receipt']==receipt
    assert Artifacts(s).verify('alpha',u,p)['ok']

def test_generated_markdown_companion_and_stale_projection(ready):
    import hashlib
    s,p,u,path=ready;md=path.with_suffix('.md')
    sha=hashlib.sha256(json.dumps(json.loads(path.read_text()),ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
    md.write_text('<!-- CODESENTINEL-GENERATED: canonical-markdown/v1\nsource-sha256: '+sha+'\nschema: codesentinel.canonical-document/v1\n-->\n## Execution\nApproved approach\n',encoding='utf-8')
    with s.catalog.project('alpha',u,p) as (db,_):preview=planning_links.read_document(s,db,str(md))
    req=request(s,p,u,md,expected_document_sha256=preview['sha256'],expected_projection_sha256=preview['projection']['sha256'])
    receipt=s.change('alpha',p,req)['planning_link_receipts'][0];assert receipt['anchor']['projection']['source_marker_sha256']==sha
    assert receipt['anchor']['generator_verification']=='not_checked' and Artifacts(s).verify('alpha',u,p)['ok']
    path.write_text(path.read_text().replace('1.0','2.0'),encoding='utf-8')
    with s.catalog.project('alpha',u,p) as (db,_):
        with pytest.raises(Fault,match='Regenerate'):planning_links.read_document(s,db,str(md))

def test_junction_escape_and_oversized_document(ready,tmp_path):
    import subprocess
    s,p,u,path=ready;outside=tmp_path/'outside';outside.mkdir();document(outside/'secret.json')
    junction=path.parent/'linked'
    result=subprocess.run(['cmd','/c','mklink','/J',str(junction),str(outside)],capture_output=True,text=True,timeout=10)
    assert result.returncode==0,result.stderr
    with s.catalog.project('alpha',u,p) as (db,_):
        with pytest.raises(Fault,match='symbolic links'):planning_links.read_document(s,db,str(junction/'secret.json'))
        oversized=path.parent/'large.json';oversized.write_bytes(b' '*(4*1024*1024+1))
        with pytest.raises(Fault,match='4 MiB'):planning_links.read_document(s,db,str(oversized))
    # Retain the contained junction as test evidence; no recursive deletion of it.

def test_schema2_reads_unlinked_and_link_requires_upgrade(ledger):
    s,p,u=ledger;change(s,p,u,[{'op':'decision.create','data':{'title':'Closed legacy','question':'Which?'}}])
    change(s,p,u,[{'op':'decision.close','key':'D000001','data':{'answer':'A','rationale':'R'}}],1,{'D000001':1},authority_refs=['Owner'])
    assert not s.detail('alpha',u,p,'D000001')['data']['planning_link']['recorded']
    with pytest.raises(Fault,match='Upgrade'):s.change('alpha',p,request(s,p,u))

def test_same_record_planning_link_batch_rejects_atomically(ready):
    s,p,u,path=ready;req=request(s,p,u,path);req.operations.append(__import__('decision_tracker.models',fromlist=['Operation']).Operation(op='decision.reopen',key='D000001',data={'impact':'Review'}));req.authority_refs=['Owner']
    with pytest.raises(Fault,match='separately'):s.change('alpha',p,req)
    assert s.detail('alpha',u,p,'D000001')['revision']==2

def test_policy_frame_bound_rejects_before_commit(ready):
    s,p,u,path=ready;req=planning_links.PolicyChange(expected_policy_revision=1,request_id=uuid4(),reason='x'*8192)
    with pytest.raises(Fault,match='administration capacity'):planning_links.set_policy(s,'alpha',u,p,req)
    with s.catalog.project('alpha',u,p) as (db,_):assert planning_links.policy(db)['policy_revision']==1

def test_policy_superseded_replay_cannot_activate_imported_access(ready):
    s,p,u,path=ready;id=uuid4();policy(s,p,u,required=False,revision=1,request_id=id);policy(s,p,u,required=True,revision=2)
    planning_links.binding_path(s,u).unlink()
    assert policy(s,p,u,required=False,revision=1,request_id=id)['data']['replayed']
    assert not planning_links.binding_path(s,u).exists()

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
