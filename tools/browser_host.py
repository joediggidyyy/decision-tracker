"""Native Calamum empirical lane: run the actual app until observations arrive."""
import hashlib,json,threading,time
from pathlib import Path
import uvicorn
from fastapi.responses import FileResponse
from decision_tracker.api import create_app
from decision_tracker.config import Config,PrincipalConfig
root=Path(__file__).resolve().parents[1]
local=root/".local";local.mkdir(exist_ok=True)
# Synthetic credential grants access only to this isolated, disposable proof data.
token="synthetic-browser-only-20261005-do-not-use-in-production"
app=create_app(Config(data_root=str(local/"browser-data"),local_storage_confirmed=True,principals=[
 PrincipalConfig(id="browser-review",token_env="DT_REVIEW_TOKEN",projects=["*"],capabilities=["read","write","decide","maintain","registry"])
]),{"DT_REVIEW_TOKEN":token})
@app.get("/home-preview",include_in_schema=False)
def home():return FileResponse(local/"home-integration/home-preview.html")
@app.get("/preview/home.css",include_in_schema=False)
def css():return FileResponse(local/"home-integration/home.css",media_type="text/css")
server=uvicorn.Server(uvicorn.Config(app,host="127.0.0.1",port=8765,access_log=False,log_level="warning",timeout_graceful_shutdown=5))
thread=threading.Thread(target=server.run,daemon=True);thread.start()
receipt=local/"browser-review.json"
try:
 deadline=time.monotonic()+1500
 while not receipt.exists() and thread.is_alive() and time.monotonic()<deadline:time.sleep(.25)
 assert receipt.exists(),"Actual browser observation receipt is missing."
 result=json.loads(receipt.read_text())
 assert result["reviewer"] and result["browser"] and result["observed_at"]
 required={"create","edit","close","history","projects","validation","conflict","keyboard","narrow","zoom","inert-script","home-launch","shell"}
 assert set(result["scenarios"])==required
 assert all(v["passed"] is True and v["observation"] for v in result["scenarios"].values())
 for shot in result["screenshots"]:
  path=local/shot["file"]
  assert path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest()==shot["sha256"]
 assert len(result["screenshots"])>=3
 print(json.dumps({"observed_scenarios":len(required),"browser":result["browser"],"screenshots":len(result["screenshots"])}))
finally:
 server.should_exit=True;thread.join(10)
 assert not thread.is_alive(),"Browser service did not stop."
