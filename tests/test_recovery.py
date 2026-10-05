import json,os,sqlite3,subprocess,sys,time
from pathlib import Path
from uuid import uuid4
import pytest
from decision_tracker import store
from decision_tracker.artifacts import Artifacts
from decision_tracker.models import Change
from decision_tracker.service import Service
from decision_tracker.errors import Fault
from conftest import change

def test_killed_transaction_preserves_prior_state(ledger,tmp_path):
 s,p,u=ledger
 change(s,p,u,[{"op":"decision.create","data":{"title":"Before crash","question":"Atomic?"}}])
 with s.catalog.project("alpha",u,p) as (db,project):path=s.root/project["db_path"]
 marker=tmp_path/"ready"
 code="import sqlite3,sys,time,pathlib; db=sqlite3.connect(sys.argv[1],isolation_level=None); db.execute('BEGIN IMMEDIATE'); db.execute(\"UPDATE decisions SET title='Uncommitted'\"); pathlib.Path(sys.argv[2]).write_text('ready'); time.sleep(30)"
 proc=subprocess.Popen([sys.executable,"-c",code,str(path),str(marker)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
 try:
  deadline=time.monotonic()+10
  while not marker.exists() and time.monotonic()<deadline:time.sleep(.01)
  assert marker.exists()
 finally:proc.kill();proc.wait(timeout=10)
 assert s.detail("alpha",u,p,"D000001")["data"]["title"]=="Before crash"
 assert Artifacts(s).verify("alpha",u,p)["revision"]==1

def test_busy_bound_and_restart_replay(ledger):
 s,p,u=ledger
 request=Change(expected_ledger_uuid=u,expected_revision=0,request_id=uuid4(),reason="Restart proof",operations=[{"op":"decision.create","data":{"title":"Stable","question":"Retry?"}}])
 first=s.change("alpha",p,request)
 restarted=Service(s.root)
 assert restarted.change("alpha",p,request)["replayed"]
 with s.catalog.project("alpha",u,p) as (_,project):path=s.root/project["db_path"]
 writer=sqlite3.connect(path,isolation_level=None);writer.execute("BEGIN IMMEDIATE")
 start=time.monotonic()
 try:
  with pytest.raises(Fault,match="busy"):
   change(s,p,u,[{"op":"decision.edit","key":"D000001","data":{"title":"Blocked"}}],1,{"D000001":1})
 finally:writer.rollback();writer.close()
 assert 4<=time.monotonic()-start<8
 assert Artifacts(s).verify("alpha",u,p)["revision"]==1

def test_incomplete_artifact_refused_and_unknown_schema(ledger):
 s,p,u=ledger
 with s.catalog.project("alpha",u,p,True) as (db,_):
  db.execute("INSERT INTO artifacts VALUES(?,?,?,?,?,NULL,NULL,?,NULL)",("pending","export","pending",0,"absent", "2026-10-05T00:00:00Z"))
 with pytest.raises(Fault,match="not verified"):Artifacts(s).download("alpha",u,p,"pending")
 with s.catalog.project("alpha",u,p) as (db,_):
  db.execute("PRAGMA ignore_check_constraints=ON")
  db.execute("UPDATE meta SET schema_version=2")
 with pytest.raises(Fault,match="Unsupported"):s.list_decisions("alpha",u,p)
