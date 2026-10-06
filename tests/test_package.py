import hashlib,json,os,subprocess,sys,socket,time,urllib.request
from pathlib import Path

def test_fresh_offline_wheel_install(tmp_path):
 root=Path(__file__).resolve().parents[1]
 wheelhouse=Path(os.environ["DECISION_TRACKER_PROOF_WHEELS"])
 work=tmp_path/"package";work.mkdir()
 env=dict(os.environ);env.pop("PYTHONPATH",None)
 def run(args):
  p=subprocess.run(args,cwd=work,env=env,capture_output=True,text=True,timeout=90)
  assert p.returncode==0,p.stdout+"\n"+p.stderr
  return p.stdout
 run([sys.executable,"-m","pip","wheel","--no-deps","--no-build-isolation","--wheel-dir",str(work),str(root)])
 wheel=next(work.glob("decision_tracker-*.whl"))
 venv=work/"venv"
 run([sys.executable,"-m","venv",str(venv)])
 python=venv/("Scripts/python.exe" if os.name=="nt" else "bin/python")
 run([str(python),"-m","pip","install","--no-index","--find-links",str(wheelhouse),str(wheel)])
 run([str(python),"-m","pip","check"])
 run([str(python),"-c","import importlib.util; assert importlib.util.find_spec('calamum') is None; assert importlib.util.find_spec('pytest') is None"])
 info=json.loads(run([str(python),"-c","import decision_tracker,pathlib,json,hashlib,sys; p=pathlib.Path(decision_tracker.__file__).parent; print(json.dumps({'prefix':sys.prefix,'base':sys.base_prefix,'path':str(p),'assets':{f.name:hashlib.sha256(f.read_bytes()).hexdigest() for f in (p/'static').iterdir()}}))"]))
 assert info["prefix"]!=info["base"]
 assert Path(info["path"]).is_relative_to(venv)
 for name,hash in info["assets"].items():assert hashlib.sha256((root/"src/decision_tracker/static"/name).read_bytes()).hexdigest()==hash
 command=python.with_name("decision-tracker.exe" if os.name=="nt" else "decision-tracker")
 assert "data" in run([str(command),"--help"])
 launch_verified=False
 if os.name=='nt':
  # Isolated deployment: no operator data or global protocol registration.
  descriptor=work/'deployment'/'deployment.json'
  with socket.socket() as sock:
   sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
  run([str(python),'-c',"from pathlib import Path; from decision_tracker.deployment import initialize; import sys; initialize(Path(sys.argv[1]),data_root=sys.argv[2],port=int(sys.argv[3]))",str(descriptor),str(work/'data'),str(port)])
  args=['--deployment',str(descriptor),'--json']
  try:
   ready=json.loads(run([str(command),'service','ensure-running',*args]));assert ready['data']['started']
   again=json.loads(run([str(command),'service','ensure-running',*args]));assert not again['data']['started']
   assert ready['data']['instance_id']==again['data']['instance_id']
   with urllib.request.urlopen(ready['data']['base_url'],timeout=5) as response:
    assert b'id="login-form"' in response.read()
   # Exercise service open through the installed CLI; replace only browser dispatch.
   opened=json.loads(run([str(python),'-c',"import sys,webbrowser; from decision_tracker.cli import main; webbrowser.open=lambda *a,**k: True; sys.argv=['decision-tracker',*sys.argv[1:]]; main()",'service','open',*args]))
   assert opened['data']['ready'];launch_verified=True
  finally:
   run([str(command),'service','stop',*args])
   deadline=time.monotonic()+10
   while time.monotonic()<deadline:
    with socket.socket() as sock:
     if sock.connect_ex(('127.0.0.1',port))!=0:break
    time.sleep(.1)
   else:raise AssertionError('Isolated managed service did not stop')
 (root/".local/package-proof.json").write_text(json.dumps({"wheel_sha256":hashlib.sha256(wheel.read_bytes()).hexdigest(),"isolated":True,"runtime_dependencies_only":True,"cli_launch_verified":launch_verified,"browser_dispatch":"stubbed; loopback sign-in page read through HTTP","assets":info["assets"]},indent=2),encoding="utf-8")
