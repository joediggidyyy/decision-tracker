"""Lossless import, existing lifecycle, retry, containment and inactive recovery."""
from copy import deepcopy
from dataclasses import replace
import base64,hashlib,json,sqlite3
from uuid import uuid4
import pytest
from pydantic import ValidationError
from decision_tracker import legacy,store,cli,planning_links
from decision_tracker.legacy_candidates import artifact,download
from decision_tracker.artifacts import Artifacts,bundle,validate_history
from decision_tracker.models import Change,ProjectChange,Decision
from decision_tracker.service import Service
from decision_tracker.errors import Fault
from legacy_fixture import request

def prepared(ledger,value=None):
    s,p,u=ledger;value=value or request()
    result=Artifacts(s).import_native(p,value,True)['data']
    return s,p,value,result
def registered(ledger,value=None):
    s,p,value,result=prepared(ledger,value)
    s.catalog.mutate(p,ProjectChange(kind='register',project_id='legacy-test',name='Synthetic legacy',candidate_id=result['candidate_id'],expected_candidate_digest=result['logical_digest'],expected_catalog_revision=1,request_id=uuid4()))
    return s,p,value,result
def mutate(s,p,u,key,op,data=None,**extra):
    d=s.detail('legacy-test',u,p,key)
    expected=extra.pop('expected_decision_revisions',{key:d['data']['revision']})
    return s.change('legacy-test',p,Change(expected_ledger_uuid=u,expected_revision=d['revision'],expected_decision_revisions=expected,request_id=uuid4(),reason='Synthetic lifecycle proof',authority_refs=['Synthetic scope'],operations=[{'op':op,'key':key,'data':data or {}}],**extra))

def test_e1_tokens_types_order_presence_unicode():
    from decision_tracker import legacy_encoding
    assert legacy.e1 is legacy_encoding.e1 and legacy.parse is legacy_encoding.parse
    assert legacy.Number is legacy_encoding.Number
    raw='{"z":[2,1],"num":1.2300,"exp":1E+02,"zero":-0,"null":null,"empty":"","emoji":"🧭"}'
    v=legacy.parse(raw);encoded=legacy.e1(v)
    assert '1.2300' in encoded and '1E+02' in encoded and '-0' in encoded
    assert legacy.literal_type(v['num'])=='number' and legacy.literal_type(v['zero'])=='integer'
    assert v['null'] is None and v['empty']=='' and 'absent' not in v
    assert legacy.e1(v['z'])=='[2,1]' and legacy.pointer(v,'/emoji')=='🧭'
    for bad in ('{"a":1,"a":2}','NaN','1e','"\\ud800"'):
        with pytest.raises(Fault):legacy.parse(bad)
    with pytest.raises(Fault):legacy.e1(1.2)
    with pytest.raises(Fault):legacy.pointer(v,'/absent')

def test_import_initial_history_fidelity_roundtrip_and_scope(ledger,tmp_path):
    s,p,value,r=registered(ledger);u=r['ledger_uuid'];a=Artifacts(s)
    with s.catalog.project('legacy-test',u,p) as (db,_):
        assert store.metadata(db)['ledger_revision']==0
        assert not db.execute('SELECT 1 FROM transactions').fetchone()
        assert not db.execute('SELECT 1 FROM approval_events').fetchone()
        assert validate_history(db)['integrity']=='ok'
        native=bundle(db)
        for table in legacy.TABLES:
            with pytest.raises(sqlite3.IntegrityError):db.execute('DELETE FROM '+table)
    d=s.detail('legacy-test',u,p,'D000001')['data']
    assert d['status']=='closed' and d['question'] is None and d['rationale'] is None and d['latest_resolution_approval'] is None
    assert d['planning_link']['resolution_id'].startswith('import:') and not d['planning_link']['recorded']
    assert s.detail('legacy-test',u,p,'D000001',0)['data']['legacy_origin']['source_id']=='SOURCE-1'
    other=Service(tmp_path/'other');copy=Artifacts(other).import_native(p,native,True)['data']
    assert copy['logical_sha256']==r['logical_digest']
    assert native['format']=='decision-tracker/v4' and len(native['legacy_native_seeds'])==4
    assert a.verify('alpha',ledger[2],p)['revision']==0  # Original active ledger is untouched.

def test_project_pages_chunks_relations_asof_and_signed_cursor(ledger):
    s,p,value,r=registered(ledger,request(extra_members=205));u=r['ledger_uuid'];reads=s.legacy_reads
    allrows=[];cursor=None
    while True:
        page=reads.read('legacy-test',u,p,'members',cursor=cursor,limit=17);allrows+=page['data']['members'];cursor=page['next_cursor']
        assert len(store.encode(page).encode())<65536
        if page['complete']:break
    assert len(allrows)==209 and sum(m['subject_kind']=='disposition' for m in allrows)==205
    associated=reads.read('legacy-test',u,p,'members',key='D000001')['data']['members'];assert len(associated)==1
    member=associated[0];ph=member['payload_sha256'];offset=0;raw=b''
    while True:
        chunk=reads.read('legacy-test',u,p,'payload',key='D000001',payload=ph,offset=offset,limit=7)
        raw+=base64.b64decode(chunk['data']['chunk_base64']);offset=chunk['data']['next_offset']
        if offset is None:break
    assert hashlib.sha256(raw).hexdigest()==ph and b'1.2300' in raw and '🧭' in raw.decode()
    with pytest.raises(Fault):reads.read('legacy-test',u,p,'payload',key='D000002',payload=ph)
    asof=reads.read('legacy-test',u,p,'as-of',key='D000001',version_id=member['version_id'])['data'];assert asof['presence']=='present' and asof['absence_ids']
    assert reads.read('legacy-test',u,p,'relations')['data']['relations'][0]['target_endpoint']['kind']=='evidence'
    first=reads.read('legacy-test',u,p,'members',limit=1)
    with pytest.raises(Fault):reads.read('legacy-test',u,p,'members',cursor=first['next_cursor']+'x',limit=1)
    mutate(s,p,u,'D000002','decision.set-work',{'work_tag':'under-investigation'})
    with pytest.raises(Fault,match='changed'):reads.read('legacy-test',u,p,'members',cursor=first['next_cursor'],limit=1)
    limited=replace(p,projects=frozenset({'alpha'}))
    with pytest.raises(Fault):reads.read('legacy-test',u,limited,'members')

def test_c3_reference_work_reopen_close_protect_amend_deprecate_link(ledger,tmp_path):
    s,p,v,r=registered(ledger);u=r['ledger_uuid']
    for key in ('D000001','D000003','D000004'):
        with pytest.raises(Fault):mutate(s,p,u,key,'reference.add',{'label':'Source','locator':'synthetic:source'})
    mutate(s,p,u,'D000002','reference.add',{'label':'Source','locator':'synthetic:source'})
    with pytest.raises(Fault):mutate(s,p,u,'D000002','decision.challenge')
    mutate(s,p,u,'D000002','decision.set-work',{'work_tag':'under-investigation'})
    mutate(s,p,u,'D000002','decision.challenge');mutate(s,p,u,'D000002','decision.resolve-challenge')
    mutate(s,p,u,'D000002','decision.defer',{'resume_trigger':'Review'});mutate(s,p,u,'D000002','decision.resume')
    mutate(s,p,u,'D000002','option.add',{'title':'Native option'})
    mutate(s,p,u,'D000001','decision.reopen',{'impact':'Reconsider'})
    with pytest.raises(ValidationError):mutate(s,p,u,'D000001','decision.close',{'answer':'A','rationale':'R'})
    with pytest.raises(ValidationError):mutate(s,p,u,'D000001','decision.edit',{'question':None})
    mutate(s,p,u,'D000001','decision.edit',{'question':'New native question'})
    mutate(s,p,u,'D000001','decision.close',{'answer':'A','rationale':'R'})
    assert s.detail('legacy-test',u,p,'D000001')['data']['latest_resolution_approval']
    mutate(s,p,u,'D000001','decision.lock',{'baseline':'Native protected baseline'})
    with pytest.raises(Fault):mutate(s,p,u,'D000001','decision.reopen',{'impact':'Denied'})
    with pytest.raises(ValidationError):mutate(s,p,u,'D000003','decision.amend',{'impact':'Review','baseline_disposition':'continue','question':''})
    mutate(s,p,u,'D000003','decision.amend',{'impact':'Review','baseline_disposition':'continue','question':'Native child','title':'Child'})
    child=s.detail('legacy-test',u,p,'D000005')['data'];assert child['question']=='Native child' and 'legacy_origin' not in child
    mutate(s,p,u,'D000002','decision.deprecate',{'kind':'obsolete'})
    assert s.detail('legacy-test',u,p,'D000002')['data']['deprecation_kind']=='obsolete'
    with pytest.raises(Fault):mutate(s,p,u,'D000004','decision.reopen',{'impact':'Terminal'})
    with pytest.raises(ValidationError):Decision(key='D000006',title='Forged',question=None)
    with pytest.raises(Fault):mutate(s,p,u,'D000005','decision.edit',{'legacy_import_id':'forged'})
    assert Artifacts(s).verify('legacy-test',u,p)['ok']

def test_imported_closed_link_receipt_replay_and_protect_sparse(ledger,tmp_path):
    s,p,v,r=registered(ledger);u=r['ledger_uuid']
    root=tmp_path/'planning';root.mkdir();doc=root/'plan.json'
    from test_planning_links import document
    document(doc)
    planning_links.set_policy(s,'legacy-test',u,replace(p,auth_method='os_owner'),planning_links.PolicyChange(expected_policy_revision=0,request_id=uuid4(),reason='Synthetic planning custody',planning_roots=[str(root)]))
    data={'planning_document':str(doc),'planning_section':'execution','expected_policy_revision':1}
    d=s.detail('legacy-test',u,p,'D000001')
    req=Change(expected_ledger_uuid=u,expected_revision=d['revision'],expected_decision_revisions={'D000001':d['data']['revision']},request_id=uuid4(),reason='Synthetic original alias receipt',operations=[{'op':'decision.apply','key':'D000001','data':data}])
    result=s.change('legacy-test',p,req)
    assert s.change('legacy-test',p,req)['replayed']
    with pytest.raises(Fault) as altered:s.change('legacy-test',p,req.model_copy(update={'reason':'Changed intent'}))
    assert altered.value.code=='REQUEST_ID_REUSED'
    assert s.detail('legacy-test',u,p,'D000001')['data']['planning_link']['linked']
    assert result['planning_link_receipts'][0]['approval_event_id'] is None
    mutate(s,p,u,'D000001','decision.lock',{'baseline':'Import provenance baseline'})
    assert s.detail('legacy-test',u,p,'D000001')['data']['rationale'] is None
    assert Artifacts(s).verify('legacy-test',u,p)['ok']

def test_imported_native_guards_approval_graph_and_strict_create(ledger):
    s,p,_,r=registered(ledger);u=r['ledger_uuid']
    with s.catalog.project('legacy-test',u,p) as (db,_):before={table:bundle(db)[table] for table in legacy.TABLES}
    with pytest.raises(Fault):mutate(s,replace(p,capabilities=p.capabilities-{'decide'}),u,'D000001','decision.reopen',{'impact':'Unauthorized'})
    d=s.detail('legacy-test',u,p,'D000001')
    batch=Change(expected_ledger_uuid=u,expected_revision=d['revision'],expected_decision_revisions={'D000001':1},request_id=uuid4(),reason='Synthetic separate-reopen guard',authority_refs=['Synthetic authority'],operations=[{'op':'decision.reopen','key':'D000001','data':{'impact':'Review'}},{'op':'decision.edit','key':'D000001','data':{'question':'Bypass'}}])
    with pytest.raises(Fault):s.change('legacy-test',p,batch)
    with pytest.raises(Fault):mutate(s,p,u,'D000001','decision.lock',{'baseline':''})
    with pytest.raises(Fault):mutate(s,p,u,'D000002','decision.lock',{'baseline':'Open guard'})
    for target in (None,'D000002','D000004'):
        with pytest.raises(Fault):mutate(s,p,u,'D000002','decision.deprecate',{'kind':'superseded','replacement_key':target})
    with pytest.raises(Fault):mutate(s,p,u,'D000001','decision.edit-resolution',{'answer':'Withdrawn'})
    meta=s.detail('legacy-test',u,p,'D000002')
    def create(data):return s.change('legacy-test',p,Change(expected_ledger_uuid=u,expected_revision=meta['revision'],expected_decision_revisions={},request_id=uuid4(),reason='Synthetic ordinary Create',operations=[{'op':'decision.create','data':data}]))
    with pytest.raises(ValidationError):create({'title':'Sparse native','question':None})
    with pytest.raises(Fault):create({'title':'Forged origin','question':'Valid?', 'legacy_import_id':'forged'})
    with pytest.raises(Fault):mutate(s,p,u,'D000002','link.add',{'type':'depends_on','target_key':'D000001'},expected_decision_revisions={'D000002':1,'D000001':1})
    mutate(s,p,u,'D000001','decision.reopen',{'impact':'Review'})
    mutate(s,p,u,'D000001','decision.edit',{'question':'Native question'})
    with pytest.raises(Fault):mutate(s,p,u,'D000001','decision.close',{'answer':'A','rationale':'R','approval':{'mode':'authenticated_now'}})
    for data in ({'answer':'','rationale':'R'},{'answer':'A','rationale':''}):
        with pytest.raises(ValidationError):mutate(s,p,u,'D000001','decision.close',data)
    a=s.detail('legacy-test',u,p,'D000001');b=s.detail('legacy-test',u,p,'D000002')
    mutate(s,p,u,'D000001','link.add',{'target_key':'D000002','type':'depends_on'},expected_decision_revisions={'D000001':a['data']['revision'],'D000002':b['data']['revision']})
    a=s.detail('legacy-test',u,p,'D000001');b=s.detail('legacy-test',u,p,'D000002')
    with pytest.raises(Fault):mutate(s,p,u,'D000002','link.add',{'target_key':'D000001','type':'depends_on'},expected_decision_revisions={'D000001':a['data']['revision'],'D000002':b['data']['revision']})
    with s.catalog.project('legacy-test',u,p) as (db,_):assert {table:bundle(db)[table] for table in legacy.TABLES}==before
    assert Artifacts(s).verify('legacy-test',u,p)['ok']

def test_imported_amendment_does_not_waive_child_title_bound(ledger):
    s,p,_,r=registered(ledger,request(statuses=('locked',),source_title='x'*160))
    with pytest.raises(ValidationError):mutate(s,p,r['ledger_uuid'],'D000001','decision.amend',{'question':'Valid native question','impact':'Review','baseline_disposition':'continue'})

def test_import_replay_after_registered_native_work_returns_original_outcome(ledger):
    s,p,v,r=registered(ledger);u=r['ledger_uuid']
    mutate(s,p,u,'D000002','decision.set-work',{'work_tag':'under-investigation'})
    before=s.detail('legacy-test',u,p,'D000002')
    replay=Artifacts(s).import_native(p,v,True)['data']
    assert replay=={**r,'replayed':True} and s.detail('legacy-test',u,p,'D000002')==before
    assert s.catalog.listing(p)['catalog_revision']==2

@pytest.mark.parametrize('stage',['intent','built','published','prepared','outcome'])
def test_durable_interruption_exact_replay_and_no_active_effects(ledger,monkeypatch,stage):
    from decision_tracker import legacy_candidates as lc
    s,p,u=ledger;v=request();objects=Artifacts(s)
    def crash(point):
        if point==stage:raise SystemExit('Synthetic interruption')
    monkeypatch.setattr(lc,'checkpoint',crash)
    with pytest.raises(SystemExit):objects.import_native(p,v,True)
    monkeypatch.setattr(lc,'checkpoint',lambda _:None)
    restarted=Service(s.root);r=Artifacts(restarted).import_native(p,v,True)['data'];again=Artifacts(restarted).import_native(p,v,True)['data']
    assert r['candidate_id']==again['candidate_id'] and again['replayed']
    assert restarted.catalog.listing(p)['catalog_revision']==1 and len(restarted.catalog.listing(p)['data'])==1
    changed=deepcopy(v);changed['source_manifest_sha256']='c'*64
    with pytest.raises(Fault,match='different content'):Artifacts(restarted).import_native(p,changed,True)
    collision={**v,'request_id':str(uuid4())}
    with pytest.raises(Fault):Artifacts(restarted).import_native(p,collision,True)
    with pytest.raises(Fault):Artifacts(restarted).import_native(replace(p,capabilities=frozenset({'read'})),v,True)

def test_inactive_export_backup_restore_tamper_roundtrip(ledger,tmp_path):
    s,p,v,r=prepared(ledger);objects=Artifacts(s);cid=r['candidate_id'];expected=r['logical_digest']
    exported=artifact(objects,p,cid,expected,'export')['data'];path,_=download(objects,p,cid,expected,exported['artifact_id'])
    assert json.loads(path.read_text())['schema_version']==4
    backup=artifact(objects,p,cid,expected,'backup')['data'];restored=artifact(objects,p,cid,expected,'restore-check',backup['artifact_id'])['data']
    assert restored['candidate_id']!=cid and restored['logical_digest']==expected and not restored['activated'] and not restored['registered']
    assert artifact(objects,p,cid,expected,'verify')['data']['integrity']=='ok'
    assert s.catalog.listing(p)['catalog_revision']==1
    with pytest.raises(Fault):artifact(objects,p,cid,'0'*64,'backup')
    path,_=download(objects,p,cid,expected,backup['artifact_id']);path.write_bytes(path.read_bytes()[:100])
    with pytest.raises(Fault,match='hash differs'):artifact(objects,p,cid,expected,'restore-check',backup['artifact_id'])
    assert Artifacts(s).verify('alpha',ledger[2],p)['revision']==0

@pytest.mark.parametrize('kind',['hash','alias','projection','unknown-field','target','ordering'])
def test_malformed_imports_reject_without_publication(ledger,kind):
    s,p,u=ledger;v=request()
    if kind=='hash':v['payloads'][0]['payload_sha256']='0'*64
    if kind=='alias':v['identities'][1]['aliases']=['SOURCE-1']
    if kind=='projection':v['projections'][0]['projection_json']='"invented"'
    if kind=='unknown-field':v['bypass']=True
    if kind=='target':v['target_ledger_uuid']='not-a-uuid'
    if kind=='ordering':v['members'].reverse()
    with pytest.raises(Fault):Artifacts(s).import_native(p,v,True)
    assert not (s.root/'import-journal.sqlite').exists() and not (s.root/'candidates').exists()

def test_validate_only_and_10mib_boundaries(ledger):
    s,p,u=ledger;v=request(statuses=('closed',));objects=Artifacts(s)
    assert objects.import_native(p,v,False)['data']['validated_only']
    assert not (s.root/'import-journal.sqlite').exists() and not (s.root/'candidates').exists()
    large=request(statuses=('closed',),payload_text='x'*(legacy.MAX_BYTES-50000))
    assert len(legacy.e1(large).encode())<legacy.MAX_BYTES
    r=objects.import_native(p,large,True)['data'];assert artifact(objects,p,r['candidate_id'],r['logical_digest'],'export')['ok']
    over=request(statuses=('closed',),payload_text='x'*legacy.MAX_BYTES)
    with pytest.raises(Fault) as exceeded:objects.import_native(p,over,True)
    assert exceeded.value.code=='LIMIT_EXCEEDED' and exceeded.value.status==413

def test_api_schema_envelopes_identity_and_candidate_routes(client):
    v=request(extra_members=2);response=client.post('/api/v1/imports/new',json=v);assert response.status_code==200,response.text;r=response.json()['data']
    body={'kind':'register','project_id':'legacy-test','name':'Legacy','candidate_id':r['candidate_id'],'expected_candidate_digest':r['logical_digest'],'expected_catalog_revision':0,'request_id':str(uuid4())}
    # Inactive maintenance before registration.
    cbody={'expected_candidate_digest':r['logical_digest']}
    assert client.post('/api/v1/candidates/'+r['candidate_id']+'/verify',json=cbody).status_code==200
    assert client.post('/api/v1/projects',json=body).status_code==200
    headers={'X-Ledger-UUID':r['ledger_uuid']};prefix='/api/v1/projects/legacy-test'
    member=client.get(prefix+'/legacy/members',headers=headers).json();legacy.check_shape(member,'member_page_response')
    relation=client.get(prefix+'/legacy/relations',headers=headers).json();legacy.check_shape(relation,'relation_page_response')
    version=member['data']['members'][0]['version_id'];ph=member['data']['members'][0]['payload_sha256']
    legacy.check_shape(client.get(prefix+'/legacy/payloads/'+ph,headers=headers).json(),'chunk_response')
    legacy.check_shape(client.get(prefix+'/decisions/D000001/legacy/as-of?version_id='+version,headers=headers).json(),'as_of_response')
    lookup=client.get(prefix+'/decisions?source_namespace=legacy-test&source_id=OLD-1',headers=headers).json();assert lookup['data']['key']=='D000001'
    assert client.get(prefix+'/legacy/members',headers={'X-Ledger-UUID':str(uuid4())}).status_code==409
    client.headers['Authorization']='Bearer '+client.readonly
    assert client.get(prefix+'/legacy/members',headers=headers).status_code==404

def test_cli_compact_mapping(monkeypatch,capsys):
    monkeypatch.setenv('DT_OPERATOR_TOKEN','synthetic-cli-only');calls=[]
    monkeypatch.setattr(cli.Client,'request',lambda self,method,path,data=None,uuid=None,download=None:calls.append((method,path,data)) or {'ok':True})
    cid=str(uuid4());u=str(uuid4())
    assert cli.main(['data','backup','--candidate-id',cid,'--expected-candidate-digest','a'*64,'--json'])==0
    assert calls[-1][1]=='/api/v1/candidates/'+cid+'/backups';capsys.readouterr()
    assert cli.main(['query','context','--project','legacy-test','--ledger-uuid',u,'--origin','legacy','--relations','--json'])==0
    assert '/legacy/relations?' in calls[-1][1];capsys.readouterr()
    assert cli.main(['decision','get','--project','legacy-test','--ledger-uuid',u,'--source-namespace','legacy-test','--source-id','OLD-1','--json'])==0
    assert 'source_namespace=legacy-test&source_id=OLD-1' in calls[-1][1]

def adapted_request(status,question='',answer='',rationale=''):
    value=request(statuses=('open',))
    member=value['members'][0];source=legacy.parse(value['payloads'][0]['value_json'])
    source.update(status=status,question=question,answer=answer,rationale=rationale,authority_refs='source:planning')
    raw=legacy.e1(source);ph=legacy.digest(source)
    value['payloads']=[{'payload_sha256':ph,'literal_type':'object','value_json':raw,'encoded_bytes':len(raw.encode())}];member['payload_sha256']=ph
    for p in value['projections']:
        field=p['field'];original=source['status'] if field in ('status','locked','work_tag') else source[field]
        projected=legacy.project_value(field,original)
        p.update(projection_kind='exact',known_state='exact_source',selector='/status' if field in ('status','locked','work_tag') else '/'+field,projection_json=legacy.e1(projected),projection_sha256=legacy.digest(projected))
    if 'deferred' in status:
        for field in ('defer_reason','resume_trigger'):
            value['projections'].append({'native_key':'D000001','field':field,'origin_member_id':None,'selector':None,'projection_kind':'none','known_state':'not_projected','projection_json':'null','projection_sha256':legacy.digest(None)})
        value['native_seeds'][0]['projection_fields']=sorted(value['projections'],key=lambda r:r['field'])
    return legacy.canonical_order(value)

@pytest.mark.parametrize('status',['[open] [queued]','[open] [deferred]','[open] [under-investigation]','[closed]'])
def test_reviewed_status_reference_and_sparse_adapters(ledger,status):
    value=adapted_request(status);s,p,_,r=registered(ledger,value);u=r['ledger_uuid']
    obj=s.detail('legacy-test',u,p,'D000001')['data']
    assert obj['status']==('open' if '[open]' in status else 'closed') and obj['question']=='' and obj['authority_refs']==['source:planning']
    if obj['status']=='closed':mutate(s,p,u,'D000001','decision.reopen',{'impact':'Synthetic re-evaluation'})
    mutate(s,p,u,'D000001','reference.add',{'label':'Native evidence','locator':'synthetic:evidence'})
    if obj['work_tag']=='deferred':mutate(s,p,u,'D000001','decision.resume')
    else:mutate(s,p,u,'D000001','decision.set-work',{'work_tag':'under-investigation'})
    with pytest.raises(ValidationError):mutate(s,p,u,'D000001','decision.close',{'answer':'New answer','rationale':'New rationale'})
    with pytest.raises(ValidationError):mutate(s,p,u,'D000001','decision.edit',{'question':''})
    mutate(s,p,u,'D000001','decision.edit',{'question':'New question'})
    mutate(s,p,u,'D000001','decision.close',{'answer':'New answer','rationale':'New rationale'})
    assert Artifacts(s).verify('legacy-test',u,p)['ok']

def test_normative_schema_and_complete_collections(client):
    discovery=client.get('/api/v1/schema');assert discovery.status_code==200 and len(discovery.content)<=65536
    normative=client.get('/api/v1/schema?contract=legacy-import-v1');assert normative.json()==legacy.schema() and len(normative.content)<=65536
    assert client.get('/api/v1/schema?contract=unknown').status_code==404
    v=request();r=client.post('/api/v1/imports/new',json=v).json()['data']
    body={'kind':'register','project_id':'legacy-test','name':'Legacy','candidate_id':r['candidate_id'],'expected_candidate_digest':r['logical_digest'],'expected_catalog_revision':0,'request_id':str(uuid4())}
    assert client.post('/api/v1/projects',json=body).status_code==200
    prefix='/api/v1/projects/legacy-test';headers={'X-Ledger-UUID':r['ledger_uuid']}
    for family in legacy.FAMILIES:
        response=client.get(prefix+'/legacy/records/'+family+'?limit=1',headers=headers)
        assert response.status_code==200,response.text
        legacy.check_shape(response.json(),'record_page_response')
        assert all('value_json' not in row for row in response.json()['data']['rows'])
    with store.connect(client.app.state.service.catalog.root/'candidates'/r['candidate_id']/'ledger.sqlite') as db:
        for name,columns in legacy.schema()['x-native-v4']['columns'].items():
            actual=[{'name':row['name'],'sqlite_type':row['type'],'not_null':bool(row['notnull']),'primary_key_order':row['pk']} for row in db.execute('PRAGMA table_info("'+name+'")')]
            assert actual==columns

@pytest.mark.parametrize('raw',[b'{"namespace":"a","namespace":"b"}',b'{"invalid":"\xff"}',b'{"invalid":"\\ud800"}'])
def test_import_json_preflight_rejects_invalid_encoding(client,raw):
    response=client.post('/api/v1/imports/new',content=raw,headers={'Content-Type':'application/json'})
    assert response.status_code==422 and response.json()['error']['code']=='VALIDATION_ERROR'

def test_target_collision_with_native_inactive_candidate(ledger):
    s,p,u=ledger
    source=s.root/'native-source.sqlite';store.initialize(source,str(uuid4()))
    with store.connect(source) as db:native=bundle(db)
    original=Artifacts(s).import_native(p,native,True)['data'];v=request();v['target_ledger_uuid']=original['ledger_uuid']
    with pytest.raises(Fault) as collision:Artifacts(s).import_native(p,v,True)
    assert collision.value.code=='IMPORT_IDENTITY_COLLISION'
