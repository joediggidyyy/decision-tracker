"""Bounded native empirical review of password UI, with disposable credentials only."""
import json,threading,time
from pathlib import Path
import uvicorn
from decision_tracker.api import create_app
from decision_tracker.config import Config
from decision_tracker.credentials import Credentials
root=Path(__file__).resolve().parents[1];local=root/'.local';local.mkdir(exist_ok=True)
store=Credentials(local/'auth.sqlite',initialize=True)
code=store.issue('bootstrap')
store.redeem('bootstrap',code,'Synthetic browser password 2026 only','Synthetic browser password 2026 only')
app=create_app(Config(data_root=str(local/'browser-data'),auth_store=str(store.path),local_storage_confirmed=True))
server=uvicorn.Server(uvicorn.Config(app,host='127.0.0.1',port=8765,access_log=False,log_level='warning',timeout_graceful_shutdown=5))
thread=threading.Thread(target=server.run,daemon=True);thread.start()
receipt=local/'account-browser-review.json'
try:
    deadline=time.monotonic()+900
    while not receipt.exists() and thread.is_alive() and time.monotonic()<deadline:time.sleep(.25)
    assert receipt.exists(),'Actual browser observations missing'
    result=json.loads(receipt.read_text())
    assert set(result['scenarios'])=={'login','account-placement','password-form','draft-retention','narrow'}
    assert all(v['passed'] and v['observation'] for v in result['scenarios'].values())
    print(json.dumps(result))
finally:
    server.should_exit=True;thread.join(10)
    assert not thread.is_alive(),'Browser service did not stop'
