import json,os,subprocess,time
from pathlib import Path
from uuid import uuid4
import pytest
from decision_tracker.config import Config,PrincipalConfig,contained
from decision_tracker.auth import Auth,Principal
from decision_tracker.errors import Fault
from decision_tracker.models import Change,ProjectChange
from conftest import change
from test_api import setup_project

def test_config_and_expired_sessions(tmp_path):
 token="synthetic-configuration-only-"+("x"*32)
 cfg=Config(data_root=str(tmp_path/"data"),local_storage_confirmed=True)
 with pytest.raises(Fault):Auth(cfg,{"DT_OPERATOR_TOKEN":"short"})
 auth=Auth(cfg,{"DT_OPERATOR_TOKEN":token})
 sid,session=auth.login(token);session["seen"]-=1801
 with pytest.raises(Fault):auth.session(sid)
 for _ in range(5):
  with pytest.raises(Fault):auth.login("invalid")
 with pytest.raises(Fault,match="Too many"):auth.login(token)
 with pytest.raises(Fault):Config(data_root=str(tmp_path/"OneDrive"/"data"),local_storage_confirmed=True).root

def test_containment_and_junction(tmp_path):
 root=tmp_path/"root";root.mkdir()
 for path in ("../outside.sqlite","C:/outside.sqlite","stream:alternate","/absolute.sqlite"):
  with pytest.raises(Fault):contained(root,path)
 if os.name=="nt":
  outside=tmp_path/"outside";outside.mkdir()
  link=root/"junction"
  result=subprocess.run(["cmd","/c","mklink","/J",str(link),str(outside)],capture_output=True,text=True,timeout=10)
  assert result.returncode==0,result.stderr
  try:
   with pytest.raises(Fault):contained(root,"junction/db.sqlite")
  finally:link.rmdir()

def test_scope_cannot_be_promoted_and_payload_is_bounded(client):
 u=setup_project(client)
 client.headers["Authorization"]="Bearer "+client.readonly
 payload={"expected_ledger_uuid":u,"expected_revision":0,"request_id":str(uuid4()),"reason":"Synthetic",
          "operations":[{"op":"decision.create","data":{"title":"X","question":"X?"}}]}
 assert client.post("/api/v1/projects/alpha/changes",json=payload).status_code==403
 client.headers["Authorization"]="Bearer "+client.token
 payload["principal_id"]="operator"
 assert client.post("/api/v1/projects/alpha/changes",json=payload).status_code==422
 del payload["principal_id"];payload["operations"][0]["data"]["title"]=123
 assert client.post("/api/v1/projects/alpha/changes",json=payload).status_code==422
 assert client.post("/api/v1/projects/alpha/changes",content=b"x"*(1024*1024+1),headers={"Content-Type":"application/json"}).status_code==413
 assert client.get("/api/v1/projects/alpha/decisions").json()["revision"]==0

def test_two_projects_duplicate_identity_and_registration_replay(ledger):
 s,p,u=ledger
 req=ProjectChange(project_id="beta",name="Beta",expected_catalog_revision=1,request_id=uuid4())
 beta=s.catalog.mutate(p,req)
 assert s.catalog.mutate(p,req)["replayed"]
 change(s,p,u,[{"op":"decision.create","data":{"title":"Only alpha","question":"Scoped?"}}])
 assert s.list_decisions("beta",beta["data"]["ledger_uuid"],p)["data"]==[]
 restricted=Principal("alpha-only",frozenset({"alpha"}),frozenset({"read"}))
 assert [x["project_id"] for x in s.catalog.listing(restricted)["data"]]==["alpha"]
 with pytest.raises(Fault):s.list_decisions("beta",beta["data"]["ledger_uuid"],restricted)
 from decision_tracker.artifacts import Artifacts,bundle
 with s.catalog.project("alpha",u,p) as (db,_):value=bundle(db)
 candidate=Artifacts(s).import_native(p,value,True)["data"]
 with pytest.raises(Fault,match="already enabled"):
  s.catalog.mutate(p,ProjectChange(kind="register",project_id="duplicate",name="Duplicate",relative_path=candidate["relative_path"],expected_catalog_revision=2,request_id=uuid4()))
 assert len(list((s.root/"catalog-backups").glob("*.receipt.json")))>=2
