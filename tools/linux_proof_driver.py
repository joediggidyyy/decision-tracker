"""Calamum entry inside the existing bounded construction container."""
from pathlib import Path
import hashlib,json,os,sys,shutil
root=Path('/tmp/work');shutil.copytree('/input',root);os.chdir(root)
sys.path[:0]=[str(root/'src'),str(root),'/opt/test','/opt/runtime']
os.environ['PYTHONPATH']=':'.join(sys.path[:4]);os.environ['PYTHONDONTWRITEBYTECODE']='1'
manifest=json.loads((root/'input-manifest.json').read_text())
for row in manifest['files']:
    p=root/row['copy_path'];assert hashlib.sha256(p.read_bytes()).hexdigest()==row['sha256']
for rel,digest in manifest['source_sha256'].items():assert hashlib.sha256((root/rel).read_bytes()).hexdigest()==digest
from calamum.api import get_definition,run_test_definition
definition=get_definition('dt-migration',catalog_root=root/'catalog')
Path('/out/effective-definition.json').write_text(json.dumps(definition,indent=2))
result=run_test_definition(definition,runs_root=Path('/out/runs'),requested_lanes=['sandbox_test'])
Path('/out/calamum-report.json').write_text(json.dumps(result,indent=2))
Path('/out/input-correspondence.json').write_text(json.dumps({'files':manifest['files'],'source_sha256':manifest['source_sha256'],'contract_sha256':manifest['contract_sha256'],'business_conversion':False,'candidate_created':False},indent=2))
print(json.dumps({'result':result['result'],'run_id':result['run_id']}))
sys.exit(0 if result['result']=='pass' else 1)
