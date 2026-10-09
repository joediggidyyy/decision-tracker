import json
from uuid import uuid4
from concurrent.futures import ThreadPoolExecutor
from decision_tracker.saved_decisions import SavedDecisions, SavedChange, Bundle, Selection, Staged, batches
from decision_tracker.models import Change
from decision_tracker.errors import Fault
from decision_tracker.cli import parser, execute
from decision_tracker import store


def content(title='Local launch', answer='Launch locally'):
    return {'title': title, 'question': 'How should the application launch?', 'answer': answer, 'rationale': 'Operator requires predictable local behavior.'}


def save(saved, principal, action='save', **fields):
    revision=saved.listing(principal)['revision']
    return saved.change(principal,SavedChange(expected_revision=revision,request_id=uuid4(),reason='Synthetic saved decision test',action=action,**fields))


def test_blank_tags_and_snapshot_independence(ledger):
    service,p,u=ledger;saved=SavedDecisions(service.root)
    assert saved.listing(p)['data']==[] and saved.listing(p)['groups']==[]
    id=save(saved,p,content=content())['data']['id']
    g=save(saved,p,action='group-save',name='Websites')['data']['id']
    h=save(saved,p,action='group-save',name='Desktop')['data']['id']
    save(saved,p,id=id,group_ids=[g,h])
    stage=saved.select(p,Selection(expected_revision=4,decision_ids=[id],group_ids=[g,h]))
    assert len(stage['data'])==1 and set(stage['data'][0])=={'id','content'}
    snapshot=Staged(decisions=[stage['data'][0]['content']])
    save(saved,p,id=id,content=content(answer='Launch differently'),group_ids=[])
    result=service.change('alpha',p,Change(expected_ledger_uuid=u,expected_revision=0,request_id=uuid4(),reason='Inject snapshot',operations=batches(snapshot)[0]))
    assert result['aliases']['saved-0']=='D000001'
    detail=service.detail('alpha',u,p,'D000001')['data']
    assert detail['answer']=='Launch locally' and detail['status']=='open'
    assert not any(k in detail for k in ('group_ids','saved_id','source_id'))
    assert saved.get(p,id)['data']['content']['answer']=='Launch differently'
    save(saved,p,action='group-delete',id=g)
    assert service.detail('alpha',u,p,'D000001')['data']['answer']=='Launch locally'


def test_repeat_contradictory_creation_children_and_replay(ledger):
    service,p,u=ledger
    item=content();item.update(options=[{'title':'Local','description':'Suggested local start'}],references=[{'label':'Instructions','locator':'https://example.test/launch'}])
    ops=batches(Staged(decisions=[item,content(answer='Never launch locally')]))[0]
    req=Change(expected_ledger_uuid=u,expected_revision=0,request_id=uuid4(),reason='Operator-selected contradictory content',operations=ops)
    first=service.change('alpha',p,req)
    assert service.change('alpha',p,req)=={**first,'replayed':True}
    second=service.change('alpha',p,req.model_copy(update={'request_id':uuid4(),'expected_revision':1}))
    assert list(second['aliases'].values())==['D000003','D000004']
    detail=service.detail('alpha',u,p,'D000001')['data']
    assert service.children('alpha',u,p,'D000001','alternatives')['data'][0]['disposition']=='unselected'
    assert service.children('alpha',u,p,'D000001','references')['data'][0]['authenticity']=='unknown'
    assert detail['evidence_state']=={'implementation':None,'verification':None,'acceptance':None}


def test_batches_resume_and_concurrent_numbering(ledger):
    service,p,u=ledger
    prepared=batches(Staged(decisions=[content(str(i)) for i in range(30)]))
    assert [len(x) for x in prepared]==[25,5]
    reqs=[Change(expected_ledger_uuid=u,expected_revision=i,request_id=uuid4(),reason='Multi-batch injection',operations=ops) for i,ops in enumerate(prepared)]
    service.change('alpha',p,reqs[0])
    assert service.change('alpha',p,reqs[0])['replayed']
    assert list(service.change('alpha',p,reqs[1])['aliases'].values())[-1]=='D000030'
    def attempt():
        try:return service.change('alpha',p,Change(expected_ledger_uuid=u,expected_revision=2,request_id=uuid4(),reason='Concurrent publication',operations=batches(Staged(decisions=[content()]))[0]))
        except Fault as exc:return exc.code
    with ThreadPoolExecutor(2) as pool:results=list(pool.map(lambda _:attempt(),range(2)))
    assert sum(isinstance(x,dict) for x in results)==1 and 'STALE_REVISION' in results
    assert len(service.list_decisions('alpha',u,p,limit=50)['data'])==31


def test_saved_revisions_replay_and_portable_import(ledger,tmp_path):
    service,p,u=ledger;saved=SavedDecisions(service.root)
    req=SavedChange(expected_revision=0,request_id=uuid4(),reason='Create reusable',action='save',content=content())
    first=saved.change(p,req);assert saved.change(p,req)==first
    try:saved.change(p,req.model_copy(update={'reason':'Changed request'}))
    except Fault as exc:assert exc.code=='REQUEST_ID_REUSED'
    else:assert False
    try:saved.change(p,req.model_copy(update={'request_id':uuid4()}))
    except Fault as exc:assert exc.code=='REVISION_CONFLICT'
    else:assert False
    with store.connect(saved.path) as db:bundle=saved.bundle(db)
    other=SavedDecisions(tmp_path/'fresh')
    save(other,p,action='import',bundle=bundle)
    assert other.get(p,first['data']['id'])['data']==saved.get(p,first['data']['id'])['data']
    save(other,p,action='import',bundle=bundle)
    conflict=bundle.model_copy(deep=True);conflict.decisions[0].content.answer='Different'
    try:save(other,p,action='import',bundle=conflict)
    except Fault as exc:assert exc.code=='REVISION_CONFLICT'
    else:assert False
    assert other.get(p,first['data']['id'])['data']['content']['answer']=='Launch locally'


def test_api_permissions_export_backup_and_validation(client):
    url='/api/v1/saved-decisions'
    assert client.get(url).json()['revision']==0
    body={'expected_revision':0,'request_id':str(uuid4()),'reason':'Save reusable','action':'save','content':content()}
    assert client.post(url+'/changes',json=body).status_code==200
    id=client.get(url).json()['data'][0]['id']
    assert client.get(url+'/'+id).json()['data']['content']['title']=='Local launch'
    stale=client.post(url+'/stage',json={'expected_revision':0,'decision_ids':[id]})
    assert stale.status_code==409
    from decision_tracker.cli import exit_code
    assert exit_code(stale.json())==3
    stage=client.post(url+'/stage',json={'expected_revision':1,'decision_ids':[id]}).json()
    assert len(stage['data'])==1
    export=client.post(url+'/export',json={}).json()
    assert export['format']=='decision-tracker.saved-decisions/v1'
    assert client.post(url+'/import-check',json=export).json()['data']['validated_only']
    assert client.post(url+'/prepare',json={'decisions':[stage['data'][0]['content']], 'new_project':True, 'approval':{'mode':'reported','approver':'Synthetic operator','precision':'unknown','sources':['Synthetic approval']}}).json()['data']['batches'][0][0]['op']=='decision.create'
    backup=client.post(url+'/backup',json={});assert backup.status_code==200,backup.text
    artifact=backup.json()['data']['artifact_id']
    checked=client.post(url+'/backup-check',json={'artifact_id':artifact});assert checked.status_code==200,checked.text
    assert checked.json()['data']['history_entries']==1
    assert client.get(url+'/backups/'+artifact+'/content').content.startswith(b'SQLite format 3')
    bad={**export,'format':'unknown'}
    assert client.post(url+'/import-check',json=bad).status_code==422
    client.headers['Authorization']='Bearer '+client.readonly
    assert client.get(url).status_code==200
    assert client.post(url+'/changes',json={**body,'expected_revision':1,'request_id':str(uuid4())}).status_code==403
    assert client.post(url+'/backup',json={}).status_code==403


def test_cli_staging_preparation_publication_parity(client,monkeypatch,tmp_path):
    monkeypatch.setenv('SAVED_TEST_TOKEN',client.token)
    from decision_tracker.cli import Client
    lost={'close':False}
    def request(self,method,path,data=None,uuid=None,download=None):
        response=client.request(method,path,json=data,headers={'X-Ledger-UUID':uuid} if uuid else {})
        if response.status_code==200 and lost['close'] and data and data.get('operations',[{}])[0].get('op')=='decision.close':
            lost['close']=False
            return {'ok':False,'error':{'code':'UNAVAILABLE','message':'Synthetic lost close response'}}
        if download and response.status_code==200:
            with open(download,'xb') as file:file.write(response.content)
            return {'ok':True,'data':{'saved':download}}
        return response.json()
    monkeypatch.setattr(Client,'request',request)
    def run(*args):return execute(parser().parse_args([*args,'--token-env','SAVED_TEST_TOKEN','--json']))
    created=run('data','saved-create','--title','CLI decision','--question','How?','--answer','Use the selected behavior','--rationale','Synthetic reason','--expected-revision','0','--request-id',str(uuid4()),'--reason','User selection')
    assert created['ok']
    stage_file=tmp_path/'stage.json'
    stage=run('data','saved-stage','--saved-id',created['data']['id'],'--expected-revision','1','--output',str(stage_file))
    assert len(stage['data'])==1
    payload=json.loads(stage_file.read_text());payload['approval']={'mode':'reported','approver':'Synthetic operator','precision':'unknown','sources':['Synthetic CLI approval']};stage_file.write_text(json.dumps(payload))
    project=client.post('/api/v1/projects',json={'project_id':'cli','name':'CLI','expected_catalog_revision':0,'request_id':str(uuid4())}).json()['data']
    prepared=tmp_path/'requests.json'
    run('data','saved-prepare','--input',str(stage_file),'--output',str(prepared),'--project','cli','--ledger-uuid',project['ledger_uuid'],'--expected-revision','0','--request-id',str(uuid4()),'--reason','Publish reusable')
    lost['close']=True
    failed=run('data','saved-publish','--input',str(prepared),'--project','cli','--ledger-uuid',project['ledger_uuid'])
    assert not failed['ok'] and failed['publication_phase']=='close'
    retained=json.loads(prepared.read_text())['data']
    assert retained['phase']=='close' and retained['index']==0 and len(retained['targets'])==1
    for _ in range(2):
        result=run('data','saved-publish','--input',str(prepared),'--project','cli','--ledger-uuid',project['ledger_uuid'])
        assert result['ok'],result
    records=client.get('/api/v1/projects/cli/decisions',headers={'X-Ledger-UUID':project['ledger_uuid']}).json()['data']
    assert len(records)==1 and records[0]['status']=='closed' and records[0]['locked']
    assert result['data']['closed_protected']==1
    assert any(receipt.get('replayed') for receipt in result['data']['receipts'])


def test_damaged_admin_store_does_not_block_projects(tmp_path,principal):
    from fastapi.testclient import TestClient
    from decision_tracker.api import create_app
    from decision_tracker.config import Config,PrincipalConfig
    root=tmp_path/'data';root.mkdir();path=root/'saved-decisions.sqlite';path.write_bytes(b'Retained corrupt saved state')
    original=path.read_bytes()
    cfg=Config(data_root=str(root),local_storage_confirmed=True,principals=[PrincipalConfig(id='fixture',token_env='TEST_SAVED_ACCESS',projects=['*'],capabilities=['read','write','registry'])])
    with TestClient(create_app(cfg,{'TEST_SAVED_ACCESS':'synthetic-test-access-value-00000000000'}),base_url='http://127.0.0.1:8765') as c:
        c.headers['Authorization']='Bearer synthetic-test-access-value-00000000000'
        result=c.get('/api/v1/saved-decisions');assert result.status_code==503
        assert 'restore a checked' in result.json()['error']['recovery']
        assert c.get('/api/v1/projects').status_code==200
        assert c.post('/api/v1/projects',json={'project_id':'unaffected','name':'Unaffected','expected_catalog_revision':0,'request_id':str(uuid4())}).status_code==200
    assert path.read_bytes()==original


def test_saved_structural_refusals_retain_state(client):
    url='/api/v1/saved-decisions'
    body={'expected_revision':0,'request_id':str(uuid4()),'reason':'Synthetic validation','action':'save','content':content(),'group_ids':[str(uuid4())]}
    assert client.post(url+'/changes',json=body).status_code==422
    assert client.get(url).json()['revision']==0
    unknown={**content(),'approval':{'mode':'authenticated_now'}}
    assert client.post(url+'/changes',json={**body,'group_ids':[],'content':unknown}).status_code==422
    assert client.get(url).json()['data']==[]
    duplicate='{"format":"decision-tracker.saved-decisions/v1","decisions":[],"groups":[],"groups":[]}'
    assert client.post(url+'/import-check',content=duplicate,headers={'Content-Type':'application/json'}).status_code==422


def test_closed_publication_phases_replay_and_stale_protection(ledger):
    import pytest
    from decision_tracker.saved_decisions import prepare_publication
    service,p,u=ledger
    staged=Staged(decisions=[content(str(i)) for i in range(30)],project_id='alpha',ledger_uuid=u,
                  approval={'mode':'reported','approver':'Synthetic operator','precision':'unknown','sources':['Synthetic scoped approval']})
    targets={};revision=0
    for phase in ('create','close'):
        prepared=prepare_publication(service,p,staged.model_copy(update={'phase':phase,'targets':targets if phase!='create' else {},'expected_revision':revision}))['data']
        assert len(prepared['requests'])==2
        for value in prepared['requests']:
            request=Change.model_validate(value);receipt=service.change('alpha',p,request)
            assert service.change('alpha',p,request)['replayed']
            targets.update({row['key']:row['revision'] for row in receipt['data']});revision=receipt['revision']
    protect=staged.model_copy(update={'phase':'protect','targets':targets,'expected_revision':revision})
    prepared=prepare_publication(service,p,protect)['data']
    assert len(prepared['requests'])==2 and len(prepared['requests'][0]['authority_refs'])==25
    with pytest.raises(Fault) as error:
        prepare_publication(service,p,protect.model_copy(update={'targets':{**targets,'D000001':1}}))
    assert error.value.code=='STALE_REVISION'
    for value in prepared['requests']:
        request=Change.model_validate(value);service.change('alpha',p,request)
        assert service.change('alpha',p,request)['replayed']
    rows=service.list_decisions('alpha',u,p,limit=50)['data']
    assert len(rows)==30 and all(row['status']=='closed' and row['locked'] for row in rows)
    obj=service.detail('alpha',u,p,'D000001')['data']
    assert obj['baseline']=='publication-'+str(staged.publication_id)
    assert obj['latest_resolution_approval']['mode']=='reported'
    assert obj['planning_link']['linked'] is False


def test_publication_preflight_retains_projects_and_requires_real_approval(client):
    url='/api/v1/saved-decisions/prepare'
    body={'decisions':[content()], 'new_project':True, 'approval':{'mode':'authenticated_now'}}
    assert client.post(url,json=body).status_code==403

    body['approval']={'mode':'reported','approver':'Synthetic operator','precision':'unknown','sources':['Synthetic approval']}
    assert client.post(url,json=body).status_code==200
    body['decisions'][0]['rationale']=None
    assert client.post(url,json=body).status_code==422
    assert client.get('/api/v1/projects').json()['data']==[]
    client.headers['Authorization']='Bearer '+client.readonly
    body['decisions'][0]['rationale']='Synthetic reason'
    assert client.post(url,json=body).status_code==403


def test_group_metadata_pages_remain_bounded_and_complete(ledger):
    service,p,u=ledger;saved=SavedDecisions(service.root)
    tags=[{'id':str(uuid4()),'name':str(i)} for i in range(500)]
    ids=[str(uuid4()) for _ in range(7)]
    value=Bundle(groups=tags,decisions=[{'id':id,'content':content(id),'group_ids':[g['id'] for g in tags]} for id in ids])
    save(saved,p,action='import',bundle=value)
    offset=0;items=[];groups=[]
    while offset is not None:
        page=saved.listing(p,offset=offset,limit=50,expected_revision=1)
        assert len(store.encode(page).encode())<=60000
        items.extend(page['data']);groups.extend(page['groups']);offset=page['next_offset']
    assert {x['id'] for x in items}==set(ids) and len(items)==7
    assert {x['id'] for x in groups}=={x['id'] for x in tags} and len(groups)==500
    assert all(len(x['group_ids'])==500 for x in items)
