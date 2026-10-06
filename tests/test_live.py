import asyncio
from uuid import uuid4
import pytest
from conftest import change
from decision_tracker.live import Hub
from decision_tracker.models import Change
from decision_tracker.errors import Fault

def test_commit_notification_is_after_commit_and_failure_cannot_undo(ledger):
 s,p,u=ledger;seen=[]
 def wake(project):
  seen.append(s.event_snapshot(project,u,p)['ledger_revision'])
  raise RuntimeError('Injected notifier failure')
 s.on_commit=wake
 req=Change(expected_ledger_uuid=u,expected_revision=0,request_id=uuid4(),reason='Notification verification',operations=[{'op':'decision.create','data':{'title':'One','question':'Why?'}}])
 assert s.change('alpha',p,req)['revision']==1
 assert seen==[1]
 assert s.change('alpha',p,req)['replayed'];assert seen==[1]
 change(s,p,u,[{'op':'decision.edit','key':'D000001','data':{'title':'Dry'}}],1,{'D000001':1},validate_only=True)
 assert seen==[1]
 assert s.event_snapshot('alpha',u,p,'D000001')['decision_revision']==1

def test_context_fingerprint_matches_and_unrelated_record_stays_current(ledger):
 s,p,u=ledger
 change(s,p,u,[{'op':'decision.create','data':{'title':'One','question':'Why?'}}])
 first=s.event_snapshot('alpha',u,p,'D000001')
 assert first['context_fingerprint']==s.related('alpha',u,p,'D000001')['data']['context_fingerprint']
 change(s,p,u,[{'op':'decision.create','data':{'title':'Two','question':'Why?'}}],1)
 second=s.event_snapshot('alpha',u,p,'D000001')
 assert second['ledger_revision']==2 and second['decision_revision']==1
 assert second['context_fingerprint']==first['context_fingerprint']
 with pytest.raises(Fault):s.event_snapshot('alpha',str(uuid4()),p)

def test_hub_latest_state_caps_and_cleanup(ledger):
 s,p,u=ledger
 async def run():
  hub=Hub(s);clients=[await hub.add('alpha',u,p,None,lambda:p) for _ in range(8)]
  with pytest.raises(Fault) as exc:await hub.add('alpha',u,p,None,lambda:p)
  assert exc.value.status==429
  client=clients[0];assert client['queue'].qsize()==1
  await asyncio.to_thread(change,s,p,u,[{'op':'decision.create','data':{'title':'One','question':'Why?'}}])
  deadline=asyncio.get_running_loop().time()+3
  while client['last']['ledger_revision']!=1 and asyncio.get_running_loop().time()<deadline:await asyncio.sleep(.02)
  assert client['last']['ledger_revision']==1 and client['queue'].qsize()==1
  await hub.close();assert not hub.groups and sum(hub.counts.values())==0
 asyncio.run(run())

def test_stream_session_checks_do_not_extend_idle(client):
 auth=client.app.state.auth;sid,session=auth.login(client.token);before=session['seen']
 assert auth.session(sid,touch=False)['seen']==before
 session['seen']-=5401
 with pytest.raises(Fault):auth.session(sid,touch=False)

def test_event_endpoint_rejects_missing_identity_and_invalid_key(client):
 from test_api import setup_project
 setup_project(client)
 assert client.get('/api/v1/projects/alpha/events?decision_key=bad').status_code==422
 client.headers.pop('X-Ledger-UUID')
 assert client.get('/api/v1/projects/alpha/events').status_code==422


def test_service_wide_stream_limit(ledger):
 from dataclasses import replace
 s,p,u=ledger
 async def run():
  hub=Hub(s)
  for i in range(32):
   actor=replace(p,id='actor'+str(i))
   await hub.add('alpha',u,actor,None,lambda actor=actor:actor)
  with pytest.raises(Fault) as exc:await hub.add('alpha',u,replace(p,id='extra'),None,lambda:p)
  assert exc.value.status==429
  await hub.close();assert sum(hub.counts.values())==0
 asyncio.run(run())

def test_blocked_network_send_is_bounded():
 from decision_tracker.live import BoundedStream
 async def run():
  async def blocked(message):await asyncio.Event().wait()
  async def source():yield ': heartbeat\n\n'
  stream=BoundedStream(source(),media_type='text/event-stream')
  started=asyncio.get_running_loop().time()
  with pytest.raises(TimeoutError):await stream.stream_response(blocked)
  assert asyncio.get_running_loop().time()-started<12
 asyncio.run(run())
