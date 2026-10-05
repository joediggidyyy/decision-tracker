from uuid import uuid4
import json
import pytest
from decision_tracker import store
from decision_tracker.artifacts import Artifacts, bundle
from decision_tracker.candidates import listing, prepare, paths
from decision_tracker.models import ProjectChange
from decision_tracker.errors import Fault
from decision_tracker.auth import Principal


def imported(service, principal, tmp_path, promote=True):
    source=tmp_path/(str(uuid4())+'.sqlite');store.initialize(source,str(uuid4()))
    with store.connect(source) as db:value=bundle(db)
    return Artifacts(service).import_native(principal,value,promote)['data']


def test_preparation_inventory_and_registration(ledger,tmp_path):
    s,p,u=ledger
    validated=imported(s,p,tmp_path,False)
    assert listing(s,p)['data']==[]
    row=prepare(s.catalog,p,validated['candidate_id'])['data']
    assert prepare(s.catalog,p,validated['candidate_id'])['data']==row
    assert listing(s,p)['data']==[row]
    request=ProjectChange(kind='register',project_id='imported',name='Imported',candidate_id=row['candidate_id'],expected_candidate_digest=row['logical_digest'],expected_catalog_revision=1,request_id=uuid4())
    result=s.catalog.mutate(p,request)
    assert result['data']['ledger_uuid']==row['ledger_uuid']
    assert s.catalog.mutate(p,request)['replayed']
    assert listing(s,p)['data']==[]
    with pytest.raises(Fault,match='already registered'):prepare(s.catalog,p,row['candidate_id'])


def test_changed_candidate_and_invalid_receipt(ledger,tmp_path):
    s,p,u=ledger;row=imported(s,p,tmp_path);key=row['candidate_id'];path=paths(s.catalog,key)[2]
    original=listing(s,p)['data'][0]
    with store.connect(path,True) as db:db.execute("UPDATE meta SET created_at='2026-01-01T00:00:00Z'")
    assert listing(s,p)['data']==[]
    updated=prepare(s.catalog,p,key)['data'];assert updated['logical_digest']!=original['logical_digest']
    request=ProjectChange(kind='register',project_id='new',name='New',candidate_id=key,expected_candidate_digest=original['logical_digest'],expected_catalog_revision=1,request_id=uuid4())
    with pytest.raises(Fault,match='changed'):s.catalog.mutate(p,request)
    paths(s.catalog,key)[3].write_text('{}')
    assert listing(s,p)['data']==[]
    assert prepare(s.catalog,p,key)['data']['logical_digest']==updated['logical_digest']


def test_candidate_pagination_permissions_and_containment(ledger,tmp_path):
    s,p,u=ledger
    for _ in range(3):imported(s,p,tmp_path)
    first=listing(s,p,limit=1);second=listing(s,p,first['next_cursor'],1)
    assert first['data'][0]['candidate_id']!=second['data'][0]['candidate_id']
    imported(s,p,tmp_path)
    with pytest.raises(Fault,match='result set changed'):listing(s,p,first['next_cursor'],1)
    for caps in ({'maintain'},{'registry'},{'read'}):
        restricted=Principal('limited',frozenset({'*'}),frozenset(caps))
        with pytest.raises(Fault):listing(s,restricted)
        with pytest.raises(Fault):prepare(s.catalog,restricted,first['data'][0]['candidate_id'])
    with pytest.raises(Fault):prepare(s.catalog,p,'../../catalog')
    assert not any('path' in k for k in first['data'][0])


def test_candidate_routes_and_input_contract(client,tmp_path):
    s=client.app.state.service
    from conftest import Principal
    p=Principal('fixture',frozenset({'*'}),frozenset({'read','maintain','registry'}))
    row=imported(s,p,tmp_path,False)
    assert client.get('/api/v1/candidates').json()['data']==[]
    r=client.post('/api/v1/candidates/'+row['candidate_id']+'/prepare',json={})
    assert r.status_code==200,r.text
    candidate=r.json()['data']
    body={'kind':'register','project_id':'copy','name':'Copy','candidate_id':row['candidate_id'],'expected_candidate_digest':candidate['logical_digest'],'expected_catalog_revision':0,'request_id':str(uuid4())}
    bad=client.post('/api/v1/projects',json={**body,'relative_path':'something.sqlite'})
    assert bad.status_code==422
    result=client.post('/api/v1/projects',json=body);assert result.status_code==200,result.text
    assert client.get('/api/v1/candidates').json()['data']==[]
