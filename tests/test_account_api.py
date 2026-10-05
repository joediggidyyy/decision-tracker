import json,time
from pathlib import Path
from fastapi.testclient import TestClient
from decision_tracker.api import create_app
from decision_tracker.config import Config
from decision_tracker.credentials import Credentials
from decision_tracker.errors import Fault
from test_credentials import OLD,NEW

def test_password_http_and_no_recovery_endpoint(tmp_path):
    store=Credentials(tmp_path/'auth.sqlite',initialize=True);code=store.issue('bootstrap')
    app=create_app(Config(data_root=str(tmp_path/'data'),auth_store=str(store.path),local_storage_confirmed=True))
    origin='http://127.0.0.1:8765'
    with TestClient(app,base_url=origin) as client:
        pre=client.get('/api/v1/session/setup').json()['data'];assert pre['setup_available']
        headers={'Origin':origin,'X-CSRF-Token':pre['csrf_token']}
        response=client.post('/api/v1/session/setup',headers=headers,json={'bootstrap_code':code,'new_password':OLD,'confirmation':OLD});assert response.status_code==204,response.text
        pre=client.get('/api/v1/session/setup').json()['data'];assert not pre['setup_available'];headers['X-CSRF-Token']=pre['csrf_token']
        response=client.post('/api/v1/session',headers=headers,json={'password':OLD});assert response.status_code==200,response.text
        headers['X-CSRF-Token']=response.json()['data']['csrf_token'];old_cookie=client.cookies.get('dt_session')
        assert client.post('/api/v1/account/password',headers=headers,json={'current_password':'wrong','new_password':NEW,'confirmation':NEW}).status_code==401
        response=client.post('/api/v1/account/password',headers=headers,json={'current_password':OLD,'new_password':NEW,'confirmation':NEW});assert response.status_code==204,response.text
        assert client.cookies.get('dt_session')!=old_cookie
        assert client.get('/api/v1/session').status_code==200
        assert client.post('/api/v1/account/recover',headers=headers,json={}).status_code==404
        reset=store.issue('recovery')
        assert client.get('/api/v1/session').status_code==401
        pre=client.get('/api/v1/session/setup').json()['data'];headers['X-CSRF-Token']=pre['csrf_token']
        assert client.post('/api/v1/session/setup',headers=headers,json={'bootstrap_code':reset,'new_password':OLD,'confirmation':OLD}).status_code==400


def test_managed_cold_start_reuse_stop(tmp_path):
    import os,sys,socket
    if os.name!='nt':__import__('pytest').skip('Windows adapter')
    from decision_tracker.deployment import initialize,ensure,local_admin,load,probe
    from decision_tracker.windows_local import read_bundle
    sock=socket.socket();sock.bind(('127.0.0.1',0));port=sock.getsockname()[1];sock.close()
    path=tmp_path/'deployment'/'deployment.json'
    initialize(path,python=sys.executable,source_root=Path(__file__).resolve().parents[1]/'src',data_root=tmp_path/'data',port=port)
    first=None
    try:
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(3) as pool:starts=list(pool.map(lambda _:ensure(path),range(3)))
        assert sum(x['started'] for x in starts)==1
        assert len({x['instance_id'] for x in starts})==1
        first=starts[0];assert first['ready']
        second=ensure(path);assert not second['started'] and second['instance_id']==first['instance_id']
        code=local_admin(path,'setup-code')['code'];assert code
        assert local_admin(path,'status')['state']=='RUNNING'
        assert local_admin(path,'stop')['state']=='DRAINING'
        value,cfg=load(path);bundle=read_bundle(Path(value['bundle']))
        deadline=time.monotonic()+10
        while time.monotonic()<deadline:
            try:
                if probe(value,cfg,bundle['control_key']) is None:break
            except Fault as exc:
                assert exc.code=='SERVICE_UNAVAILABLE'
            time.sleep(.1)
        else:raise AssertionError('Managed process did not stop')
    finally:
        if first:
            try:local_admin(path,'stop')
            except (Fault,OSError):pass


def test_preauth_forgery_and_secret_redaction(tmp_path):
    store=Credentials(tmp_path/'auth.sqlite',initialize=True)
    app=create_app(Config(data_root=str(tmp_path/'data'),auth_store=str(store.path),local_storage_confirmed=True))
    origin='http://127.0.0.1:8765'
    with TestClient(app,base_url=origin) as client:
        pre=client.get('/api/v1/session/setup').json()['data']
        secret='Synthetic private malformed value'
        response=client.post('/api/v1/session',headers={'Origin':'https://foreign.invalid','X-CSRF-Token':pre['csrf_token']},json={'password':secret})
        assert response.status_code==403 and secret not in response.text
        response=client.post('/api/v1/session',headers={'Origin':origin,'X-CSRF-Token':pre['csrf_token']},json={'password':{'secret':secret}})
        assert response.status_code==422 and secret not in response.text
        assert client.post('/api/v1/account/reset-password',json={}).status_code==404


def test_token_rotation_published_journal_recovery(tmp_path):
    import os
    if os.name!='nt':__import__('pytest').skip('Windows adapter')
    from decision_tracker.config import PrincipalConfig
    from decision_tracker.deployment import initialize,load,atomic_json
    from decision_tracker.administration import dispatch,recover_token_journal
    from decision_tracker.windows_local import read_bundle,save_bundle
    from decision_tracker.credentials import digest
    path=tmp_path/'deployment'/'deployment.json'
    initialize(path,data_root=tmp_path/'data')
    value,cfg=load(path)
    cfg.principals.append(PrincipalConfig(id='agent',token_env='DT_AGENT_TOKEN',projects=['alpha'],capabilities=['read']))
    store=Credentials(Path(cfg.auth_store))
    first=dispatch(value,cfg,store,None,'token-create',{'principal':'agent','store_local':True})
    second=dispatch(value,cfg,store,None,'token-rotate',{'token_id':first['token_id'],'store_local':True})
    import pytest
    with pytest.raises(Fault):store.token_principal(first['token'])
    assert store.token_principal(second['token'])=='agent'
    key,raw=store.token_create('agent',state='pending')
    journal=path.parent/'token-journal.json'
    atomic_json(journal,{'new_id':key,'old_id':second['token_id'],'principal':'agent','digest':digest(raw)})
    bundle=read_bundle(Path(value['bundle']));bundle['tokens']['agent']=raw;save_bundle(Path(value['bundle']),bundle)
    recover_token_journal(value,store)
    assert store.token_principal(raw)=='agent'
    with pytest.raises(Fault):store.token_principal(second['token'])


def test_readiness_rejects_unknown_listener_without_credentials(tmp_path):
    import threading
    from http.server import HTTPServer,BaseHTTPRequestHandler
    from decision_tracker.deployment import probe
    import pytest
    seen=[]
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            seen.append(dict(self.headers));self.send_response(200);self.end_headers();self.wfile.write(b'{"version":1,"mac":"wrong"}')
        def log_message(self,*args):pass
    server=HTTPServer(('127.0.0.1',0),Handler);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    try:
        cfg=Config(port=server.server_port)
        with pytest.raises(Fault) as caught:probe({'deployment_id':'test'},cfg,'synthetic-control-key')
        assert caught.value.code=='PORT_CONFLICT'
        assert seen and 'Authorization' not in seen[0]
    finally:server.shutdown();server.server_close();thread.join(2)


def test_protocol_rejects_payloads_before_open(monkeypatch):
    from decision_tracker.protocol import main
    calls=[]
    monkeypatch.setattr('decision_tracker.deployment.open_app',lambda p:calls.append(p))
    for uri in ['decision-tracker://recover','decision-tracker://open?command=anything','decision-tracker://open#code','https://foreign.invalid','decision-tracker://open/extra']:
        assert main(['deployment.json',uri])==2
    assert main(['deployment.json','decision-tracker://open','extra'])==2
    assert not calls
    assert main(['deployment.json','decision-tracker://open'])==0
    assert len(calls)==1


def test_failed_migration_prevalidation_does_not_publish(tmp_path,monkeypatch):
    from argparse import Namespace
    from decision_tracker.local_cli import execute
    from decision_tracker.config import PrincipalConfig
    import pytest
    cfg=Config(data_root=str(tmp_path/'data'),local_storage_confirmed=True)
    cfg.principals.append(PrincipalConfig(id='agent',token_env='DT_MISSING_TEST',projects=['alpha'],capabilities=['read']))
    old=tmp_path/'legacy.json';old.write_text(cfg.model_dump_json())
    monkeypatch.setattr('decision_tracker.local_cli.terminal',lambda *args:None)
    monkeypatch.delenv('DT_MISSING_TEST',raising=False)
    descriptor=tmp_path/'new'/'deployment.json'
    with pytest.raises(Fault):execute(Namespace(deployment=str(descriptor),group='auth',action='migrate',config=str(old)))
    assert not descriptor.exists() and not descriptor.parent.exists()


def test_status_poll_does_not_extend_idle_timer(tmp_path):
    from decision_tracker.config import PrincipalConfig
    store=Credentials(tmp_path/'auth.sqlite',initialize=True)
    _,raw=store.token_create('agent')
    cfg=Config(data_root=str(tmp_path/'data'),auth_store=str(store.path),local_storage_confirmed=True)
    cfg.principals.append(PrincipalConfig(id='agent',token_env='DT_AGENT_TOKEN',projects=['*'],capabilities=['read']))
    app=create_app(cfg)
    tick=[0.];app.state.lifecycle.clock=lambda:tick[0]
    with TestClient(app,base_url='http://127.0.0.1:8765') as client:
        tick[0]=1000
        assert client.get('/api/v1/status',headers={'Authorization':'Bearer '+raw}).status_code==200
        assert app.state.lifecycle.last==0
        assert client.get('/api/v1/projects',headers={'Authorization':'Bearer '+raw}).status_code==200
        assert app.state.lifecycle.last==1000


def test_managed_agent_cli_and_online_offline_recovery(tmp_path):
    import os,sys,socket,subprocess
    import pytest
    if os.name!='nt':pytest.skip('Windows adapter')
    from decision_tracker.deployment import initialize,load,atomic_json,ensure,local_admin,probe
    from decision_tracker.windows_local import read_bundle
    from decision_tracker.config import PrincipalConfig
    sock=socket.socket();sock.bind(('127.0.0.1',0));port=sock.getsockname()[1];sock.close()
    path=tmp_path/'deployment'/'deployment.json';initialize(path,python=sys.executable,source_root=Path(__file__).resolve().parents[1]/'src',data_root=tmp_path/'data',port=port)
    value,cfg=load(path);cfg.principals.append(PrincipalConfig(id='agent',token_env='DT_AGENT_TOKEN',projects=['alpha'],capabilities=['read','write','propose']))
    atomic_json(Path(value['config']),cfg.model_dump(mode='json'))
    store=Credentials(Path(cfg.auth_store));code=local_admin(path,'setup-code')['code'];store.redeem('bootstrap',code,OLD,OLD)
    token=local_admin(path,'token-create',principal='agent',store_local=True)
    def cli(*args):
        result=subprocess.run([sys.executable,'-m','decision_tracker.cli',*args,'--deployment',str(path),'--credential-principal','agent','--json'],capture_output=True,text=True,timeout=15)
        return result.returncode,json.loads(result.stdout)
    try:
        ensure(path)
        status,result=cli('service','status');assert status==0 and result['ok']
        status,result=cli('project','list');assert status==0 and result['data']==[]
        status,result=cli('project','show','--project','other');assert status==2 and result['error']['code']=='NOT_FOUND'
        reset=local_admin(path,'recover')['code'];assert store.state()['state']=='recovery_pending'
        assert cli('project','list')[0]==0
        local_admin(path,'reset-password',code=reset,password=NEW,confirmation=NEW)
        assert store.check_password(NEW)>1
        replacement=local_admin(path,'token-rotate',token_id=token['token_id'],store_local=True)
        with pytest.raises(Fault):store.token_principal(token['token'])
        assert cli('project','list')[0]==0
        local_admin(path,'token-revoke',token_id=replacement['token_id']);assert cli('project','list')[0]==4
    finally:
        local_admin(path,'stop')
        deadline=time.monotonic()+10;bundle=read_bundle(Path(value['bundle']))
        while time.monotonic()<deadline:
            try:
                if probe(value,cfg,bundle['control_key']) is None:break
            except Fault as exc:
                assert exc.code=='SERVICE_UNAVAILABLE'
            time.sleep(.05)
        else:raise AssertionError('Managed service did not stop')
    reset=local_admin(path,'recover')['code']
    local_admin(path,'reset-password',code=reset,password=OLD,confirmation=OLD)
    assert store.check_password(OLD)>1


def test_two_sessions_revoke_and_recovery_keep_agent_independent(tmp_path):
    from decision_tracker.password_auth import PasswordAuth
    from decision_tracker.config import PrincipalConfig
    import pytest
    store=Credentials(tmp_path/'auth.sqlite',initialize=True);code=store.issue('bootstrap');store.redeem('bootstrap',code,OLD,OLD)
    cfg=Config();cfg.principals.append(PrincipalConfig(id='agent',token_env='DT_AGENT_TOKEN',projects=['alpha'],capabilities=['read']))
    auth=PasswordAuth(cfg,store);one,_=auth.login(OLD);two,_=auth.login(OLD);_,raw=store.token_create('agent')
    epoch=auth.session(one)['epoch'];new_epoch=store.revoke_sessions(OLD,epoch);fresh,_=auth.new_session(new_epoch)
    for sid in [one,two]:
        with pytest.raises(Fault):auth.session(sid)
    assert auth.session(fresh) and auth.bearer(raw).id=='agent'
    store.issue('recovery')
    with pytest.raises(Fault):auth.session(fresh)
    assert auth.bearer(raw).id=='agent'
