from uuid import uuid4
import shutil,subprocess
from pathlib import Path
from conftest import change


def test_open_count_lifecycle(ledger):
 s,p,u=ledger
 def count():return s.project_summary('alpha',u,p)['data']['counts']['open']
 assert count()==0
 change(s,p,u,[{'op':'decision.create','data':{'title':'A','question':'Which?'}},{'op':'decision.create','data':{'title':'B','question':'Which?'}}])
 assert count()==2
 change(s,p,u,[{'op':'decision.close','key':'D000002','data':{'answer':'Yes','rationale':'Reviewed'}}],1,{'D000002':1},authority_refs=['Synthetic owner'])
 assert count()==1
 change(s,p,u,[{'op':'decision.close','key':'D000001','data':{'answer':'Yes','rationale':'Reviewed'}}],2,{'D000001':1},authority_refs=['Synthetic owner'])
 assert count()==0
 change(s,p,u,[{'op':'decision.reopen','key':'D000001','data':{'impact':'Review again'}}],3,{'D000001':2},authority_refs=['Synthetic owner'])
 assert count()==1


def test_open_count_browser_and_modules(tmp_path):
 root=Path(__file__).parents[1];node=shutil.which('node')
 for name in ['project-attention.js','app.js','projects.js']:
  result=subprocess.run([node,'--check','--input-type=module'],input=(root/'src/decision_tracker/static'/name).read_text(encoding='utf-8'),capture_output=True,text=True,encoding='utf-8',timeout=20)
  assert result.returncode==0,result.stderr
 result=subprocess.run([node,str(root/'tests/project_attention_cases.mjs')],capture_output=True,text=True,encoding='utf-8',timeout=20)
 assert result.returncode==0,result.stdout+result.stderr
 from test_action_browser import run_browser
 run_browser(tmp_path,'project_attention_browser.cjs','project-attention-browser')
