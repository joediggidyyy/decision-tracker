"""Durable local credentials. Secret material is never included in errors or audit rows."""
import base64
from contextlib import contextmanager
import hashlib
import hmac
import json
import secrets
import sqlite3
import threading
import time
import unicodedata
from uuid import uuid4
from .errors import Fault, require

_KDF_WORK = threading.BoundedSemaphore(1)
_KDF_QUEUE = threading.BoundedSemaphore(5)

def password_valid(value):
    require(isinstance(value,str) and 15 <= len(value) <= 128 and len(value.encode('utf-8')) <= 512
            and not any(unicodedata.category(c).startswith('C') for c in value),
            'PASSWORD_POLICY','Use 15–128 characters without control characters.')

def derive(value,salt):
    require(_KDF_QUEUE.acquire(False),'RETRY_LATER','Credential verification is busy.',503)
    acquired=False
    try:
        acquired=_KDF_WORK.acquire(timeout=5)
        require(acquired,'RETRY_LATER','Credential verification is busy.',503)
        return hashlib.scrypt(value.encode('utf-8'),salt=salt,n=131072,r=8,p=1,dklen=32,maxmem=256*1024*1024)
    finally:
        if acquired:_KDF_WORK.release()
        _KDF_QUEUE.release()

def hash_password(value):
    password_valid(value)
    salt=secrets.token_bytes(16)
    return 'scrypt-v1$131072$8$1$'+salt.hex()+'$'+derive(value,salt).hex()

def verify_password(value,encoded):
    try:
        a,n,r,p,salt,digest=encoded.split('$')
        if (a,n,r,p)!=('scrypt-v1','131072','8','1') or len(salt)!=32 or len(digest)!=64:return False
        if not isinstance(value,str) or len(value.encode('utf-8'))>512:return False
        return hmac.compare_digest(derive(value,bytes.fromhex(salt)),bytes.fromhex(digest))
    except (ValueError,AttributeError):return False

def digest(value):return hashlib.sha256(value.encode('utf-8')).hexdigest()

class Credentials:
    def __init__(self,path,*,initialize=False,clock=time.time):
        self.path=path;self.clock=clock;self.lock=threading.RLock()
        require(path.exists() or initialize,'SETUP_REQUIRED','Initialize credentials using the local CLI.',503)
        if initialize:
            path.parent.mkdir(parents=True,exist_ok=True)
            with self.db() as db:
                db.executescript('''
                CREATE TABLE IF NOT EXISTS meta(version INTEGER NOT NULL,last_time REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS human(id TEXT PRIMARY KEY,state TEXT NOT NULL,hash TEXT,epoch INTEGER NOT NULL);
                CREATE TABLE IF NOT EXISTS codes(id TEXT PRIMARY KEY,purpose TEXT UNIQUE,hash TEXT NOT NULL,expires REAL NOT NULL,attempts INTEGER NOT NULL,consumed INTEGER NOT NULL);
                CREATE TABLE IF NOT EXISTS tokens(id TEXT PRIMARY KEY,principal TEXT NOT NULL,hash TEXT NOT NULL UNIQUE,state TEXT NOT NULL,created REAL NOT NULL,revoked REAL);
                CREATE TABLE IF NOT EXISTS failures(at REAL NOT NULL,kind TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY,at REAL NOT NULL,kind TEXT NOT NULL,actor TEXT NOT NULL,outcome TEXT NOT NULL,epoch INTEGER NOT NULL);
                ''')
                if not db.execute('SELECT 1 FROM meta').fetchone():
                    db.execute('INSERT INTO meta VALUES(1,?)',(clock(),))
                    db.execute("INSERT INTO human VALUES('operator','uninitialized',NULL,0)")
        with self.db() as db:
            require(db.execute('SELECT version FROM meta').fetchone()[0]==1,'AUTH_SCHEMA_INVALID','Unsupported credential schema.',503)
            rows=db.execute('SELECT id,state,hash,epoch FROM human').fetchall()
            require(len(rows)==1 and rows[0]['id']=='operator' and rows[0]['state'] in ('uninitialized','active','recovery_pending') and isinstance(rows[0]['epoch'],int) and rows[0]['epoch']>=0,'AUTH_SCHEMA_INVALID','Invalid credential store.',503)
            require(rows[0]['state']!='active' or isinstance(rows[0]['hash'],str) and rows[0]['hash'].startswith('scrypt-v1$131072$8$1$'),'AUTH_SCHEMA_INVALID','Invalid password verifier.',503)

    @contextmanager
    def db(self):
        with self.lock:
            db=sqlite3.connect(self.path,timeout=5);db.row_factory=sqlite3.Row
            try:
                db.execute('PRAGMA secure_delete=ON');db.execute('BEGIN IMMEDIATE')
                yield db
                db.commit()
            except BaseException:db.rollback();raise
            finally:db.close()

    def now(self,db):
        previous=db.execute('SELECT last_time FROM meta').fetchone()[0];tick=self.clock()
        if tick<previous:db.execute('UPDATE codes SET consumed=1')
        tick=max(tick,previous);db.execute('UPDATE meta SET last_time=?',(tick,));return tick

    def event(self,db,kind,outcome='success',actor='operator'):
        epoch=db.execute('SELECT epoch FROM human').fetchone()[0]
        db.execute('INSERT INTO events(at,kind,actor,outcome,epoch) VALUES(?,?,?,?,?)',(self.now(db),kind,actor,outcome,epoch))

    def state(self):
        with self.db() as db:return dict(db.execute('SELECT state,epoch FROM human').fetchone())

    def _limited(self,db,kind):
        tick=self.now(db);db.execute('DELETE FROM failures WHERE at<=?',(tick-300,))
        count=db.execute('SELECT count(*) FROM failures WHERE kind=?',(kind,)).fetchone()[0]
        total=db.execute('SELECT count(*) FROM failures').fetchone()[0]
        require(count<5 and total<20,'RATE_LIMITED','Try again after the credential retry window.',429)

    def check_password(self,value):
        with self.db() as db:
            self._limited(db,'password');row=dict(db.execute('SELECT * FROM human').fetchone())
        good=row['state']=='active' and verify_password(value,row['hash'])
        with self.db() as db:
            current=db.execute('SELECT state,epoch FROM human').fetchone()
            good=good and current['state']=='active' and current['epoch']==row['epoch']
            if not good:
                db.execute('INSERT INTO failures VALUES(?,?)',(self.now(db),'password'));self.event(db,'password-check','failed')
        require(good,'UNAUTHORIZED','Authentication failed.',401)
        return row['epoch']

    def issue(self,purpose,supplied=None):
        require(purpose in ('bootstrap','recovery'),'VALIDATION_ERROR','Invalid code purpose.')
        if supplied is not None:
            require(purpose=='bootstrap' and supplied.isascii() and 20<=len(supplied)<=128 and not any(c.isspace() for c in supplied),'PASSWORD_POLICY','Temporary code does not meet policy.')
        raw=supplied or secrets.token_urlsafe(32)
        hashed=hash_password(raw) if supplied else 'sha256$'+digest(raw)
        with self.db() as db:
            state=db.execute('SELECT state FROM human').fetchone()[0]
            require(purpose!='bootstrap' or state=='uninitialized','AUTH_STATE_CONFLICT','Initial setup is unavailable.',409)
            if purpose=='recovery':
                require(state!='uninitialized','AUTH_STATE_CONFLICT','Use initial setup first.',409)
                db.execute("UPDATE human SET state='recovery_pending',epoch=epoch+1")
                db.execute('UPDATE codes SET consumed=1')
            db.execute('INSERT OR REPLACE INTO codes VALUES(?,?,?,?,0,0)',(str(uuid4()),purpose,hashed,self.now(db)+900))
            self.event(db,'code-issued-'+purpose)
        return raw

    def redeem(self,purpose,code,new,confirmation):
        password_valid(new);require(new==confirmation and new!=code,'PASSWORD_POLICY','Passwords must match and differ from the code.')
        with self.db() as db:
            self._limited(db,'code');tick=self.now(db)
            row=db.execute('SELECT * FROM codes WHERE purpose=?',(purpose,)).fetchone()
            candidate=dict(row) if row else None
            valid=bool(row and not row['consumed'] and row['attempts']<5 and row['expires']>tick)
        valid=valid and (hmac.compare_digest(candidate['hash'],'sha256$'+digest(code)) if candidate['hash'].startswith('sha256$') else verify_password(code,candidate['hash']))
        if not valid:
            with self.db() as db:
                db.execute('INSERT INTO failures VALUES(?,?)',(self.now(db),'code'))
                db.execute('UPDATE codes SET attempts=attempts+1,consumed=CASE WHEN attempts>=4 THEN 1 ELSE consumed END WHERE purpose=?',(purpose,))
            raise Fault('INVALID_CODE','Setup or recovery could not be completed.',400)
        hashed=hash_password(new)
        with self.db() as db:
            tick=self.now(db);row=db.execute('SELECT * FROM codes WHERE purpose=?',(purpose,)).fetchone()
            expected='uninitialized' if purpose=='bootstrap' else 'recovery_pending'
            require(row and row['id']==candidate['id'] and not row['consumed'] and row['expires']>tick and row['attempts']<5 and db.execute('SELECT state FROM human').fetchone()[0]==expected,'INVALID_CODE','Setup or recovery could not be completed.',400)
            db.execute("UPDATE human SET state='active',hash=?,epoch=epoch+1",(hashed,));db.execute('UPDATE codes SET consumed=1');self.event(db,'password-set-'+purpose)

    def change(self,current,new,confirmation,expected_epoch):
        epoch=self.check_password(current);require(epoch==expected_epoch,'AUTH_STATE_CONFLICT','Sign in again.',409)
        password_valid(new);require(new==confirmation and new!=current,'PASSWORD_POLICY','Passwords must match and differ from the current password.')
        hashed=hash_password(new)
        with self.db() as db:
            require(db.execute('SELECT epoch FROM human').fetchone()[0]==epoch,'AUTH_STATE_CONFLICT','Account changed; sign in again.',409)
            db.execute('UPDATE human SET hash=?,epoch=epoch+1',(hashed,));db.execute('UPDATE codes SET consumed=1');self.event(db,'password-changed')
        return epoch+1

    def revoke_sessions(self,current,epoch):
        require(self.check_password(current)==epoch,'AUTH_STATE_CONFLICT','Sign in again.',409)
        with self.db() as db:
            require(db.execute('SELECT epoch FROM human').fetchone()[0]==epoch,'AUTH_STATE_CONFLICT','Account changed.',409)
            db.execute('UPDATE human SET epoch=epoch+1');self.event(db,'sessions-revoked')
        return epoch+1

    def token_create(self,principal,raw=None,state='active'):
        raw=raw or secrets.token_urlsafe(32);key=str(uuid4())
        with self.db() as db:
            db.execute('INSERT INTO tokens VALUES(?,?,?,?,?,NULL)',(key,principal,digest(raw),state,self.now(db)));self.event(db,'token-created',actor=principal)
        return key,raw

    def token_principal(self,raw):
        with self.db() as db:row=db.execute("SELECT principal FROM tokens WHERE hash=? AND state='active'",(digest(raw),)).fetchone()
        require(row,'UNAUTHORIZED','Authentication failed.',401);return row['principal']

    def token_list(self):
        with self.db() as db:return [dict(r) for r in db.execute('SELECT id,principal,state,created FROM tokens ORDER BY created')]

    def token_revoke(self,key):
        with self.db() as db:
            require(db.execute('SELECT 1 FROM tokens WHERE id=?',(key,)).fetchone(),'NOT_FOUND','Token unavailable.',404)
            db.execute("UPDATE tokens SET state='revoked',revoked=? WHERE id=?",(self.now(db),key));self.event(db,'token-revoked')
