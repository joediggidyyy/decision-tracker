from dataclasses import replace
from datetime import datetime, timezone, timedelta
from uuid import uuid4
import json
import sqlite3
import pytest
from conftest import change
from decision_tracker import store
from decision_tracker.models import Change
from decision_tracker.artifacts import Artifacts, bundle, validate_history
from decision_tracker.approval_api import upgrade, Upgrade
from decision_tracker.approvals import Approval
from decision_tracker.errors import Fault

def seed(s,p,u):
    change(s,p,u,[{'op':'decision.create','client_ref':'d','data':{'title':'Storage','question':'Where?'}},
                  {'op':'option.add','key':'@d','data':{'title':'Local storage','description':'Use local storage','benefit':'Reliable locking','cost':'Separate backup'}}])
    return s.children('alpha',u,p,'D000001','alternatives')['data'][0]

def resolution(u,option=None,approval=None,revision=1,record_revision=1):
    data={'answer':'Use local storage','rationale':'Reliable locking; separate backups','approval':approval or {'mode':'authenticated_now'}}
    if option:data.update(selected_option=option['id'],expected_option_revision=option['revision'])
    return Change(expected_ledger_uuid=u,expected_revision=revision,expected_decision_revisions={'D000001':record_revision},request_id=uuid4(),reason='Approved storage proposal',operations=[{'op':'decision.close','key':'D000001','data':data}])

def test_current_approval_replay_restore_and_identity(ledger):
    s,p,u=ledger;option=seed(s,p,u);human=replace(p,auth_method='human_password_session');req=resolution(u,option)
    with pytest.raises(Fault,match='signed-in'):s.change('alpha',p,req)
    result=s.change('alpha',human,req);assert result['revision']==2
    event=s.detail('alpha',u,p,'D000001')['data']['latest_resolution_approval']
    assert event['mode']=='authenticated_now' and event['recorded_by']==p.id and event['recorded_at']==event['occurred_at']
    assert s.change('alpha',human,req)['replayed']
    # An agent cannot replay human approval by reusing a principal ID in direct tests.
    with pytest.raises(Fault,match='signed-in'):s.change('alpha',p,req)
    artifacts=Artifacts(s);assert artifacts.verify('alpha',u,p)['data']['integrity']=='ok'
    backup=artifacts.create('alpha',u,p,'backup')['data'];assert artifacts.restore_check('alpha',u,p,backup['artifact_id'])['data']['activated'] is False
    with s.catalog.project('alpha',u,p) as (db,_):native=bundle(db)
    assert native['schema_version']==2 and len(native['approval_events'])==1
    imported=artifacts.import_native(p,native,True);assert imported['data']['logical_sha256']==store.digest(native)

@pytest.mark.parametrize('precision',['date','unknown','exact'])
def test_reported_precision_and_immutable_recording(ledger,precision):
    s,p,u=ledger;seed(s,p,u)
    approval={'mode':'reported','approver':'Owner','sources':['Meeting note 2020-01-02'],'precision':precision}
    if precision=='date':approval.update(occurred_date='2020-01-02',utc_offset_minutes=-300)
    if precision=='exact':approval.update(occurred_at='2020-01-02T14:30:00-05:00',utc_offset_minutes=-300)
    s.change('alpha',p,resolution(u,approval=approval));event=s.detail('alpha',u,p,'D000001')['data']['latest_resolution_approval']
    assert event['precision']==precision and event['reported_approver']=='Owner'
    assert (event['occurred_at'] is None)==(precision!='exact')
    assert event['recorded_at'].startswith(str(datetime.now().year))
    assert Artifacts(s).verify('alpha',u,p)['ok']

def test_invalid_dates_proposal_and_atomic_failure(ledger):
    s,p,u=ledger;option=seed(s,p,u);human=replace(p,auth_method='human_password_session')
    req=resolution(u,option);req.operations[0].data['answer']='Something else'
    with pytest.raises(Fault,match='differs'):s.change('alpha',human,req)
    req=resolution(u,option);req.operations[0].data['expected_option_revision']=999
    with pytest.raises(Fault,match='changed'):s.change('alpha',human,req)
    req=resolution(u,approval={'mode':'reported','precision':'exact','approver':'Owner','sources':['Note'],'occurred_at':'2999-01-01T00:00:00+00:00','utc_offset_minutes':0})
    with pytest.raises(Fault,match='future'):s.change('alpha',p,req)
    assert s.list_decisions('alpha',u,p)['revision']==1
    with s.catalog.project('alpha',u,p) as (db,_):assert db.execute('SELECT count(*) FROM approval_events').fetchone()[0]==0
    with pytest.raises(ValueError):Approval(mode='authenticated_now',approver='Spoof')
    with pytest.raises(ValueError):Approval(mode='reported',precision='unknown',approver='Owner',sources=['note'],occurred_date='2020-01-01')

def test_dry_run_and_tamper_detection(ledger):
    s,p,u=ledger;seed(s,p,u);human=replace(p,auth_method='human_password_session');req=resolution(u);req.validate_only=True
    assert s.change('alpha',human,req)['validated'];assert s.list_decisions('alpha',u,p)['revision']==1
    req.validate_only=False;s.change('alpha',human,req)
    with s.catalog.project('alpha',u,p,True) as (db,_):
        with pytest.raises(sqlite3.IntegrityError):db.execute('DELETE FROM approval_events')
        db.execute('DROP TRIGGER immutable_approval_update')
        row=db.execute('SELECT * FROM approval_events').fetchone();e=json.loads(row['event_json']);e['recorded_by']='Forged'
        db.execute('UPDATE approval_events SET event_json=?,event_sha256=?',(store.encode(e),store.digest(e)))
    with pytest.raises(Fault,match='inconsistent'):Artifacts(s).verify('alpha',u,p)

def test_v1_upgrade_keeps_history_and_receipt_replays(ledger):
    s,p,u=ledger;seed(s,p,u)
    with s.catalog.project('alpha',u,p) as (db,_):native=bundle(db)
    for table in ('approval_events','schema_upgrades'):native.pop(table)
    native['schema_version']=native['meta']['schema_version']=1;native['format']='decision-tracker/v1'
    artifacts=Artifacts(s);candidate=artifacts.import_native(p,native,True)['data']
    from decision_tracker.models import ProjectChange
    from decision_tracker.auth import Principal
    # Same UUID may only have one enabled registration: use a separate service.
    other=__import__('decision_tracker.service',fromlist=['Service']).Service(s.root.parent/'other')
    other_artifacts=Artifacts(other);candidate=other_artifacts.import_native(p,native,True)['data']
    other.catalog.mutate(p,ProjectChange(kind='register',project_id='alpha',name='Alpha',relative_path=candidate['relative_path'],expected_catalog_revision=0,request_id=uuid4()))
    with pytest.raises(Fault,match='upgrade'):other.change('alpha',replace(p,auth_method='human_password_session'),resolution(u))
    check=upgrade(other_artifacts,'alpha',u,p);assert check['data']['history']=='verified'
    req=Upgrade(expected_revision=1,request_id=uuid4());result=upgrade(other_artifacts,'alpha',u,p,req)
    assert result['schema_version']==2 and result['revision']==1
    assert upgrade(other_artifacts,'alpha',u,p,req)['data']['replayed']
    with other.catalog.project('alpha',u,p) as (db,_):
        assert bundle(db)['transactions']==native['transactions'];assert bundle(db)['revisions']==native['revisions']
    other.change('alpha',replace(p,auth_method='human_password_session'),resolution(u))
    assert other_artifacts.verify('alpha',u,p)['ok']

def legacy_candidate(ledger,folder):
    s,p,u=ledger;seed(s,p,u)
    with s.catalog.project('alpha',u,p) as (db,_):native=bundle(db)
    native.pop('approval_events');native.pop('schema_upgrades')
    native.update(format='decision-tracker/v1',schema_version=1);native['meta']['schema_version']=1
    from decision_tracker.service import Service
    from decision_tracker.models import ProjectChange
    other=Service(s.root.parent/folder);artifacts=Artifacts(other)
    candidate=artifacts.import_native(p,native,True)['data']
    other.catalog.mutate(p,ProjectChange(kind='register',project_id='alpha',name='Alpha',relative_path=candidate['relative_path'],expected_catalog_revision=0,request_id=uuid4()))
    return other,artifacts,p,u,native

@pytest.mark.parametrize('stage',['backup','restore','ddl','final-validation'])
def test_upgrade_failure_is_atomic(ledger,monkeypatch,stage):
    other,artifacts,p,u,native=legacy_candidate(ledger,'fault-'+stage)
    def fail(*a,**k):raise RuntimeError('injected upgrade failure')
    if stage=='backup':monkeypatch.setattr(artifacts,'create',fail)
    if stage=='restore':monkeypatch.setattr(artifacts,'restore_check',fail)
    if stage=='ddl':monkeypatch.setattr(store,'APPROVAL_SQL',store.APPROVAL_SQL+'\nINVALID DDL;\n')
    if stage=='final-validation':
        from decision_tracker import approval_api
        real=approval_api.validate_history
        def validate(db):
            if store.metadata(db)['schema_version']==2:fail()
            return real(db)
        monkeypatch.setattr(approval_api,'validate_history',validate)
    expected=Fault if stage=='ddl' else RuntimeError
    with pytest.raises(expected):upgrade(artifacts,'alpha',u,p,Upgrade(expected_revision=1,request_id=uuid4()))
    with other.catalog.project('alpha',u,p) as (db,_):assert bundle(db)==native

def test_upgrade_concurrent_replay(ledger):
    from concurrent.futures import ThreadPoolExecutor
    other,artifacts,p,u,native=legacy_candidate(ledger,'concurrent')
    req=Upgrade(expected_revision=1,request_id=uuid4())
    with ThreadPoolExecutor(2) as pool:results=list(pool.map(lambda _:upgrade(artifacts,'alpha',u,p,req),range(2)))
    assert sorted(x['data']['replayed'] for x in results)==[False,True]
    with other.catalog.project('alpha',u,p) as (db,_):assert bundle(db)['transactions']==native['transactions']

def test_reopen_edit_and_mixed_authority_are_separate(ledger):
    s,p,u=ledger;option=seed(s,p,u);human=replace(p,auth_method='human_password_session')
    request=resolution(u,option);s.change('alpha',human,request)
    first=s.detail('alpha',u,p,'D000001')['data']['latest_resolution_approval']
    change(s,p,u,[{'op':'decision.reopen','key':'D000001','data':{'impact':'Reconsider'}}],2,{'D000001':2},authority_refs=['Reconsideration approval'])
    assert s.detail('alpha',u,p,'D000001')['data']['latest_resolution_approval']==first
    change(s,p,u,[{'op':'decision.close','key':'D000001','data':{'answer':'New answer','rationale':'Reconsidered'}}],3,{'D000001':3},authority_refs=['External approval'])
    legacy=s.detail('alpha',u,p,'D000001')['data']['latest_resolution_approval'];assert legacy['mode']=='legacy_reference'
    change(s,human,u,[{'op':'decision.edit-resolution','key':'D000001','data':{'answer':'Corrected answer','rationale':'Correction','approval':{'mode':'authenticated_now'}}},
                      {'op':'decision.create','data':{'title':'Other','question':'Unrelated?'}}],4,{'D000001':4})
    with s.catalog.project('alpha',u,p) as (db,_):
        events=[json.loads(r[0]) for r in db.execute('SELECT event_json FROM approval_events ORDER BY ledger_revision')]
        assert len(events)==3 and events[2]['supersedes_event_id']==events[1]['event_id']
        assert store.get(db,'decisions','D000002')['authority_refs']==[]
    assert Artifacts(s).verify('alpha',u,p)['ok']
    assert s.detail('alpha',u,p,'D000001',2)['data']['latest_resolution_approval']==first

def test_approval_aggregate_size_and_full_source_count(ledger):
    s,p,u=ledger;seed(s,p,u)
    req=resolution(u,approval={'mode':'reported','approver':'Owner','sources':['source '+str(i) for i in range(32)],'precision':'unknown'})
    req.operations[0].data['answer']='a'*32768;req.operations[0].data['rationale']='b'*32768
    with pytest.raises(Fault,match='128 KiB'):s.change('alpha',p,req)
    req.operations[0].data.update(answer='A',rationale='B');s.change('alpha',p,req)
    with s.catalog.project('alpha',u,p) as (db,_):assert len(store.get(db,'decisions','D000001')['authority_refs'])==33
    assert Artifacts(s).verify('alpha',u,p)['ok']

@pytest.mark.parametrize('boundary',['before-commit','after-commit'])
def test_upgrade_process_exit_recovery(ledger,boundary):
    import subprocess,sys
    other,artifacts,p,u,native=legacy_candidate(ledger,'process-'+boundary)
    request_id=str(uuid4())
    script="""
import os,sys
from decision_tracker.service import Service
from decision_tracker.artifacts import Artifacts
from decision_tracker.auth import Principal
from decision_tracker import approval_api,store
s=Service(sys.argv[1]);p=Principal('operator',frozenset({'*'}),frozenset({'read','write','maintain','registry','decide'}))
real=approval_api.validate_history
def validate(db):
    if store.metadata(db)['schema_version']==2:os._exit(71)
    return real(db)
if sys.argv[4]=='before-commit':approval_api.validate_history=validate
approval_api.upgrade(Artifacts(s),'alpha',sys.argv[2],p,approval_api.Upgrade(expected_revision=1,request_id=sys.argv[3]))
os._exit(72)
"""
    result=subprocess.run([sys.executable,'-c',script,str(other.root),u,request_id,boundary],capture_output=True,timeout=20)
    assert result.returncode==(71 if boundary=='before-commit' else 72),result.stderr
    with other.catalog.project('alpha',u,p) as (db,_):
        if boundary=='before-commit':assert bundle(db)==native
        else:assert store.metadata(db)['schema_version']==2
    replay=upgrade(artifacts,'alpha',u,p,Upgrade(expected_revision=1,request_id=request_id))
    assert replay['data']['replayed']==(boundary=='after-commit')
    assert artifacts.verify('alpha',u,p)['ok']
