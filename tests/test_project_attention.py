from uuid import uuid4
import json,shutil,subprocess,time
from pathlib import Path
import pytest
from conftest import change
from test_api import setup_project
from decision_tracker.errors import Fault
from decision_tracker import store
from decision_tracker.models import ProjectChange


def test_attention_open_intervals_not_count_or_edits(ledger):
 s,p,u=ledger
 def a():return s.project_summary('alpha',u,p,True)['data']['attention']
 assert a()=={'version':1,'open_count':0,'latest_open_revision':None}
 change(s,p,u,[{'op':'decision.create','data':{'title':'Old','question':'Which?'}}])
 assert a()['latest_open_revision']==1
 change(s,p,u,[{'op':'decision.edit','key':'D000001','data':{'title':'Edited'}}],1,{'D000001':1})
 assert a()['latest_open_revision']==1
 change(s,p,u,[{'op':'decision.create','data':{'title':'New','question':'Which?'}}],2)
 assert a()=={'version':1,'open_count':2,'latest_open_revision':3}
 change(s,p,u,[{'op':'decision.close','key':'D000002','data':{'answer':'Yes','rationale':'Reviewed'}}],3,{'D000002':1},authority_refs=['Synthetic owner'])
 assert a()=={'version':1,'open_count':1,'latest_open_revision':1}
 change(s,p,u,[{'op':'decision.reopen','key':'D000002','data':{'impact':'Review again'}}],4,{'D000002':2},authority_refs=['Synthetic owner'])
 assert a()=={'version':1,'open_count':2,'latest_open_revision':5}
 # A closed/deprecated newest interval disappears even with an old open question.
 change(s,p,u,[{'op':'decision.deprecate','key':'D000002','data':{'kind':'obsolete'}}],5,{'D000002':3},authority_refs=['Synthetic owner'])
 assert a()['latest_open_revision']==1
 assert 'attention' not in s.project_summary('alpha',u,p)['data']


def test_attention_read_contract(client):
 u=setup_project(client);client.headers['Authorization']='Bearer '+client.readonly
 r=client.get('/api/v1/projects/alpha/summary?include_attention=true');assert r.status_code==200
 assert r.json()['data']['attention']=={'version':1,'open_count':0,'latest_open_revision':None}
 assert client.get('/api/v1/projects/alpha/summary?include_attention=invalid').status_code==422
 client.headers['X-Ledger-UUID']=str(uuid4());assert client.get('/api/v1/projects/alpha/summary?include_attention=true').status_code==409


def test_attention_missing_history_refuses_false_clear(ledger):
 s,p,u=ledger;change(s,p,u,[{'op':'decision.create','data':{'title':'Question','question':'Which?'}}])
 with s.catalog.project('alpha',u,p) as (db,_):
  db.execute('DROP TRIGGER immutable_revisions_delete');db.execute('DELETE FROM revisions')
 with pytest.raises(Fault):s.project_summary('alpha',u,p,True)
 assert s.project_summary('alpha',u,p)['data']['counts']['open']==1


def test_attention_imported_seed(ledger):
 from legacy_fixture import request
 from decision_tracker.artifacts import Artifacts
 s,p,_=ledger
 candidate=Artifacts(s).import_native(p,request(),True)['data']
 result=s.catalog.mutate(p,ProjectChange(kind='register',project_id='imported',name='Imported',candidate_id=candidate['candidate_id'],expected_candidate_digest=candidate['logical_digest'],expected_catalog_revision=1,request_id=uuid4()))
 u=result['data']['ledger_uuid'];summary=s.project_summary('imported',u,p,True)
 assert summary['data']['attention']['open_count']==summary['data']['counts']['open']
 if summary['data']['counts']['open']:assert summary['data']['attention']['latest_open_revision']==0


def test_attention_synthetic_scale(tmp_path,principal):
 from decision_tracker.service import Service
 s=Service(tmp_path/'scale');start=time.monotonic();counts=0;read_seconds=0
 for n in range(50):
  name=f'p{n}';u=s.catalog.mutate(principal,ProjectChange(project_id=name,name=name,expected_catalog_revision=n,request_id=uuid4()))['data']['ledger_uuid']
  from decision_tracker.models import Change
  for revision in range(3):
   s.change(name,principal,Change(expected_ledger_uuid=u,expected_revision=revision,request_id=uuid4(),reason='Synthetic scale',operations=[{'op':'decision.create','data':{'title':str(i),'question':'Which?'}} for i in range(25)]))
  read_start=time.monotonic();counts+=s.project_summary(name,u,principal,True)['data']['attention']['open_count'];read_seconds+=time.monotonic()-read_start
 elapsed=time.monotonic()-start;print(f'SCALE 50 projects, 3750 open records, 150 transactions including setup: {elapsed:.3f}s')
 output=Path(__file__).parents[1]/'.local/project-attention-scale.json';output.parent.mkdir(exist_ok=True);output.write_text(json.dumps({'projects':50,'open_records':counts,'transactions':150,'read_seconds':read_seconds,'setup_and_read_seconds':elapsed,'sweep_budget_seconds':20,'reads_within_sweep_budget':read_seconds<20},indent=2)+'\n',encoding='utf-8')
 assert counts==3750


def test_attention_browser_and_modules(tmp_path):
 root=Path(__file__).parents[1];node=shutil.which('node')
 for name in ['project-attention.js','app.js','projects.js']:
  result=subprocess.run([node,'--check','--input-type=module'],input=(root/'src/decision_tracker/static'/name).read_text(encoding='utf-8-sig'),capture_output=True,text=True,encoding="utf-8",timeout=20)
  assert result.returncode==0,result.stderr
 result=subprocess.run([node,str(root/'tests/project_attention_cases.mjs')],capture_output=True,text=True,encoding="utf-8",timeout=30)
 assert result.returncode==0,result.stdout+result.stderr
 from test_action_browser import run_browser
 run_browser(tmp_path,'project_attention_browser.cjs','project-attention-browser')
