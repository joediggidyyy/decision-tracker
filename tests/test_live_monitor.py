import sys, shutil, subprocess
from pathlib import Path

def test_browser_monitor_fault_boundaries():
 node=shutil.which('node')
 assert node,'Node is required only for the JavaScript unit-test lane; it is not an application runtime.'
 result=subprocess.run([node,str(Path(__file__).with_name('live_monitor_cases.mjs')),str(Path(__file__).parents[1]/'src/decision_tracker/static/live.js')],capture_output=True,text=True,timeout=20)
 assert result.returncode==0,result.stdout+result.stderr
 assert 'monitor cases passed' in result.stdout
