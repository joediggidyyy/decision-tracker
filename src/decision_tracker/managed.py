"""Windowless managed service entry point. No credential or request-body diagnostics."""
import argparse,base64,json,logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
import threading,time
from fastapi import Query
from .deployment import load,fingerprint,signature
from .windows_local import read_bundle,AdminPipe
from .credentials import Credentials
from .administration import dispatch,recover_token_journal
from .api import create_app

def run(path):
    value,cfg=load(path);bundle=read_bundle(Path(value['bundle']))
    store=Credentials(Path(cfg.auth_store));recover_token_journal(value,store)
    logger=logging.getLogger('decision_tracker.lifecycle');logger.setLevel(logging.INFO)
    handler=RotatingFileHandler(Path(value['path']).parent/'lifecycle.log',maxBytes=1024*1024,backupCount=2,encoding='utf-8');logger.addHandler(handler)
    app=create_app(cfg);life=app.state.lifecycle
    @app.get('/api/v1/service/identity')
    def identity(nonce:str=Query(pattern=r'^[A-Za-z0-9_-]{43}$')):
        from .errors import require
        require(len(base64.urlsafe_b64decode(nonce+'='))==32,'VALIDATION_ERROR','Invalid challenge.')
        payload={'version':1,'nonce':nonce,'deployment_id':value['deployment_id'],'configuration':fingerprint(value,cfg),'instance_id':life.instance_id,'state':life.state}
        return {**payload,'mac':signature(bundle['control_key'],payload)}
    import uvicorn
    server=uvicorn.Server(uvicorn.Config(app,host='127.0.0.1',port=cfg.port,workers=1,access_log=False,proxy_headers=False,log_config=None,timeout_graceful_shutdown=5))
    app.state.shutdown=lambda:setattr(server,'should_exit',True)
    def call(request):
        return dispatch(value,cfg,app.state.auth.store,life,request['operation'],{k:v for k,v in request.items() if k not in ('operation','version','deployment_id')})
    pipe=AdminPipe(value['deployment_id'],call)
    try:
        pipe.start();logger.info('instance=%s state=STARTING',life.instance_id)
        def startup_watch():
            time.sleep(30)
            if not server.started:server.should_exit=True
        threading.Thread(target=startup_watch,daemon=True).start()
        server.run();logger.info('instance=%s state=STOPPED',life.instance_id)
    except Exception:logger.error('state=FAILED code=LOCAL_STARTUP_FAILED');raise
    finally:pipe.close();handler.close();logger.removeHandler(handler)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--deployment',required=True);args=parser.parse_args()
    run(args.deployment)
