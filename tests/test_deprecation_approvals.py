"""Deprecation approval is operation-local evidence, separate from resolution."""
from dataclasses import replace
from uuid import uuid4
import json
import pytest
from conftest import change
from decision_tracker.models import Change
from decision_tracker.errors import Fault
from decision_tracker import store
from decision_tracker.artifacts import Artifacts, bundle
from decision_tracker.cli import parser, execute

def seed(ledger,closed=False):
    s,p,u=ledger
    change(s,p,u,[{'op':'decision.create','data':{'title':'Old','question':'What?'}},
                  {'op':'decision.create','data':{'title':'Replacement','question':'What next?'}}])
    if closed:change(s,p,u,[{'op':'decision.close','key':'D000001','data':{'answer':'Original','rationale':'Reviewed'}}],revision=1,expected={'D000001':1},authority_refs=['Original approval'])

def request(ledger,approval=None,closed=False,kind='obsolete',**extra):
    s,p,u=ledger
    data={'kind':kind}
    if approval is not None:data['approval']=approval
    if kind in ('duplicate','superseded'):data['replacement_key']='D000002'
    return Change(expected_ledger_uuid=u,expected_revision=2 if closed else 1,
        expected_decision_revisions={'D000001':2 if closed else 1,**({'D000002':1} if kind in ('duplicate','superseded') else {})},
        request_id=uuid4(),reason='End use after review',operations=[{'op':'decision.deprecate','key':'D000001','data':data}],**extra)

@pytest.mark.parametrize('mode',['authenticated_now','legacy_reference','exact','date','unknown'])
@pytest.mark.parametrize('closed',[False,True])
def test_modes_preserve_resolution_replay_and_recovery(ledger,mode,closed):
    seed(ledger,closed);s,p,u=ledger
    a={'mode':'authenticated_now'} if mode=='authenticated_now' else None
    if mode in ('exact','date','unknown'):
        a={'mode':'reported','approver':'Owner','sources':['Review note'],'precision':mode}
        if mode=='date':a.update(occurred_date='2020-01-02',utc_offset_minutes=-300)
        if mode=='exact':a.update(occurred_at='2020-01-02T12:00:00-05:00',utc_offset_minutes=-300)
    req=request(ledger,a,closed,**({'authority_refs':['Legacy instruction']} if a is None else {}))
    actor=replace(p,auth_method='human_password_session') if mode=='authenticated_now' else p
    before=s.detail('alpha',u,p,'D000001')['data']['latest_resolution_approval']
    if mode=='authenticated_now':
        with pytest.raises(Fault,match='signed-in'):s.change('alpha',p,req)
    req.validate_only=True;assert s.change('alpha',actor,req)['validated']
    assert s.detail('alpha',u,p,'D000001')['data']['status']==('closed' if closed else 'open')
    req.validate_only=False;s.change('alpha',actor,req);assert s.change('alpha',actor,req)['replayed']
    d=s.detail('alpha',u,p,'D000001')['data'];assert d['latest_resolution_approval']==before
    assert d['latest_deprecation_approval']['kind']=='deprecate'
    with s.catalog.project('alpha',u,p) as (db,_):
        native=bundle(db);e=next(x['event_json'] for x in native['approval_events'] if x['event_json']['kind']=='deprecate')
        assert e['schema_version']=='decision-tracker.deprecation-approval/v1'
        assert not {'answer','rationale','selected_option'}&set(e)
        assert e['supersedes_event_id'] is None and e['deprecation_reason']==req.reason
    artifacts=Artifacts(s);assert artifacts.verify('alpha',u,p)['ok']
    backup=artifacts.create('alpha',u,p,'backup')['data'];assert not artifacts.restore_check('alpha',u,p,backup['artifact_id'])['data']['activated']
    assert artifacts.import_native(p,native,True)['ok']
    history=s.history('alpha',u,p,'D000001')['data']
    assert sum(bool(x.get('deprecation_approval')) for x in history)==1

@pytest.mark.parametrize('approval,extra,code',[
    ({'mode':'authenticated_now','approver':'Spoof'}, {},'APPROVAL_DATE_INVALID'),
    ({'mode':'reported','precision':'unknown','sources':['note']},{},'APPROVER_REQUIRED'),
    ({'mode':'reported','precision':'unknown','approver':'Owner','sources':[]},{},'APPROVAL_SOURCE_REQUIRED'),
    ({'mode':'reported','precision':'exact','approver':'Owner','sources':['note'],'occurred_at':'2999-01-01T00:00:00Z','utc_offset_minutes':0},{},'APPROVAL_DATE_FUTURE'),
    ({'mode':'authenticated_now'},{'authority_refs':['ambiguous']},'VALIDATION_ERROR'),
    ({'mode':'authenticated_now'},{'occurred_at':'2020-01-01T00:00:00Z'},'VALIDATION_ERROR'),
])
def test_invalid_approval_is_atomic(ledger,approval,extra,code):
    seed(ledger);s,p,u=ledger;req=request(ledger,approval,**extra)
    with pytest.raises(Fault) as fault:s.change('alpha',replace(p,auth_method='human_password_session'),req)
    assert fault.value.code==code
    assert s.detail('alpha',u,p,'D000001')['data']['status']=='open'
    with s.catalog.project('alpha',u,p) as (db,_):assert db.execute('SELECT count(*) FROM approval_events').fetchone()[0]==0

@pytest.mark.parametrize('kind',['duplicate','superseded'])
def test_replacement_and_terminal_guards(ledger,kind):
    seed(ledger);s,p,u=ledger;req=request(ledger,{'mode':'authenticated_now'},kind=kind)
    actor=replace(p,auth_method='human_password_session');s.change('alpha',actor,req)
    assert Artifacts(s).verify('alpha',u,p)['ok']
    with pytest.raises(Fault):change(s,p,u,[{'op':'decision.reopen','key':'D000001','data':{'impact':'Retry'}}],revision=2,expected={'D000001':2},authority_refs=['Review'])

def test_tamper_rejected_even_with_recomputed_event_hash(ledger):
    seed(ledger);s,p,u=ledger;s.change('alpha',p,request(ledger,authority_refs=['Legacy note']))
    with s.catalog.project('alpha',u,p,True) as (db,_):
        db.execute('DROP TRIGGER immutable_approval_update');row=db.execute('SELECT * FROM approval_events').fetchone();e=json.loads(row['event_json']);e['deprecation_reason']='Forged'
        db.execute('UPDATE approval_events SET event_json=?,event_sha256=?',(store.encode(e),store.digest(e)))
    with pytest.raises(Fault,match='inconsistent'):Artifacts(s).verify('alpha',u,p)

def test_cli_approval_read_route(monkeypatch):
    class Client:
        def request(self,method,path,**kwargs):return method,path,kwargs
    args=parser().parse_args(['decision','get','--project','alpha','--ledger-uuid',str(uuid4()),'--key','D000001','--approval-kind','deprecate','--limit','2'])
    monkeypatch.setenv('DT_OPERATOR_TOKEN','synthetic-test-token')
    monkeypatch.setattr('decision_tracker.cli.Client',lambda *args:Client())
    result=execute(args)
    assert result[0]=='GET' and result[1].endswith('/D000001/approvals?kind=deprecate&limit=2')

@pytest.mark.parametrize('version',[2,3,4])
def test_schema_roundtrip_and_existing_alias_replacement(ledger,version):
    from decision_tracker.models import ProjectChange
    s,p,_=ledger;u=str(uuid4());path=s.root/'fresh.sqlite';store.initialize(path,u,schema_version=version)
    s.catalog.mutate(p,ProjectChange(kind='register',project_id='fresh',name='Fresh',relative_path='fresh.sqlite',expected_catalog_revision=1,request_id=uuid4()))
    s.change('fresh',p,Change(expected_ledger_uuid=u,expected_revision=0,request_id=uuid4(),reason='Fixture',operations=[{'op':'decision.create','data':{'title':'Old','question':'Old?'}}]))
    req=Change(expected_ledger_uuid=u,expected_revision=1,expected_decision_revisions={'D000001':1},request_id=uuid4(),reason='Replace obsolete question',authority_refs=['Review note'],operations=[{'op':'decision.create','client_ref':'replacement','data':{'title':'New','question':'New?'}},{'op':'decision.deprecate','key':'D000001','data':{'kind':'superseded','replacement_key':'@replacement'}}])
    s.change('fresh',p,req);artifacts=Artifacts(s);assert artifacts.verify('fresh',u,p)['ok']
    with s.catalog.project('fresh',u,p) as (db,_):native=bundle(db)
    assert native['schema_version']==version and native['approval_events'][0]['event_json']['replacement_key']=='D000002'
    assert artifacts.import_native(p,native,True)['data']['logical_sha256']==store.digest(native)
    backup=artifacts.create('fresh',u,p,'backup')['data'];assert not artifacts.restore_check('fresh',u,p,backup['artifact_id'])['data']['activated']

def test_api_filtered_reads_cursor_binding_permissions_and_discovery(client):
    from test_api import setup_project
    u=setup_project(client);path='/api/v1/projects/alpha';data={'expected_ledger_uuid':u,'expected_revision':0,'request_id':str(uuid4()),'reason':'Seed','operations':[{'op':'decision.create','data':{'title':'Question','question':'Which?'}}]}
    assert client.post(path+'/changes',json=data).status_code==200
    data.update(expected_revision=1,expected_decision_revisions={'D000001':1},request_id=str(uuid4()),authority_refs=['Resolution note'],operations=[{'op':'decision.close','key':'D000001','data':{'answer':'Answer','rationale':'Reason'}}])
    assert client.post(path+'/changes',json=data).status_code==200
    data.update(expected_revision=2,expected_decision_revisions={'D000001':2},request_id=str(uuid4()),authority_refs=[],operations=[{'op':'decision.deprecate','key':'D000001','data':{'kind':'obsolete','approval':{'mode':'reported','approver':'Owner','sources':['Withdrawal note'],'precision':'unknown'}}}])
    assert client.post(path+'/changes',json=data).status_code==200
    endpoint=path+'/decisions/D000001/approvals'
    page=client.get(endpoint+'?limit=1').json();assert not page['complete'] and page['next_cursor']
    assert client.get(endpoint,params={'kind':'deprecate','cursor':page['next_cursor']}).status_code==409
    dep=client.get(endpoint+'?kind=deprecate').json()['data'];assert len(dep)==1
    assert dep[0]['kind']=='deprecate' and dep[0]['schema_version']=='decision-tracker.deprecation-approval/v1'
    event=client.get(endpoint+'/'+dep[0]['event_id']+'?kind=deprecate').json()['data'];assert event['deprecation_reason']=='Seed'
    assert client.get(endpoint+'/'+dep[0]['event_id']+'?kind=resolution').status_code==404
    assert client.get(endpoint+'?kind=wrong').status_code==422
    discovery=client.get('/api/v1/schema').json()['x-decision-tracker']
    assert 'deprecation_approval_v1' in discovery['capabilities']
    assert discovery['deprecation_approval']['event']['additionalProperties'] is False
    assert 'answer' not in discovery['deprecation_approval']['event']['properties']
    before=client.get(path+'/decisions/D000001/as-of?revision=2').json()['data'];assert before['latest_deprecation_approval'] is None and before['latest_resolution_approval']
    client.headers['X-Ledger-UUID']=str(uuid4());assert client.get(endpoint).status_code==409
    client.headers['X-Ledger-UUID']=u;client.headers['Authorization']='Bearer '+client.readonly
    assert client.post(path+'/changes',json=data).status_code==403

@pytest.mark.parametrize('phase',['before_commit','after_commit'])
def test_interrupted_deprecation_recovers_atomically(ledger,monkeypatch,phase):
    seed(ledger);s,p,u=ledger;req=request(ledger,authority_refs=['Review note'])
    if phase=='before_commit':
        import decision_tracker.approvals as approvals
        real=approvals.insert
        def interrupted(db,event):real(db,event);raise RuntimeError('Synthetic interruption')
        monkeypatch.setattr(approvals,'insert',interrupted)
        with pytest.raises(RuntimeError):s.change('alpha',p,req)
        assert s.detail('alpha',u,p,'D000001')['data']['status']=='open'
        monkeypatch.setattr(approvals,'insert',real)
        assert not s.change('alpha',p,req)['replayed']
    else:
        s.on_commit=lambda *_:(_ for _ in ()).throw(RuntimeError('Synthetic lost notification'))
        s.change('alpha',p,req);assert s.change('alpha',p,req)['replayed']
    assert Artifacts(s).verify('alpha',u,p)['ok']

def test_old_reader_refuses_new_event_and_historical_deprecation_replays(ledger):
    import importlib.util
    from pathlib import Path
    seed(ledger);s,p,u=ledger;req=request(ledger,authority_refs=['Old reference instruction']);s.change('alpha',p,req)
    with s.catalog.project('alpha',u,p,True) as (db,_):
        fixture=Path(__file__).parent/'fixtures/pre_deprecation_approval_history.py'
        spec=importlib.util.spec_from_file_location('decision_tracker.older_history',fixture);older=importlib.util.module_from_spec(spec);spec.loader.exec_module(older)
        with pytest.raises(Fault,match='inconsistent'):older.validate(db,store.metadata(db))
        # Simulate the exact pre-feature reference-only history: preserve receipt/request/snapshot.
        db.execute('DROP TRIGGER immutable_approval_delete');db.execute('DELETE FROM approval_events')
    assert s.change('alpha',p,req)['replayed']
    assert s.detail('alpha',u,p,'D000001')['data']['latest_deprecation_approval'] is None
    assert Artifacts(s).verify('alpha',u,p)['ok']
    with s.catalog.project('alpha',u,p) as (db,_):assert db.execute('SELECT count(*) FROM approval_events').fetchone()[0]==0

@pytest.mark.parametrize('failure',['no-decide','wrong-project','wrong-uuid','stale-ledger','stale-record','blank-authority','missing-authority','event-spoof'])
def test_authority_identity_and_revision_failures_are_atomic(ledger,failure):
    seed(ledger);s,p,u=ledger;req=request(ledger,authority_refs=['Instruction'])
    if failure=='no-decide':p=replace(p,capabilities=p.capabilities-{'decide'})
    if failure=='wrong-project':p=replace(p,projects=frozenset({'other'}))
    if failure=='wrong-uuid':req.expected_ledger_uuid=uuid4()
    if failure=='stale-ledger':req.expected_revision=0
    if failure=='stale-record':req.expected_decision_revisions={'D000001':99}
    if failure=='blank-authority':req.authority_refs=[' ']
    if failure=='missing-authority':req.authority_refs=[]
    if failure=='event-spoof':req.operations[0].data['event_id']='spoof'
    with pytest.raises(Fault):s.change('alpha',p,req)
    s,p,u=ledger
    assert s.detail('alpha',u,p,'D000001')['data']['status']=='open'
    with s.catalog.project('alpha',u,p) as (db,_):assert db.execute('SELECT count(*) FROM approval_events').fetchone()[0]==0

@pytest.mark.parametrize('kind',['obsolete','withdrawn','error'])
def test_all_simple_types_preserve_replay_permission_checks(ledger,kind):
    seed(ledger,True);s,p,u=ledger;req=request(ledger,closed=True,kind=kind,authority_refs=['Authorized instruction']);s.change('alpha',p,req)
    changed=req.model_copy(deep=True);changed.reason='Changed'
    with pytest.raises(Fault) as error:s.change('alpha',p,changed)
    assert error.value.code=='REQUEST_ID_REUSED'
    with pytest.raises(Fault):s.change('alpha',replace(p,capabilities=p.capabilities-{'decide'}),req)
    assert Artifacts(s).verify('alpha',u,p)['ok']

@pytest.mark.parametrize('phase',['before','after'])
def test_process_exit_during_deprecation_recovers(ledger,phase):
    import subprocess,sys
    seed(ledger);s,p,u=ledger;req=request(ledger,authority_refs=['Actual synthetic instruction'])
    script='''
import os,sys
from decision_tracker.service import Service
from decision_tracker.auth import Principal
from decision_tracker.models import Change
from decision_tracker import approvals
s=Service(sys.argv[1]);p=Principal('operator',frozenset({'*'}),frozenset({'read','write','decide'}))
if sys.argv[3]=='before':
 real=approvals.insert
 def interrupted(db,event):real(db,event);os._exit(71)
 approvals.insert=interrupted
else:s.on_commit=lambda *_:os._exit(72)
s.change('alpha',p,Change.model_validate_json(sys.argv[2]))
'''
    r=subprocess.run([sys.executable,'-c',script,str(s.root),req.model_dump_json(),phase],capture_output=True,timeout=20)
    assert r.returncode==(71 if phase=='before' else 72),r.stderr
    assert s.detail('alpha',u,p,'D000001')['data']['status']==('open' if phase=='before' else 'deprecated')
    assert s.change('alpha',p,req)['replayed']==(phase=='after')
    assert Artifacts(s).verify('alpha',u,p)['ok']
