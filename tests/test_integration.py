import concurrent.futures,json,os,subprocess,sys,threading,time
from uuid import uuid4
import pytest
from decision_tracker.models import Change,ProjectState
from decision_tracker.errors import Fault
from decision_tracker.cli import Client
from decision_tracker.api import InstanceLock
from conftest import change

def test_concurrent_changes_one_commit_then_durable_replay(ledger):
 s,p,u=ledger
 requests=[Change(expected_ledger_uuid=u,expected_revision=0,request_id=uuid4(),reason="Concurrent synthetic write",operations=[{"op":"decision.create","data":{"title":str(i),"question":"Race?"}}]) for i in range(2)]
 def run(req):
  try:return s.change("alpha",p,req)
  except Fault as e:return e.code
 with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(run,requests))
 assert sum(isinstance(x,dict) for x in results)==1
 winner=next(i for i,x in enumerate(results) if isinstance(x,dict))
 assert s.change("alpha",p,requests[winner])["replayed"]
 assert len(s.list_decisions("alpha",u,p)["data"])==1
 s.catalog.mutate(p,ProjectState(enabled=False,expected_catalog_revision=1,request_id=uuid4()),"alpha")
 with pytest.raises(Fault,match="disabled"):s.change("alpha",p,requests[winner])

def test_process_lock_and_outbound_credential_boundary(tmp_path):
 a=InstanceLock(tmp_path/"lock");b=InstanceLock(tmp_path/"lock")
 a.acquire()
 try:
  with pytest.raises(Fault):b.acquire()
 finally:a.release()
 b.acquire();b.release()
 for url in ["https://example.com","http://127.0.0.1@evil.test","http://localhost/path"]:
  with pytest.raises(Fault):Client(url,"synthetic")

def test_live_cli_same_service_restart_replay(tmp_path):
 import uvicorn,secrets
 from decision_tracker.api import create_app
 from decision_tracker.config import Config,PrincipalConfig
 import socket
 sock=socket.socket();sock.bind(("127.0.0.1",0));port=sock.getsockname()[1]
 token=secrets.token_urlsafe(36)
 app=create_app(Config(port=port,data_root=str(tmp_path/"live"),local_storage_confirmed=True,principals=[PrincipalConfig(id="test",token_env="DT_TEST_TOKEN",projects=["*"],capabilities=["read","propose","write","registry"])]),{"DT_TEST_TOKEN":token})
 server=uvicorn.Server(uvicorn.Config(app,host="127.0.0.1",port=port,log_level="error",access_log=False))
 thread=threading.Thread(target=server.run,kwargs={"sockets":[sock]},daemon=True);thread.start()
 deadline=time.monotonic()+10
 while not server.started and time.monotonic()<deadline:time.sleep(.02)
 assert server.started
 env=dict(os.environ,DT_TEST_TOKEN=token)
 def cli(*args):
  proc=subprocess.run([sys.executable,"-m","decision_tracker.cli","--base-url",f"http://127.0.0.1:{port}","--token-env","DT_TEST_TOKEN","--json",*args],env=env,capture_output=True,text=True,timeout=15)
  return proc.returncode,json.loads(proc.stdout)
 try:
  code,project=cli("project","create","--project","alpha","--name","Alpha","--expected-catalog-revision","0","--request-id",str(uuid4()))
  assert code==0,project
  uuid=project["data"]["ledger_uuid"];request_id=str(uuid4())
  binding=tmp_path/"alpha-binding.json"
  code,bound=cli("project","show","--project","alpha","--bind",str(binding))
  assert code==0 and json.loads(binding.read_text())["ledger_uuid"]==uuid
  binding_bytes=binding.read_bytes()
  code,_=cli("project","show","--project","alpha","--bind",str(binding))
  assert code!=0 and binding.read_bytes()==binding_bytes
  code,listed=cli("decision","list","--project","alpha","--binding",str(binding))
  assert code==0 and listed["data"]==[]
  code,wrong=cli("decision","list","--project","beta","--binding",str(binding))
  assert code==3 and wrong["error"]["code"]=="LEDGER_IDENTITY_MISMATCH"
  envelope={"expected_ledger_uuid":uuid,"expected_revision":0,"expected_decision_revisions":{},"request_id":str(uuid4()),"reason":"Skill dry run","operations":[{"op":"decision.create","data":{"title":"Proposal","question":"Commit later?"}}]}
  payload=tmp_path/"change.json";payload.write_text(json.dumps(envelope))
  code,validated=cli("change","apply","--project","alpha","--binding",str(binding),"--input",str(payload),"--dry-run")
  assert code==0,validated
  code,listed=cli("decision","list","--project","alpha","--binding",str(binding))
  assert code==0 and listed["data"]==[]
  args=("decision","create","--project","alpha","--ledger-uuid",uuid,"--expected-revision","0","--request-id",request_id,"--reason","CLI synthetic test","--title","CLI record","--question","Shared rules?")
  code,result=cli(*args);assert code==0,result
  assert result["revision"]==1
  code,replay=cli(*args);assert code==0 and replay["replayed"]
  code,result=cli("decision","get","--project","alpha","--ledger-uuid",uuid,"--key","D000001")
  assert code==0 and result["data"]["title"]=="CLI record"
 finally:
  server.should_exit=True;thread.join(10);sock.close()
 assert not thread.is_alive()
