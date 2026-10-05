"""Request admission and idle shutdown share one mutex; no timer can kill active work."""
import threading,time
from uuid import uuid4
from .errors import require

class Lifecycle:
    def __init__(self,minutes=90,enabled=False,clock=time.monotonic):
        self.lock=threading.RLock();self.clock=clock;self.timeout=minutes*60;self.enabled=enabled
        self.last=clock();self.active=0;self.state='STARTING';self.leases={};self.instance_id=str(uuid4())
    def start(self):
        with self.lock:self.state='RUNNING';self.last=self.clock()
    def enter(self,touch=True):
        with self.lock:
            require(self.state=='RUNNING','SERVICE_STOPPING','Service is stopping; start it again.',503)
            self.active+=1
            if touch:self.last=self.clock()
    def leave(self,touch=True):
        with self.lock:
            self.active-=1
            if touch:self.last=self.clock()
    def sweep(self,valid=lambda lease:True):
        now=self.clock()
        for key,lease in list(self.leases.items()):
            if lease['expires']<=now or not valid(lease):self.leases.pop(key);self.last=now
    def status(self):
        with self.lock:
            self.sweep()
            return {'state':self.state,'idle_seconds_remaining':max(0,int(self.timeout-(self.clock()-self.last))),
                    'operation_count':self.active,'lease_count':len(self.leases),'instance_id':self.instance_id}
    def stop(self,explicit=False,valid=lambda lease:True):
        with self.lock:
            self.sweep(valid)
            busy=self.active or self.leases
            if explicit:require(not busy,'SERVICE_BUSY','Active operations or drafts prevent shutdown.',409)
            if self.state=='RUNNING' and not busy and (explicit or self.enabled and self.clock()-self.last>=self.timeout):
                self.state='DRAINING';return True
            return False
    def lease(self,sid,project,uuid,tab,key=None):
        with self.lock:
            self.sweep()
            require(self.state=='RUNNING','SERVICE_STOPPING','Service is stopping.',503)
            if key:
                lease=self.leases.get(key)
                require(lease and (lease['sid'],lease['project'],lease['uuid'],lease['tab'])==(sid,project,uuid,tab),'NOT_FOUND','Lease unavailable.',404)
            else:
                require(len(self.leases)<32 and sum(x['sid']==sid for x in self.leases.values())<8,'RATE_LIMITED','Draft protection capacity reached.',429)
                key=str(uuid4());self.last=self.clock()
            self.leases[key]={'sid':sid,'project':project,'uuid':uuid,'tab':tab,'expires':self.clock()+180}
            return {'lease_id':key,'expires_in_seconds':180,'idle_timeout_seconds':self.timeout}
    def release(self,sid,key):
        with self.lock:
            require(key in self.leases and self.leases[key]['sid']==sid,'NOT_FOUND','Lease unavailable.',404)
            self.leases.pop(key);self.last=self.clock()
