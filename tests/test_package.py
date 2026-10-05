import hashlib,json,os,subprocess,sys
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
 run([str(python),"-m","pip","install","--no-index","--find-links",str(wheelhouse),"--require-hashes","-r",str(root/"requirements-dev.lock")])
 run([str(python),"-m","pip","install","--no-index","--no-deps",str(wheel)])
 run([str(python),"-m","pip","check"])
 info=json.loads(run([str(python),"-c","import decision_tracker,pathlib,json,hashlib,sys; p=pathlib.Path(decision_tracker.__file__).parent; print(json.dumps({'prefix':sys.prefix,'base':sys.base_prefix,'path':str(p),'assets':{f.name:hashlib.sha256(f.read_bytes()).hexdigest() for f in (p/'static').iterdir()}}))"]))
 assert info["prefix"]!=info["base"]
 assert Path(info["path"]).is_relative_to(venv)
 for name,hash in info["assets"].items():assert hashlib.sha256((root/"src/decision_tracker/static"/name).read_bytes()).hexdigest()==hash
 command=python.with_name("decision-tracker.exe" if os.name=="nt" else "decision-tracker")
 assert "data" in run([str(command),"--help"])
 (root/".local/package-proof.json").write_text(json.dumps({"wheel_sha256":hashlib.sha256(wheel.read_bytes()).hexdigest(),"isolated":True,"assets":info["assets"]},indent=2),encoding="utf-8")
