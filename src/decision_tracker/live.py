"""Bounded latest-state notifications; the ledger remains the durable authority."""
import asyncio
import json
from collections import Counter
from fastapi.responses import StreamingResponse
from .errors import Fault

class BoundedStream(StreamingResponse):
    async def stream_response(self, send):
        async def bounded(message):
            await asyncio.wait_for(send(message),10)
        await super().stream_response(bounded)

class Hub:
    def __init__(self, service):
        self.service=service;self.groups={};self.counts=Counter();self.loop=None
        service.on_commit=self.notify

    def notify(self,project):
        if self.loop and not self.loop.is_closed():
            self.loop.call_soon_threadsafe(self._wake,project)

    def _wake(self,project):
        if project in self.groups:self.groups[project]['wake'].set()

    async def add(self,project,uuid,principal,key,authorize):
        self.loop=asyncio.get_running_loop()
        if sum(self.counts.values())>=32 or self.counts[principal.id]>=8:
            raise Fault('STREAM_LIMIT','Too many live connections.',429)
        # Register first; the initial snapshot and queued wake cover the subscribe race.
        group=self.groups.setdefault(project,{'wake':asyncio.Event(),'clients':[],'task':None})
        client={'uuid':uuid,'principal':principal,'key':key,'authorize':authorize,'queue':asyncio.Queue(1),'last':None}
        group['clients'].append(client);self.counts[principal.id]+=1
        try:
            authorize()
            initial=await asyncio.to_thread(self.service.event_snapshot,project,uuid,principal,key)
            client['queue'].put_nowait(initial);client['last']=initial
            if group['task'] is None:group['task']=asyncio.create_task(self._pump(project,group))
            return client
        except BaseException:
            await self.remove(project,client);raise

    async def remove(self,project,client):
        group=self.groups.get(project)
        if not group or client not in group['clients']:return
        group['clients'].remove(client);self.counts[client['principal'].id]-=1
        if not group['clients']:
            self.groups.pop(project,None)
            if group['task']:
                group['task'].cancel()
                await asyncio.gather(group['task'],return_exceptions=True)

    @staticmethod
    def offer(client,value):
        queue=client['queue']
        if queue.full():queue.get_nowait()
        queue.put_nowait(value)

    async def _pump(self,project,group):
        while True:
            try:await asyncio.wait_for(group['wake'].wait(),5)
            except TimeoutError:pass
            group['wake'].clear()
            await asyncio.sleep(.25)
            cache={}
            for client in list(group['clients']):
                try:
                    principal=client['authorize']();principal.need('read');principal.project(project)
                    key=(client['uuid'],principal.id,client['key'])
                    if key not in cache:
                        cache[key]=await asyncio.to_thread(self.service.event_snapshot,project,client['uuid'],principal,client['key'])
                    value=cache[key]
                    if value!=client['last']:self.offer(client,value);client['last']=value
                except Exception:
                    self.offer(client,{'terminal':True})

    async def events(self,project,client):
        try:
            while True:
                try:value=await asyncio.wait_for(client['queue'].get(),15)
                except TimeoutError:
                    client['authorize']()
                    yield ': heartbeat\n\n';continue
                if value.get('stopping'):
                    yield 'event: service-stopping\ndata: {}\n\n';return
                if value.get('terminal'):
                    yield 'event: unavailable\ndata: {}\n\n';return
                client['authorize']()
                payload=json.dumps(value,separators=(',',':'))
                if len(payload.encode())>8192:return
                yield f'id: {value["ledger_revision"]}\nevent: state\ndata: {payload}\n\n'
        except Fault:
            yield 'event: unavailable\ndata: {}\n\n'
        finally:await self.remove(project,client)

    async def close(self,stopping=False):
        for project,group in list(self.groups.items()):
            for client in list(group['clients']):
                if stopping:self.offer(client,{'stopping':True})
                await self.remove(project,client)
