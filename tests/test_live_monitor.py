import sys, shutil, subprocess
from pathlib import Path

def test_changed_browser_modules_parse():
 node=shutil.which('node')
 root=Path(__file__).parents[1]/'src/decision_tracker/static'
 for name in ['app.js','projects.js','page-layout.js','refresh.js','yellow-sync.js','saved-decisions.js']:
  result=subprocess.run([node,'--check','--input-type=module'],input=(root/name).read_text(encoding='utf-8'),capture_output=True,text=True,encoding='utf-8',timeout=20)
  assert result.returncode==0,name+'\n'+result.stderr


def test_browser_monitor_fault_boundaries():
 node=shutil.which('node')
 assert node,'Node is required only for the JavaScript unit-test lane; it is not an application runtime.'
 result=subprocess.run([node,str(Path(__file__).with_name('live_monitor_cases.mjs')),str(Path(__file__).parents[1]/'src/decision_tracker/static/live.js')],capture_output=True,text=True,timeout=20)
 assert result.returncode==0,result.stdout+result.stderr
 assert 'monitor cases passed' in result.stdout


def test_browser_update_collection_and_scheduler():
 node=shutil.which('node')
 result=subprocess.run([node,str(Path(__file__).with_name('browser_update_cases.mjs'))],capture_output=True,text=True,timeout=20)
 assert result.returncode==0,result.stdout+result.stderr
 assert 'browser update cases passed' in result.stdout
