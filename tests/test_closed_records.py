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
    with pytest.raises(Fault):change(s,p,u,[{'op':'link.add','key':'D000002','data':{'target_key':'D000001','type':'depends_on'}}],2,{'D000001':2,'D000002':1})
    assert native(s,p,u)==before
    change(s,p,u,[{'op':'decision.lock','key':'D000001','data':{'baseline':'Release'}}],2,{'D000001':2},authority_refs=['Synthetic'])
    change(s,p,u,[{'op':'decision.amend','key':'D000001','data':{'question':'What changes?','impact':'New requirement','baseline_disposition':'continue'}}],3,{'D000001':3},authority_refs=['Synthetic'])
    assert s.detail('alpha',u,p,'D000003')['data']['status']=='open'
    change(s,p,u,[{'op':'decision.deprecate','key':'D000002','data':{'kind':'superseded','replacement_key':'D000001'}}],4,{'D000002':1,'D000001':4},authority_refs=['Synthetic'])
    change(s,p,u,[{'op':'decision.deprecate','key':'D000001','data':{'kind':'obsolete'}}],5,{'D000001':5},authority_refs=['Synthetic'])
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


def test_revision_precedence_and_in_batch_closure_rollback(ledger):
    s,p,u=seeded(ledger);before=native(s,p,u)
    with pytest.raises(Fault) as stale:change(s,p,u,[{'op':'decision.edit','key':'D000001','data':{'title':'Old draft'}}],2,{'D000001':1})
    assert stale.value.code=='STALE_REVISION'
    with pytest.raises(Fault):change(s,p,u,[{'op':'decision.close','key':'D000002','data':{'answer':'B','rationale':'Reviewed'}},{'op':'decision.edit','key':'D000002','data':{'title':'After closure'}}],2,{'D000002':1},authority_refs=['Synthetic'])
    assert native(s,p,u)==before
