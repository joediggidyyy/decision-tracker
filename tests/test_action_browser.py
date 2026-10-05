"""Real Chromium exercises isolated application data through native Calamum."""
import os, shutil, subprocess, threading, socket, time
from pathlib import Path
import uvicorn
from decision_tracker.api import create_app
from decision_tracker.config import Config
from decision_tracker.credentials import Credentials

def run_browser(tmp_path, script="action_browser.cjs", folder="action-browser"):

    credentials=Credentials(tmp_path/'auth.sqlite',initialize=True)
    password='Synthetic action form test password'
    credentials.redeem('bootstrap',credentials.issue('bootstrap'),password,password)
    with socket.socket() as sock:
        sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    app=create_app(Config(data_root=str(tmp_path/'data'),auth_store=str(credentials.path),local_storage_confirmed=True,port=port))
    if folder=='projects-browser':
        from decision_tracker import store
        from decision_tracker.artifacts import Artifacts,bundle
        from decision_tracker.auth import Principal
        from uuid import uuid4
        principal=Principal('fixture',frozenset({'*'}),frozenset({'maintain','registry'}))
        for version,promote in ((1,True),(2,True),(2,False)):
            source=tmp_path/(str(uuid4())+'.sqlite');store.initialize(source,str(uuid4()),schema_version=version)
            with store.connect(source) as db:value=bundle(db)
            Artifacts(app.state.service).import_native(principal,value,promote)
    server=uvicorn.Server(uvicorn.Config(app,host='127.0.0.1',port=port,log_level='warning'))
    thread=threading.Thread(target=server.run,daemon=True);thread.start()
    try:
        for _ in range(100):
            if server.started:break
            time.sleep(.05)
        assert server.started
        root=Path(__file__).parents[1]
        output=root/'.local'/folder;output.mkdir(parents=True,exist_ok=True)
        result=subprocess.run([shutil.which('node'),str(root/'tests'/script),f'http://127.0.0.1:{port}',str(output)],capture_output=True,text=True,encoding="utf-8",timeout=180,env=os.environ.copy())
        print(result.stdout)
        assert result.returncode==0,result.stdout+result.stderr
    finally:
        server.should_exit=True;thread.join(10)
        assert not thread.is_alive()


def test_action_forms_browser(tmp_path):
    run_browser(tmp_path)
