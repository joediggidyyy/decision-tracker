import copy,json
import pytest
from decision_tracker.artifacts import Artifacts,bundle
from decision_tracker.errors import Fault
from decision_tracker import store
from conftest import change

def seed(ledger):
 s,p,u=ledger
 change(s,p,u,[{"op":"decision.create","data":{"title":"Retention","question":"Preserve history?"}}])
 change(s,p,u,[{"op":"decision.close","key":"D000001","data":{"answer":"Yes","rationale":"Traceable"}}],1,{"D000001":1},authority_refs=["synthetic:approval"])
 return s,p,u

def test_export_import_backup_restore_roundtrip(ledger):
 s,p,u=seed(ledger);a=Artifacts(s)
 original=a.verify("alpha",u,p)["data"]
 exported=a.create("alpha",u,p,"export")["data"]
 path,row=a.download("alpha",u,p,exported["artifact_id"])
 candidate=a.import_native(p,json.loads(path.read_text(encoding="utf-8")),True)["data"]
 assert candidate["logical_sha256"]==original["logical_sha256"]
 assert not candidate["registered"]
 backup=a.create("alpha",u,p,"backup")["data"]
 restored=a.restore_check("alpha",u,p,backup["artifact_id"])["data"]
 assert restored["logical_sha256"]==original["logical_sha256"] and not restored["activated"]
 assert a.catalog_backup(p)["catalog_revision"]==1
 assert a.verify("alpha",u,p)["revision"]==2

def test_import_tamper_and_artifact_tamper_rejected(ledger):
 s,p,u=seed(ledger);a=Artifacts(s)
 with s.catalog.project("alpha",u,p) as (db,_):value=bundle(db)
 corrupted=copy.deepcopy(value);corrupted["decisions"][0]["title"]="Tampered"
 with pytest.raises(Fault,match="Current state"):a.import_native(p,corrupted,True)
 exported=a.create("alpha",u,p,"export")["data"]
 path,_=a.download("alpha",u,p,exported["artifact_id"]);path.write_bytes(b"tampered")
 with pytest.raises(Fault,match="hash"):a.download("alpha",u,p,exported["artifact_id"])
 assert a.verify("alpha",u,p)["data"]["integrity"]=="ok"

def test_http_artifacts_and_static_assets(client):
 c=client
 from uuid import uuid4
 r=c.post("/api/v1/projects",json={"project_id":"alpha","name":"Alpha","expected_catalog_revision":0,"request_id":str(uuid4())}).json()
 c.headers["X-Ledger-UUID"]=r["data"]["ledger_uuid"]
 for route in ["exports","backups","verify"]:
  result=c.post("/api/v1/projects/alpha/"+route,json={})
  assert result.status_code==200,result.text
 assert c.get("/").status_code==200
 assert c.get("/static/app.js").status_code==200
 assert c.get("/static/logo.png").headers["content-type"]=="image/png"

def test_manager_paging_inventory_binding_and_legacy(ledger):
 s,p,u=ledger;a=Artifacts(s)
 # Deterministic equal timestamps exercise the ID tie breaker without expensive file creation.
 with s.catalog.project('alpha',u,p,True) as (db,_):
  for n in range(27):
   db.execute('INSERT INTO artifacts VALUES(?,?,?,?,?,?,?,?,?)',
     (f'file-{n:03}', 'backup' if n<26 else 'export','complete',0,'synthetic',10,'hash','2026-10-05T10:00:00Z',None))
 first=a.list('alpha',u,p,limit=10,kind='backup',order='newest')
 assert first['total_count']==26 and first['page_count']==3 and first['page_index']==1
 assert [r['artifact_id'] for r in first['data']]==[f'file-{n:03}' for n in range(25,15,-1)]
 second=a.list('alpha',u,p,first['next_cursor'],10,'backup','newest')
 previous=a.list('alpha',u,p,second['previous_cursor'],10,'backup','newest')
 assert previous['data']==first['data']
 final=a.list('alpha',u,p,second['next_cursor'],10,'backup','newest')
 assert len(final['data'])==6 and final['complete'] and final['next_cursor'] is None
 assert all('relative_path' not in r for r in first['data'])
 assert len(a.list('alpha',u,p)['data'])==27
 assert a.list('alpha',u,p,kind='export',order='newest')['total_count']==1
 for kwargs in ({'limit':25,'kind':'backup'},{'limit':10,'kind':'export'}):
  with pytest.raises(Fault) as fault:a.list('alpha',u,p,cursor=first['next_cursor'],order='newest',**kwargs)
  assert fault.value.code=='VALIDATION_ERROR'
 with s.catalog.project('alpha',u,p,True) as (db,_):db.execute("UPDATE artifacts SET state='failed' WHERE artifact_id='file-025'")
 with pytest.raises(Fault) as fault:a.list('alpha',u,p,first['next_cursor'],10,'backup','newest')
 assert fault.value.code=='CURSOR_STALE'

def test_manager_byte_limited_pages_and_empty(ledger):
 s,p,u=ledger;a=Artifacts(s)
 empty=a.list('alpha',u,p,kind='backup',order='newest')
 assert empty['page_count']==empty['page_index']==empty['total_count']==0
 with s.catalog.project('alpha',u,p,True) as (db,_):
  for n in range(7):db.execute('INSERT INTO artifacts VALUES(?,?,?,?,?,?,?,?,?)',
   (f'file-{n}', 'backup','failed',0,'synthetic',None,None,'2026-10-05T10:00:00Z','x'*20000))
 page=a.list('alpha',u,p,limit=100,kind='backup',order='newest');ids=[]
 while True:
  ids.extend(r['artifact_id'] for r in page['data'])
  if not page['next_cursor']:break
  page=a.list('alpha',u,p,page['next_cursor'],100,'backup','newest')
 assert len(ids)==len(set(ids))==7 and page['page_count']==3
 prior=a.list('alpha',u,p,page['previous_cursor'],100,'backup','newest')
 assert prior['page_index']==2 and len(prior['data'])==3

def test_manager_http_filters(client):
 from uuid import uuid4
 c=client;r=c.post('/api/v1/projects',json={'project_id':'alpha','name':'Alpha','expected_catalog_revision':0,'request_id':str(uuid4())}).json()
 c.headers['X-Ledger-UUID']=r['data']['ledger_uuid']
 c.post('/api/v1/projects/alpha/exports',json={})
 page=c.get('/api/v1/projects/alpha/artifacts?kind=export&order=newest&limit=10').json()
 assert page['total_count']==1 and page['data'][0]['kind']=='export'
 assert c.get('/api/v1/projects/alpha/artifacts?order=newest').status_code==422
 assert c.get('/api/v1/projects/alpha/artifacts?kind=wrong').status_code==422
