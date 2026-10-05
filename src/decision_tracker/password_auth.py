"""Human password sessions with durable epoch revocation and separate agent bearer auth."""
import secrets,time,threading
from .auth import Principal
from .errors import require

class PasswordAuth:
    def __init__(self,config,store):
        self.store=store;self.lock=threading.RLock();self.sessions={};self.preauth={};self.pre_requests=[]
        self.principals={p.id:Principal(p.id,frozenset(p.projects),frozenset(p.capabilities)) for p in config.principals}
        require(len(self.principals)==len(config.principals),'AUTH_CONFIG_INVALID','Principal IDs must be unique.',503)
        require('operator' in self.principals,'AUTH_CONFIG_INVALID','Configure the operator principal.',503)
    def bearer(self,token):
        name=self.store.token_principal(token)
        require(name!='operator' and name in self.principals,'UNAUTHORIZED','Authentication failed.',401)
        return self.principals[name]
    def new_session(self,epoch):
        with self.lock:
            tick=time.monotonic()
            self.sessions={k:v for k,v in self.sessions.items() if tick-v['seen']<1800 and tick-v['created']<28800 and v['epoch']==epoch}
            require(len(self.sessions)<256,'RETRY_LATER','Session capacity reached.',503)
            sid=secrets.token_urlsafe(32);session={'principal':self.principals['operator'],'csrf':secrets.token_urlsafe(32),'epoch':epoch,'created':tick,'seen':tick}
            self.sessions[sid]=session;return sid,session
    def login(self,password):return self.new_session(self.store.check_password(password))
    def session(self,sid,touch=True):
        state=self.store.state()
        with self.lock:
            value=self.sessions.get(sid);tick=time.monotonic()
            require(value and state['state']=='active' and value['epoch']==state['epoch'] and tick-value['seen']<1800 and tick-value['created']<28800,'UNAUTHORIZED','Sign in again.',401)
            if touch:value['seen']=tick
            return value
    def logout(self,sid):
        with self.lock:self.sessions.pop(sid,None)
    def challenge(self):
        with self.lock:
            tick=time.monotonic();self.pre_requests=[x for x in self.pre_requests if tick-x<60];self.preauth={k:v for k,v in self.preauth.items() if tick-v[1]<300}
            require(len(self.pre_requests)<60 and len(self.preauth)<64,'RATE_LIMITED','Try sign-in again later.',429)
            self.pre_requests.append(tick);sid=secrets.token_urlsafe(32);csrf=secrets.token_urlsafe(32);self.preauth[sid]=(csrf,tick)
            return sid,csrf
    def precheck(self,sid,csrf):
        with self.lock:
            value=self.preauth.get(sid)
            require(value and time.monotonic()-value[1]<300 and secrets.compare_digest(value[0],csrf),'FORBIDDEN','Reload sign-in before continuing.',403)
    def consume(self,sid):
        with self.lock:self.preauth.pop(sid,None)
