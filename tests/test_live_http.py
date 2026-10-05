import asyncio,json,secrets,socket,threading,time
from uuid import uuid4
import httpx
import uvicorn
from decision_tracker.api import create_app
from decision_tracker.config import Config,PrincipalConfig

def test_actual_http_stream_reconciles_write_and_closes_on_disabled_project(tmp_path):
 sock=socket.socket();sock.bind(('127.0.0.1',0));port=sock.getsockname()[1];token=secrets.token_urlsafe(36)
 app=create_app(Config(port=port,data_root=str(tmp_path/'live'),local_storage_confirmed=True,principals=[PrincipalConfig(id='stream',token_env='DT_STREAM_TOKEN',projects=['*'],capabilities=['read','write','registry'])]),{'DT_STREAM_TOKEN':token})
 server=uvicorn.Server(uvicorn.Config(app,host='127.0.0.1',port=port,access_log=False,log_level='error',timeout_graceful_shutdown=2))
 thread=threading.Thread(target=server.run,kwargs={'sockets':[sock]},daemon=True);thread.start();deadline=time.monotonic()+10
 while not server.started and time.monotonic()<deadline:time.sleep(.02)
 assert server.started
 async def run():
  async with httpx.AsyncClient(base_url=f'http://127.0.0.1:{port}',headers={'Authorization':'Bearer '+token},timeout=10) as c:
   result=await c.post('/api/v1/projects',json={'project_id':'alpha','name':'Alpha','expected_catalog_revision':0,'request_id':str(uuid4())});assert result.status_code==200
   c.headers['X-Ledger-UUID']=result.json()['data']['ledger_uuid']
   async with c.stream('GET','/api/v1/projects/alpha/events') as response:
    assert response.status_code==200 and response.headers['content-type'].startswith('text/event-stream')
    lines=response.aiter_lines()
    async def event():
     kind=None;data=None
     async for line in lines:
      if line.startswith('event:'):kind=line[6:].strip()
      if line.startswith('data:'):data=json.loads(line[5:])
      if line=='' and kind:return kind,data
    kind,initial=await event();assert kind=='state' and initial['ledger_revision']==0
    result=await c.post('/api/v1/projects/alpha/changes',json={'expected_ledger_uuid':c.headers['X-Ledger-UUID'],'expected_revision':0,'request_id':str(uuid4()),'reason':'Live HTTP','operations':[{'op':'decision.create','data':{'title':'Changed','question':'Why?'}}]});assert result.status_code==200
    kind,changed=await event();assert kind=='state' and changed['ledger_revision']==1
    result=await c.post('/api/v1/projects/alpha/state',json={'enabled':False,'expected_catalog_revision':1,'request_id':str(uuid4())});assert result.status_code==200
    kind,value=await event();assert kind=='unavailable' and value=={}
 try:asyncio.run(run())
 finally:server.should_exit=True;thread.join(10);sock.close()
 assert not thread.is_alive()

def test_reconciliation_repairs_lost_wakeup(ledger):
 from conftest import change
 from decision_tracker.live import Hub
 s,p,u=ledger
 async def run():
  hub=Hub(s);client=await hub.add('alpha',u,p,None,lambda:p);client['queue'].get_nowait();s.on_commit=lambda project:None
  await asyncio.to_thread(change,s,p,u,[{'op':'decision.create','data':{'title':'Durable','question':'Why?'}}])
  state=await asyncio.wait_for(client['queue'].get(),7);assert state['ledger_revision']==1
  await hub.close()
 asyncio.run(run())
