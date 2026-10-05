"""Disposable native browser observation host; never loads owner credentials/data."""
import json,threading,time
from pathlib import Path
from uuid import uuid4
import uvicorn
from starlette.responses import Response,JSONResponse
from decision_tracker.api import create_app
from decision_tracker.config import Config
from decision_tracker.credentials import Credentials
from decision_tracker.auth import Principal
from decision_tracker.models import Change,ProjectChange

root=Path(__file__).resolve().parents[1];local=root/'.local/decision-form-browser';local.mkdir(parents=True)
credentials=Credentials(local/'auth.sqlite',initialize=True)
password='Synthetic form observation 2026 only'
credentials.redeem('bootstrap',credentials.issue('bootstrap'),password,password)
app=create_app(Config(data_root=str(local/'data'),auth_store=str(credentials.path),local_storage_confirmed=True,port=8766))
control=local/'fault.json'
@app.middleware('http')
async def controlled_fault(request,call_next):
    fault=json.loads(control.read_text(encoding='utf-8-sig')) if control.exists() else {}
    if request.url.path.endswith('/changes') and request.method=='POST' and fault.get('mode')=='lost-response' and fault.get('remaining',0)>0:
        response=await call_next(request)
        if response.status_code==200:
            fault['remaining']-=1;control.write_text(json.dumps(fault),encoding='utf-8')
            return Response('intentionally interrupted JSON',status_code=200,media_type='application/json')
        return response
    if request.url.path.endswith('/changes') and request.method=='POST' and fault.get('mode')=='refresh-failure':
        response=await call_next(request)
        if response.status_code==200:control.write_text(json.dumps({'mode':'fail-next-read'}),encoding='utf-8')
        return response
    if request.method=='GET' and '/decisions' in request.url.path and fault.get('mode')=='fail-next-read':
        control.write_text('{}',encoding='utf-8')
        return JSONResponse({'error':{'code':'INTERNAL_ERROR','message':'Injected refresh failure'}},status_code=500)
    return await call_next(request)
p=Principal('operator',frozenset({'*'}),frozenset({'read','write','decide','maintain','registry'}))
s=app.state.service;project=s.catalog.mutate(p,ProjectChange(project_id='form-review',name='Disposable form review',expected_catalog_revision=0,request_id=uuid4()))['data'];u=project['ledger_uuid']
ops=[]
for title in ('Choose storage','Record a written answer','Record an earlier approval','Review proposal eligibility'):
    ref=str(len(ops));ops.append({'op':'decision.create','client_ref':ref,'data':{'title':title,'question':'Which storage approach should this example use?'}})
    if title=='Choose storage':
        for name,description in [('Use local storage','Store active ledgers on the local drive.'),('Use a dedicated local volume','Store active ledgers on a separate local disk.')]:
            ops.append({'op':'option.add','key':'@'+ref,'data':{'title':name,'description':description,'benefit':'Reliable local locking','cost':'Keep verified backups separately'}})
    if title=='Review proposal eligibility':
        ops.extend([{'op':'option.add','key':'@'+ref,'data':{'title':'Only eligible proposal','description':'Long explanation. '*80,'benefit':'Visible details','cost':'Review the complete text'}},
                    {'op':'option.add','key':'@'+ref,'data':{'title':'Rejected proposal','disposition':'rejected','reason':'Rejected in the synthetic fixture'}},
                    {'op':'option.add','key':'@'+ref,'data':{'title':'Retired proposal','disposition':'retired'}}])
s.change('form-review',p,Change(expected_ledger_uuid=u,expected_revision=0,request_id=uuid4(),reason='Disposable form fixtures',authority_refs=['Synthetic fixture authority'],operations=ops))
server=uvicorn.Server(uvicorn.Config(app,host='127.0.0.1',port=8766,access_log=False,log_level='warning',timeout_graceful_shutdown=5));thread=threading.Thread(target=server.run,daemon=True);thread.start()
receipt=local/'observations.json'
try:
    deadline=time.monotonic()+900
    print(json.dumps({'url':'http://127.0.0.1:8766','receipt':str(receipt)}),flush=True)
    while thread.is_alive() and not receipt.exists() and time.monotonic()<deadline:time.sleep(.25)
    assert receipt.exists(),'Actual browser observations missing'
    result=json.loads(receipt.read_text(encoding='utf-8'))
    assert all(item['passed'] and item['observation'] for item in result['scenarios'].values())
    assert {'proposal','manual','historical','dirty-preservation','keyboard','narrow','zoom'}<=set(result['scenarios'])
    print(json.dumps(result),flush=True)
finally:
    server.should_exit=True;thread.join(10);assert not thread.is_alive()
