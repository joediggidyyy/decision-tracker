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
