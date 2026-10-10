"""Closed-record rules exercise the shared service and public adapters, using isolated data."""
from uuid import uuid4
from dataclasses import replace
import json
import pytest
from conftest import change
from decision_tracker import store, state, cli
from decision_tracker.models import Change
from decision_tracker.errors import Fault
from decision_tracker.artifacts import Artifacts, bundle


def seeded(ledger):
    s,p,u=ledger
    change(s,p,u,[{'op':'decision.create','client_ref':'a','data':{'title':'A','question':'Which?'}},
                  {'op':'decision.create','client_ref':'b','data':{'title':'B','question':'Related?'}},
                  {'op':'option.add','key':'@a','data':{'title':'Option'}},
                  {'op':'reference.add','key':'@a','data':{'label':'Source','locator':'synthetic:source'}},
                  {'op':'link.add','key':'@a','data':{'target_key':'@b','type':'relates_to'}}])
    change(s,p,u,[{'op':'decision.close','key':'D000001','data':{'answer':'A','rationale':'Reviewed'}}],1,{'D000001':1},authority_refs=['Synthetic approval'])
    return s,p,u


def native(s,p,u):
    with s.catalog.project('alpha',u,p) as (db,_):return bundle(db)


@pytest.mark.parametrize('op',sorted(state.ORDINARY))
@pytest.mark.parametrize('dry',[False,True])
def test_closed_rejects_every_ordinary_operation_without_commit(ledger,op,dry):
    s,p,u=seeded(ledger);before=native(s,p,u)
    children=s.children('alpha',u,p,'D000001','links' if op.startswith('link.') else 'alternatives' if op.startswith('option.') else 'references')['data']
    data={'target_key':'D000002','type':'relates_to'} if op=='link.add' else {}
    operation={'op':op,'key':'D000001','data':data}
    if op.endswith(('.edit','.retire','.unlink')) and not op.startswith('decision.'):operation['id']=children[0]['id']
    with pytest.raises(Fault) as rejected:change(s,p,u,[operation],2,{'D000001':2,'D000002':1},authority_refs=['Synthetic'],validate_only=dry)
    assert (rejected.value.code,rejected.value.status)==('INVALID_TRANSITION',422)
    assert native(s,p,u)==before


@pytest.mark.parametrize('extra',[{'op':'decision.edit','data':{'title':'Bypass'}},{'op':'decision.close','data':{'answer':'Bypass'}}])
def test_reopen_must_commit_separately(ledger,extra):
    s,p,u=seeded(ledger);before=native(s,p,u)
    with pytest.raises(Fault):change(s,p,u,[{'op':'decision.reopen','key':'D000001','data':{'impact':'Review'}},dict(extra,key='D000001')],2,{'D000001':2},authority_refs=['Synthetic'])
    assert native(s,p,u)==before
    change(s,p,u,[{'op':'decision.reopen','key':'D000001','data':{'impact':'Review'}}],2,{'D000001':2},authority_refs=['Synthetic'])
    change(s,p,u,[{'op':'decision.edit','key':'D000001','data':{'answer':'Revised','rationale':'Reviewed'}}],3,{'D000001':3})
    change(s,p,u,[{'op':'decision.close','key':'D000001','data':{}}],4,{'D000001':4},authority_refs=['Synthetic'])
    assert s.detail('alpha',u,p,'D000001')['data']['answer']=='Revised'
    assert Artifacts(s).verify('alpha',u,p)['ok']


def test_relationship_target_and_lifecycle_exceptions(ledger):
    s,p,u=seeded(ledger);before=native(s,p,u)
    change(s,p,u,[{'op':'link.add','key':'D000002','data':{'target_key':'D000001','type':'depends_on'}}],2,{'D000001':2,'D000002':1})
    change(s,p,u,[{'op':'decision.lock','key':'D000001','data':{'baseline':'Release'}}],3,{'D000001':3},authority_refs=['Synthetic'])
    change(s,p,u,[{'op':'decision.amend','key':'D000001','data':{'question':'What changes?','impact':'New requirement','baseline_disposition':'continue'}}],4,{'D000001':4},authority_refs=['Synthetic'])
    assert s.detail('alpha',u,p,'D000003')['data']['status']=='open'
    change(s,p,u,[{'op':'decision.deprecate','key':'D000002','data':{'kind':'superseded','replacement_key':'D000001'}}],5,{'D000002':2,'D000001':5},authority_refs=['Synthetic'])
    change(s,p,u,[{'op':'decision.deprecate','key':'D000001','data':{'kind':'obsolete'}}],6,{'D000001':6},authority_refs=['Synthetic'])
    assert Artifacts(s).verify('alpha',u,p)['ok']


def test_historical_correction_replays_but_new_correction_rejects(ledger,monkeypatch):
    s,p,u=seeded(ledger)
    request=Change(expected_ledger_uuid=u,expected_revision=2,expected_decision_revisions={'D000001':2},request_id=uuid4(),reason='Historical correction',authority_refs=['Synthetic approval'],operations=[{'op':'decision.edit-resolution','key':'D000001','data':{'answer':'Historical answer'}}])
    # Reconstruct predecessor behavior in isolated fixture only; no runtime bypass.
    with monkeypatch.context() as old:
        old.setattr(state,'check_new_request',lambda db,req:None)
        old.setattr(state,'ORDINARY',state.ORDINARY-{'decision.edit-resolution'})
        receipt=s.change('alpha',p,request)
    before=native(s,p,u)
    assert s.change('alpha',p,request)==dict(receipt,replayed=True)
    new=request.model_copy(update={'request_id':uuid4(),'expected_revision':3,'expected_decision_revisions':{'D000001':3}})
    with pytest.raises(Fault) as rejected:s.change('alpha',p,new)
    assert rejected.value.code=='INVALID_TRANSITION'
    different=request.model_copy(deep=True);different.reason='Different'
    with pytest.raises(Fault) as reused:s.change('alpha',p,different)
    assert reused.value.code=='REQUEST_ID_REUSED'
    with pytest.raises(Fault) as forbidden:s.change('alpha',replace(p,capabilities=frozenset({'read'})),request)
    assert forbidden.value.code=='FORBIDDEN'
    assert native(s,p,u)==before
    assert Artifacts(s).verify('alpha',u,p)['ok']
    assert s.detail('alpha',u,p,'D000001',3)['data']['answer']=='Historical answer'
    assert native(s,p,u)['approval_events'][-1]['event_json']['kind']=='edit_resolution'


def test_http_cli_and_schema_share_policy(client,monkeypatch,tmp_path,capsys):
    project=client.post('/api/v1/projects',json={'project_id':'alpha','name':'Alpha','expected_catalog_revision':0,'request_id':str(uuid4())}).json()
    u=project['data']['ledger_uuid'];client.headers['X-Ledger-UUID']=u
    def request(op,rev,keyrev=None,dry=False):return {'expected_ledger_uuid':u,'expected_revision':rev,'expected_decision_revisions':{'D000001':keyrev} if keyrev else {},'request_id':str(uuid4()),'reason':'Synthetic policy','authority_refs':['Synthetic'],'validate_only':dry,'operations':[op]}
    path='/api/v1/projects/alpha/changes'
    assert client.post(path,json=request({'op':'decision.create','data':{'title':'A','question':'Q'}},0)).status_code==200
    assert client.post(path,json=request({'op':'decision.close','key':'D000001','data':{'answer':'A','rationale':'Reviewed'}},1,1)).status_code==200
    schema=client.get('/api/v1/schema').json();assert schema['x-decision-tracker']['mutation_policy']['edit_resolution']=='withdrawn_for_new_writes'
    payload=request({'op':'decision.edit','key':'D000001','data':{'title':'Blocked'}},2,2,True)
    r=client.post(path,json=payload);assert r.status_code==422 and r.json()['error']['code']=='INVALID_TRANSITION'
    def adapter(self,method,path,data=None,uuid=None,download=None):
        response=client.request(method,path,json=data)
        value=response.json()
        if not response.is_success:raise Fault(value['error']['code'],value['error']['message'],response.status_code)
        return value
    monkeypatch.setattr(cli.Client,'request',adapter);monkeypatch.setenv('DT_OPERATOR_TOKEN','synthetic-cli-only-credential-123456789')
    file=tmp_path/'change.json';file.write_text(json.dumps(payload))
    assert cli.main(['change','apply','--input',str(file),'--project','alpha','--ledger-uuid',u,'--dry-run','--json'])==2
    assert json.loads(capsys.readouterr().out)['error']['code']=='INVALID_TRANSITION'
    assert client.get('/api/v1/projects/alpha/decisions/D000001').json()['data']['revision']==2
    policy=schema['x-decision-tracker']['mutation_policy']
    assert 'closed_context_v1' in schema['x-decision-tracker']['capabilities'] and policy['relationship_endpoints']=='both_active_open_or_closed'
    assert set(policy['protected_closed_supplemental'])==state.SUPPLEMENTAL
    file.write_text(json.dumps({'evidence_state':{'acceptance':{'status':'Reported acceptance','evidence_refs':['Synthetic source']}}}))
    assert cli.main(['decision','set-evidence','--key','D000001','--input',str(file),'--project','alpha','--ledger-uuid',u,'--expected-revision','2','--record-revision','2','--request-id',str(uuid4()),'--reason','Record evidence','--json'])==0
    assert json.loads(capsys.readouterr().out)['ok']
    current=client.get('/api/v1/projects/alpha/decisions/D000001').json()['data']
    assert current['status']=='closed' and current['evidence_state']['acceptance']['status']=='Reported acceptance'



def test_revision_precedence_and_in_batch_closure_rollback(ledger):
    s,p,u=seeded(ledger);before=native(s,p,u)
    with pytest.raises(Fault) as stale:change(s,p,u,[{'op':'decision.edit','key':'D000001','data':{'title':'Old draft'}}],2,{'D000001':1})
    assert stale.value.code=='STALE_REVISION'
    with pytest.raises(Fault):change(s,p,u,[{'op':'decision.close','key':'D000002','data':{'answer':'B','rationale':'Reviewed'}},{'op':'decision.edit','key':'D000002','data':{'title':'After closure'}}],2,{'D000002':1},authority_refs=['Synthetic'])
    assert native(s,p,u)==before

# Supplemental context preserves approved core and uses both endpoint revisions.
def mutate_current(s,p,u,ops,**extra):
    listing=s.list_decisions('alpha',u,p)['data']
    expected={d['key']:d['revision'] for d in listing}
    with s.catalog.project('alpha',u,p) as (db,_):revision=store.metadata(db)['ledger_revision']
    return change(s,p,u,ops,revision,expected,**extra)


def core(s,p,u,key):
    d=s.detail('alpha',u,p,key)['data']
    return {k:d.get(k) for k in ('title','question','answer','rationale','owner_role','occurred_at','status','locked','baseline','authority_refs','latest_resolution_approval','planning_link','legacy_origin')}


@pytest.mark.parametrize('protected',[False,True])
def test_supplemental_core_replay_patch_and_recovery(ledger,protected):
    s,p,u=seeded(ledger)
    if protected:mutate_current(s,p,u,[{'op':'decision.lock','key':'D000001','data':{'baseline':'Release'}}],authority_refs=['Synthetic'])
    before=core(s,p,u,'D000001');original=native(s,p,u)
    ops=[{'op':'reference.add','key':'D000001','data':{'label':'Later source','locator':'synthetic:later'}},
         {'op':'decision.set-evidence','key':'D000001','data':{'evidence_state':{'implementation':{'status':'Delivered','evidence_refs':['synthetic:build'],'responsible_role':'agent'}}}}]
    trial=mutate_current(s,p,u,ops,validate_only=True);assert trial['validated'] and native(s,p,u)==original
    result=mutate_current(s,p,u,ops);assert result['data'][0]['revision']==before_revision(original,'D000001')+1
    mutate_current(s,p,u,[{'op':'decision.set-evidence','key':'D000001','data':{'evidence_state':{'verification':{'status':'Verified'}}}}])
    evidence=s.detail('alpha',u,p,'D000001')['data']['evidence_state'];assert evidence['implementation']['status']=='Delivered' and evidence['verification']['status']=='Verified'
    mutate_current(s,p,u,[{'op':'decision.set-evidence','key':'D000001','data':{'evidence_state':{'verification':None}}}])
    assert s.detail('alpha',u,p,'D000001')['data']['evidence_state']['verification'] is None
    assert core(s,p,u,'D000001')==before
    after=native(s,p,u);assert after['approval_events']==original['approval_events'];assert after['alternatives']==original['alternatives']
    objects=Artifacts(s);assert objects.verify('alpha',u,p)['ok']
    backup=objects.create('alpha',u,p,'backup');assert backup['ok'];assert objects.restore_check('alpha',u,p,backup['data']['artifact_id'])['ok']
    imported=objects.import_native(p,after,True);assert imported['ok']
    # Exact replay of an original retained request after later writes.
    with s.catalog.project('alpha',u,p) as (db,_):
        row=db.execute('SELECT request_json,request_id FROM transactions WHERE ledger_revision=?',(result['revision'],)).fetchone()
        payload=json.loads(row['request_json']);payload['request_id']=row['request_id']
    req=Change.model_validate(payload);assert s.change('alpha',p,req)['replayed']
    req.reason='Altered'
    with pytest.raises(Fault) as reused:s.change('alpha',p,req)
    assert reused.value.code=='REQUEST_ID_REUSED'


def before_revision(value,key):
    return next(d['revision'] for d in value['decisions'] if d['key']==key)


@pytest.mark.parametrize('left',['open','closed','protected'])
@pytest.mark.parametrize('right',['open','closed','protected'])
def test_relationship_state_matrix_and_symmetric_unlink(ledger,left,right):
    s,p,u=ledger
    change(s,p,u,[{'op':'decision.create','data':{'title':'A','question':'Q'}},{'op':'decision.create','data':{'title':'B','question':'Q'}}])
    for key,status in [('D000001',left),('D000002',right)]:
        if status!='open':mutate_current(s,p,u,[{'op':'decision.close','key':key,'data':{'answer':'A','rationale':'R'}}],authority_refs=['Synthetic'])
        if status=='protected':mutate_current(s,p,u,[{'op':'decision.lock','key':key,'data':{'baseline':'Release'}}],authority_refs=['Synthetic'])
    before=[core(s,p,u,k) for k in ['D000001','D000002']]
    result=mutate_current(s,p,u,[{'op':'link.add','key':'D000002','data':{'target_key':'D000001','type':'relates_to'}}]);assert len(result['data'])==2
    link=s.children('alpha',u,p,'D000002','links')['data'][0];assert link['source_key']=='D000001'
    mutate_current(s,p,u,[{'op':'link.unlink','key':'D000002','id':link['id']}])
    mutate_current(s,p,u,[{'op':'link.add','key':'D000001','data':{'target_key':'D000002','type':'depends_on'}}])
    links=s.children('alpha',u,p,'D000002','links')['data'];dependency=next(x for x in links if x['active'])
    old=native(s,p,u)
    with pytest.raises(Fault):mutate_current(s,p,u,[{'op':'link.unlink','key':'D000002','id':dependency['id']}])
    with pytest.raises(Fault):mutate_current(s,p,u,[{'op':'link.add','key':'D000002','data':{'target_key':'D000001','type':'depends_on'}}])
    assert native(s,p,u)==old
    mutate_current(s,p,u,[{'op':'link.unlink','key':'D000001','id':dependency['id']}])
    assert [core(s,p,u,k) for k in ['D000001','D000002']]==before
    assert Artifacts(s).verify('alpha',u,p)['ok']


@pytest.mark.parametrize('patch',[{},[],{'other':None},{'verification':[]},{'verification':{'status':' '}},{'verification':{'status':42}},{'verification':{'status':'OK','extra':1}},{'verification':{'status':'OK','evidence_refs':[' ']}},{'verification':{'status':'OK','responsible_role':' '}}])
def test_evidence_patch_rejects_invalid_without_commit(ledger,patch):
    from pydantic import ValidationError
    s,p,u=seeded(ledger);before=native(s,p,u)
    with pytest.raises((Fault,ValidationError)):mutate_current(s,p,u,[{'op':'decision.set-evidence','key':'D000001','data':{'evidence_state':patch}}])
    assert native(s,p,u)==before


def test_supplemental_permissions_terminal_mixing_and_stale(ledger):
    s,p,u=seeded(ledger);before=native(s,p,u)
    supplement={'op':'reference.add','key':'D000001','data':{'label':'Later','locator':'synthetic'}}
    for caps in [{'read'},{'read','propose'}]:
        with pytest.raises(Fault):mutate_current(s,replace(p,capabilities=frozenset(caps)),u,[supplement])
    assert mutate_current(s,replace(p,capabilities=frozenset({'read','propose'})),u,[supplement],validate_only=True)['validated']
    with pytest.raises(Fault):mutate_current(s,p,u,[supplement,{'op':'decision.reopen','key':'D000001','data':{'impact':'Review'}}],authority_refs=['Synthetic'])
    with pytest.raises(Fault):change(s,p,u,[{'op':'link.unlink','key':'D000002','id':s.children('alpha',u,p,'D000001','links')['data'][0]['id']}],2,{'D000001':1,'D000002':1})
    assert native(s,p,u)==before
    mutate_current(s,p,u,[{'op':'decision.deprecate','key':'D000001','data':{'kind':'obsolete'}}],authority_refs=['Synthetic'])
    for operation in [supplement,{'op':'decision.set-evidence','key':'D000001','data':{'evidence_state':{'acceptance':None}}},{'op':'link.add','key':'D000002','data':{'target_key':'D000001','type':'depends_on'}}]:
        with pytest.raises(Fault):mutate_current(s,p,u,[operation])


def test_new_alias_cannot_mix_supplement_and_lifecycle(ledger):
    s,p,u=ledger
    with pytest.raises(Fault):change(s,p,u,[{'op':'decision.create','client_ref':'new','data':{'title':'New','question':'Q'}},{'op':'decision.close','key':'@new','data':{'answer':'A','rationale':'R'}},{'op':'reference.add','key':'@new','data':{'label':'Source','locator':'synthetic'}}],authority_refs=['Synthetic'])
    assert not s.list_decisions('alpha',u,p)['data']


def test_legacy_sparse_protected_supplement_preserves_origin(ledger):
    from legacy_fixture import request
    from decision_tracker.models import ProjectChange
    s,p,u=ledger
    candidate=Artifacts(s).import_native(p,request(statuses=('locked',)),True)['data']
    s.catalog.mutate(p,ProjectChange(kind='register',project_id='legacy',name='Legacy',candidate_id=candidate['candidate_id'],expected_candidate_digest=candidate['logical_digest'],expected_catalog_revision=1,request_id=uuid4()))
    lu=candidate['ledger_uuid'];before=s.detail('legacy',lu,p,'D000001')['data']
    with s.catalog.project('legacy',lu,p) as (db,_):original=bundle(db)
    req=Change(expected_ledger_uuid=lu,expected_revision=original['ledger_revision'],expected_decision_revisions={'D000001':before['revision']},request_id=uuid4(),reason='Supporting evidence',operations=[{'op':'decision.set-evidence','key':'D000001','data':{'evidence_state':{'implementation':{'status':'Reported later'}}}},{'op':'reference.add','key':'D000001','data':{'label':'Later source','locator':'synthetic:later'}}])
    s.change('legacy',p,req);after=s.detail('legacy',lu,p,'D000001')['data']
    for field in ['question','answer','rationale','authority_refs','locked','baseline','legacy_origin','latest_resolution_approval']:assert before.get(field)==after.get(field)
    with s.catalog.project('legacy',lu,p) as (db,_):current=bundle(db)
    for table in original:
        if table.startswith('legacy_'):assert current[table]==original[table]
    assert Artifacts(s).verify('legacy',lu,p)['ok']


def test_linked_baseline_preserves_actual_receipt_and_rejects_core_patch(ledger,tmp_path):
    from test_planning_links import document,policy,request
    from decision_tracker.approval_api import upgrade,Upgrade
    s,p,u=seeded(ledger);upgrade(Artifacts(s),'alpha',u,p,Upgrade(expected_revision=2,request_id=uuid4()))
    root=tmp_path/'planning';root.mkdir();path=document(root/'plan.json');policy(s,p,u,[str(root)])
    s.change('alpha',p,request(s,p,u,path));mutate_current(s,p,u,[{'op':'decision.lock','key':'D000001','data':{'baseline':'Linked'}}],authority_refs=['Synthetic'])
    before=core(s,p,u,'D000001');assert before['planning_link']['linked']
    mutate_current(s,p,u,[{'op':'reference.add','key':'D000001','data':{'label':'Later','locator':'synthetic'}},{'op':'decision.set-evidence','key':'D000001','data':{'evidence_state':{'verification':{'status':'Verified'}}}}])
    assert core(s,p,u,'D000001')==before
    with pytest.raises(Fault):mutate_current(s,p,u,[{'op':'decision.set-evidence','key':'D000001','data':{'evidence_state':{'verification':None},'answer':'Injected'}}])
    with pytest.raises(Fault):mutate_current(s,p,u,[{'op':'decision.amend','key':'D000001','client_ref':'amended','data':{'question':'New question','impact':'Changed requirement','baseline_disposition':'continue'}},{'op':'reference.add','key':'@amended','data':{'label':'Source','locator':'synthetic'}}],authority_refs=['Synthetic'])
    assert core(s,p,u,'D000001')==before
    assert Artifacts(s).verify('alpha',u,p)['ok']
