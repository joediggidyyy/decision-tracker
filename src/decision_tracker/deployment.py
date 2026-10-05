"""Names-only deployment descriptors and single-instance, authenticated local startup."""
from pathlib import Path
from contextlib import contextmanager
import hashlib,hmac,http.client,json,os,secrets,subprocess,sys,time
from uuid import UUID,uuid4
from .errors import Fault,require
from .config import Config,load_config
from .store import encode
from .windows_local import protect_path,read_bundle,save_bundle,owner_sid,admin_request

def default_path():return Path(os.environ.get('LOCALAPPDATA',Path.home()))/'DecisionTracker'/'deployment'/'deployment.json'
def atomic_json(path,value):
    temp=path.with_name(path.name+'.'+uuid4().hex+'.new')
    with temp.open('x',encoding='utf-8') as f:f.write(encode(value));f.flush();os.fsync(f.fileno())
    protect_path(temp);temp.replace(path)
def safe_path(path):
    path=Path(path).absolute()
    require(not str(path).startswith(('\\\\','//')) and not any('onedrive' in p.lower() for p in path.parts),'FORBIDDEN','Use local nonsynchronized deployment storage.',403)
    for p in (path,*path.parents):require(not p.is_symlink() and not p.is_junction(),'FORBIDDEN','Linked deployment paths are not allowed.',403)
    return path

def load(path):
    path=safe_path(path);require(path.is_file(),'SETUP_REQUIRED','Install the local launcher first.',503)
    require(path.stat().st_size<=16384,'SETUP_REQUIRED','Invalid deployment descriptor.',503)
    value=json.loads(path.read_text(encoding='utf-8'))
    require(value.get('schema_version')==1 and value.get('owner_sid')==owner_sid(),'SETUP_REQUIRED','Deployment belongs to another owner or version.',503)
    UUID(value['deployment_id']);base=path.parent
    require(set(value)=={'schema_version','deployment_id','owner_sid','python','source_root','config','bundle','auth_initialized','auth_schema_version'},'SETUP_REQUIRED','Invalid deployment descriptor fields.',503)
    for name in ('config','bundle'):
        p=safe_path(value[name]);require(p.parent==base,'FORBIDDEN','Deployment files must remain contained.',403)
    require(Path(value['python']).is_file() and Path(value['source_root']).is_dir(),'SETUP_REQUIRED','Repair the moved application installation.',503)
    cfg=load_config(value['config']);safe_path(cfg.auth_store)
    require(Path(cfg.auth_store).parent==base and value['auth_initialized'] and value['auth_schema_version']==1,'SETUP_REQUIRED','Credential store initialization is required.',503)
    require(Path(cfg.auth_store).is_file(),'SETUP_REQUIRED','Preserve and repair the missing credential store.',503)
    value['path']=str(path);return value,cfg

def initialize(path,python=None,source_root=None,data_root=None,port=8765,publish=True,config=None):
    from .credentials import Credentials
    path=safe_path(path);require(not path.exists(),'ALREADY_EXISTS','Deployment already exists.',409)
    root=path.parent;root.mkdir(parents=True,exist_ok=True);protect_path(root)
    require(not any((root/n).exists() for n in ('config.json','auth.sqlite','secrets.bin')),'SETUP_REQUIRED','Preserve existing setup files and inspect before retrying.',409)
    cfg=Config(auth_store=str(root/'auth.sqlite'),data_root=str(safe_path(data_root or root.parent/'data')),local_storage_confirmed=True,managed_idle=True,port=port)
    if config is not None:
        cfg=config.model_copy(update={'auth_store':str(root/'auth.sqlite'),'managed_idle':True})
    Credentials(Path(cfg.auth_store),initialize=True);protect_path(Path(cfg.auth_store))
    save_bundle(root/'secrets.bin',{'version':1,'control_key':secrets.token_urlsafe(32),'tokens':{}})
    atomic_json(root/'config.json',cfg.model_dump(mode='json'))
    value={'schema_version':1,'deployment_id':str(uuid4()),'owner_sid':owner_sid(),'python':str(Path(python or sys.executable).resolve()),'source_root':str(Path(source_root or Path(__file__).resolve().parents[1]).resolve()),'config':str(root/'config.json'),'bundle':str(root/'secrets.bin'),'auth_initialized':True,'auth_schema_version':1}
    if publish:atomic_json(path,value)
    return value

def fingerprint(value,cfg):
    return hashlib.sha256(encode({'deployment_id':value['deployment_id'],'config':cfg.model_dump(mode='json')}).encode()).hexdigest()
def signature(key,payload):return hmac.new(key.encode(),encode(payload).encode(),hashlib.sha256).hexdigest()

def probe(value,cfg,key):
    nonce=secrets.token_urlsafe(32);conn=http.client.HTTPConnection('127.0.0.1',cfg.port,timeout=3)
    try:
        conn.request('GET','/api/v1/service/identity?nonce='+nonce)
        r=conn.getresponse();raw=r.read(8193)
        require(r.status==200 and len(raw)<=8192,'PORT_CONFLICT','An unrecognized service occupies the configured port.',503)
        try:payload=json.loads(raw);mac=payload.pop('mac')
        except (ValueError,KeyError,TypeError):raise Fault('PORT_CONFLICT','An unrecognized service occupies the configured port.',503) from None
        require(payload.get('nonce')==nonce and payload.get('deployment_id')==value['deployment_id'] and payload.get('configuration')==fingerprint(value,cfg) and payload.get('version')==1 and hmac.compare_digest(signature(key,payload),mac),'PORT_CONFLICT','The local listener does not match this deployment.',503)
        return payload
    except ConnectionRefusedError:return None
    except (TimeoutError,ConnectionResetError,ConnectionAbortedError,http.client.HTTPException):raise Fault('SERVICE_UNAVAILABLE','The local listener is not ready.',503) from None
    finally:conn.close()

@contextmanager
def coordinator(value,timeout=30):
    from .api import InstanceLock
    lock=InstanceLock(Path(value['path']).parent/'.launch.lock');deadline=time.monotonic()+timeout
    while True:
        try:lock.acquire();break
        except Fault:
            require(time.monotonic()<deadline,'SERVICE_UNAVAILABLE','Another launch or administration operation is busy.',503);time.sleep(.1)
    try:yield
    finally:lock.release()

def ensure(path):
    value,cfg=load(path);bundle=read_bundle(Path(value['bundle']));started=False
    deadline=time.monotonic()+30
    with coordinator(value):
        state=probe(value,cfg,bundle['control_key'])
        while state and state['state']=='DRAINING':
            require(time.monotonic()<deadline,'SERVICE_UNAVAILABLE','Service is still stopping.',503);time.sleep(.1);state=probe(value,cfg,bundle['control_key'])
        if state is None:
            python=Path(value['python']);hidden=python.with_name('pythonw.exe')
            require(hidden.is_file(),'SETUP_REQUIRED','A windowless Python interpreter is required.',503)
            env=dict(os.environ)
            for key in list(env):
                if key.startswith(('DT_','CALAMUM_')):env.pop(key)
            env['PYTHONPATH']=value['source_root']
            subprocess.Popen([str(hidden),'-m','decision_tracker.managed','--deployment',value['path']],cwd=value['source_root'],env=env,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=0x00000008|0x00000200,close_fds=True)
            started=True
        while state is None or state['state']!='RUNNING':
            require(time.monotonic()<deadline,'SERVICE_UNAVAILABLE','Startup did not become ready; inspect local lifecycle diagnostics.',503)
            time.sleep(.1);state=probe(value,cfg,bundle['control_key'])
        return {'started':started,'deployment_id':value['deployment_id'],'instance_id':state['instance_id'],'base_url':f'http://127.0.0.1:{cfg.port}/','ready':True}

def open_app(path):
    result=ensure(path)
    import webbrowser
    webbrowser.open(result['base_url'],new=2)
    return result

def local_admin(path,operation,**args):
    value,cfg=load(path)
    with coordinator(value):
        try:return admin_request(value['deployment_id'],operation,**args)
        except OSError as exc:
            # Only a missing pipe permits an attempt to acquire the offline writer lock.
            if exc.errno not in (2,3):raise Fault('SERVICE_UNAVAILABLE','Local administration is unavailable.',503) from None
        from .api import InstanceLock
        from .credentials import Credentials
        from .administration import dispatch
        root=cfg.root;root.mkdir(parents=True,exist_ok=True);lock=InstanceLock(root/'.service.lock');lock.acquire()
        try:return dispatch(value,cfg,Credentials(Path(cfg.auth_store)),None,operation,args)
        finally:lock.release()

def install_protocol(path):
    import winreg
    value,cfg=load(path);key_path=r'Software\Classes\decision-tracker'
    python=Path(value['python']).with_name('pythonw.exe')
    # The handler accepts exactly two positional arguments; injected extra args fail closed.
    handler=Path(value['source_root'])/'decision_tracker'/'protocol.py'
    command=f'"{python}" "{handler}" "{value["path"]}" "%1"'
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,key_path+r'\shell\open\command') as k:prior=winreg.QueryValueEx(k,'')[0]
    except FileNotFoundError:prior=None
    receipt=Path(value['path']).parent/'protocol-registration.json'
    if prior is not None:
        known=json.loads(receipt.read_text()) if receipt.exists() else {}
        require(prior==command or prior==known.get('command'),'REGISTRATION_CONFLICT','An unrelated protocol handler already exists.',409)
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER,key_path) as k:
        winreg.SetValueEx(k,'',0,winreg.REG_SZ,'URL:Decision Tracker');winreg.SetValueEx(k,'URL Protocol',0,winreg.REG_SZ,'')
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER,key_path+r'\shell\open\command') as k:winreg.SetValueEx(k,'',0,winreg.REG_SZ,command)
    atomic_json(receipt,{'command':command,'deployment_id':value['deployment_id'],'previous_command':prior})
    return {'registered':True,'uri':'decision-tracker://open','deployment':value['path']}

def uninstall_protocol(path):
    import winreg
    value,_=load(path);receipt=Path(value['path']).parent/'protocol-registration.json';require(receipt.exists(),'NOT_FOUND','No owned registration receipt.',404)
    saved=json.loads(receipt.read_text());base=r'Software\Classes\decision-tracker'
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER,base+r'\shell\open\command') as key:current=winreg.QueryValueEx(key,'')[0]
    require(current==saved['command'],'REGISTRATION_CONFLICT','Handler changed; preserve it for review.',409)
    for suffix in (r'\shell\open\command',r'\shell\open',r'\shell',''):winreg.DeleteKey(winreg.HKEY_CURRENT_USER,base+suffix)
    return {'unregistered':True,'data_preserved':True}
