"""Offline, same-origin HTTP API for browser, CLI and agents."""
from contextlib import asynccontextmanager
from pathlib import Path
import hmac
import os
import sqlite3
from uuid import uuid4
from fastapi import FastAPI, Request, Query
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, FileResponse
from pydantic import ValidationError, Field
from .auth import Auth
from .config import Config, contained
from .errors import Fault, require
from .models import Model, Change, ProjectChange, ProjectState
from .service import Service

class Login(Model):
    token: str = Field(min_length=1,max_length=4096)

class InstanceLock:
    def __init__(self,path):self.path=path;self.file=None
    def acquire(self):
        self.file=self.path.open("a+b")
        try:
            self.file.seek(0,2)
            if self.file.tell()==0:self.file.write(b"0");self.file.flush()
            self.file.seek(0)
            if os.name=="nt":
                import msvcrt
                msvcrt.locking(self.file.fileno(),msvcrt.LK_NBLCK,1)
            else:
                import fcntl
                fcntl.flock(self.file,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except OSError:
            self.file.close();self.file=None
            raise Fault("SERVICE_ALREADY_RUNNING","Another service owns this data root.",503) from None
    def release(self):
        if self.file is not None:self.file.close();self.file=None

def create_app(config:Config,environment=None):
    from .lifecycle import Lifecycle
    from .credentials import Credentials
    from .password_auth import PasswordAuth
    # Legacy authentication is available only when a test injects an explicit environment.
    legacy=environment is not None and not config.auth_store
    require(legacy or config.auth_store,'SETUP_REQUIRED','Configure the credential store through local setup.',503)
    auth=Auth(config,environment) if legacy else PasswordAuth(config,Credentials(Path(config.auth_store)))
    life=Lifecycle(config.idle_timeout_minutes,config.managed_idle)
    root=config.root;root.mkdir(parents=True,exist_ok=True)
    lock=InstanceLock(contained(root,".service.lock"))
    service=Service(root)
    from .live import Hub, BoundedStream
    hub=Hub(service)
    origin=f"http://127.0.0.1:{config.port}"

    @asynccontextmanager
    async def lifespan(app):
        lock.acquire()
        try:
            # Interrupted artifact publication remains unavailable until explicitly recreated.
            with service.catalog.coordinator, __import__("decision_tracker.store",fromlist=["connect"]).connect(service.catalog.path) as catalog:
                from .store import connect
                for row in catalog.execute("SELECT db_path,ledger_uuid FROM projects WHERE enabled=1"):
                    with connect(contained(root,row["db_path"]),True) as ledger:
                        from .store import metadata
                        metadata(ledger,row["ledger_uuid"])
                        ledger.execute("UPDATE artifacts SET state='failed',error_code='INTERRUPTED' WHERE state='pending'")
            life.start()
            import asyncio
            async def idle_watch():
                while True:
                    await asyncio.sleep(1)
                    def valid(lease):
                        try:
                            p=auth.session(lease['sid'],touch=False)['principal']
                            service.event_snapshot(lease['project'],lease['uuid'],p,None)
                            return True
                        except Fault:return False
                    with life.lock:leases=list(life.leases.values())
                    snapshot_ids={id(lease) for lease in leases}
                    valid_ids={id(lease) for lease in leases if valid(lease)}
                    if life.stop(valid=lambda lease:id(lease) not in snapshot_ids or id(lease) in valid_ids) or life.state=='DRAINING':
                        await hub.close(stopping=True)
                        callback=getattr(app.state,'shutdown',None)
                        if callback:callback()
                        break
            watcher=asyncio.create_task(idle_watch())
            try:yield
            finally:
                watcher.cancel()
                try:await watcher
                except asyncio.CancelledError:pass
        finally:
            await hub.close()
            life.state="STOPPED"
            lock.release()

    app=FastAPI(title="Decision Tracker",version="1.0.0",docs_url=None,redoc_url=None,openapi_url=None,lifespan=lifespan)
    app.state.service=service
    app.state.auth=auth
    app.state.config=config
    app.state.lifecycle=life
    app.state.legacy_auth=legacy

    def error(exc,request):
        return JSONResponse({"ok":False,"request_id":getattr(request.state,"request_id",str(uuid4())),
                "error":{"code":exc.code,"message":exc.message,"details":exc.details,"recovery":exc.recovery}},status_code=exc.status)

    @app.exception_handler(Fault)
    async def domain_error(request,exc):return error(exc,request)

    @app.exception_handler(RequestValidationError)
    async def request_error(request,exc):
        details=[{"field":".".join(map(str,x["loc"])),"message":x["msg"]} for x in exc.errors()]
        status=400 if any(x["type"]=="json_invalid" for x in exc.errors()) else 422
        return error(Fault("VALIDATION_ERROR","The request is invalid.",status,{"fields":details}),request)

    @app.exception_handler(ValidationError)
    async def model_error(request,exc):
        return error(Fault("VALIDATION_ERROR","The proposed record is invalid.",422,
                           {"fields":[{"field":".".join(map(str,x["loc"])),"message":x["msg"]} for x in exc.errors()]}),request)

    @app.exception_handler(sqlite3.Error)
    async def database_error(request,exc):
        return error(Fault("DATABASE_UNAVAILABLE","Database integrity or availability check failed.",503,
                           recovery="Preserve the database and inspect the local evidence."),request)

    @app.middleware("http")
    async def guard(request,call_next):
        request.state.request_id=str(uuid4())
        try:
            host=request.headers.get("host","").lower()
            require(host in (f"127.0.0.1:{config.port}",f"localhost:{config.port}"),
                    "FORBIDDEN","Unrecognized local host.",403)
            supplied_origin=request.headers.get("origin")
            require(supplied_origin is None or supplied_origin==origin,"FORBIDDEN","Origin is not permitted.",403)
            if request.method in ("POST","PUT","PATCH"):
                require(request.headers.get("content-type","").split(";")[0].lower()=="application/json",
                        "VALIDATION_ERROR","Use application/json.",422)
                cap=10*1024*1024 if request.url.path in ("/api/v1/imports/new","/api/v1/imports/validate", "/api/v1/saved-decisions/changes", "/api/v1/saved-decisions/import-check", "/api/v1/saved-decisions/prepare") else 1024*1024
                if request.url.path.startswith(("/api/v1/session","/api/v1/account","/api/v1/service")):cap=16384
                body=bytearray()
                async for chunk in request.stream():
                    require(len(body)+len(chunk)<=cap,"LIMIT_EXCEEDED","Request body exceeds the documented limit.",413)
                    body.extend(chunk)
                request._body=bytes(body)
                if request.url.path in ('/api/v1/imports/new','/api/v1/imports/validate','/api/v1/saved-decisions/changes','/api/v1/saved-decisions/import-check','/api/v1/saved-decisions/prepare'):
                    from .legacy import parse
                    parse(request._body)
            response=await call_next(request)
        except Fault as exc:response=error(exc,request)
        except Exception:
            response=error(Fault("INTERNAL_ERROR","The request could not be completed.",500,
                                recovery="Inspect the local diagnostic reference; do not assume the write failed."),request)
        if getattr(request.state,'admitted',False):life.leave()
        if response.status_code in (429,503):response.headers['Retry-After']='60' if response.status_code==429 else '5'
        response.headers.update({"Content-Security-Policy":"default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'",
            "X-Content-Type-Options":"nosniff","Referrer-Policy":"no-referrer","Cache-Control":"no-store",
            "X-Request-ID":request.state.request_id})
        return response

    def authenticate(request, touch=True):
        header=request.headers.get("authorization")
        cookie=request.cookies.get("dt_session")
        require(not (header and cookie),"FORBIDDEN","Use one authentication method per request.",403)
        if header:
            require(header.startswith("Bearer "),"UNAUTHORIZED","Use bearer authentication.",401)
            return auth.bearer(header[7:])
        require(bool(cookie),"UNAUTHORIZED","Sign in or supply a bearer credential.",401)
        session=auth.session(cookie,touch=touch)
        if request.method not in ("GET","HEAD"):
            require(request.headers.get("origin")==origin and hmac.compare_digest(request.headers.get("x-csrf-token",""),session["csrf"]),
                    "FORBIDDEN","Session write requires same-origin CSRF protection.",403)
        from dataclasses import replace
        return replace(session["principal"],auth_method='legacy_token_session' if legacy else 'human_password_session')

    def principal(request,touch=True):
        # Credential mutation and admission are ordered by the same store lock.
        guard_lock=auth.lock if legacy else auth.store.lock
        with guard_lock:
            path=request.url.path
            excluded=(path in ('/api/v1/status','/api/v1/session') and request.method=='GET' or path.endswith('/events') or path.startswith('/api/v1/service/'))
            p=authenticate(request,touch=touch and not excluded)
            if path.startswith('/api/v1/projects/'):
                p.project(path.split('/')[4])
            if not excluded and not getattr(request.state,'admitted',False):
                life.enter();request.state.admitted=True
            return p

    def identity(request):
        value=request.headers.get("x-ledger-uuid")
        require(bool(value),"VALIDATION_ERROR","Supply X-Ledger-UUID.")
        return value

    def output(request,value):
        value.setdefault("request_id",request.state.request_id)
        from .store import encode
        require(len(encode(value).encode())<=65536,"LIMIT_EXCEEDED","Response requires pagination or field chunks.",413)
        return value

    @app.get("/api/v1/projects/{project_id}/events")
    async def events(project_id:str,request:Request,decision_key:str|None=Query(default=None,pattern=r"^D[0-9]{6}$")):
        p=principal(request,touch=False);p.need("read");p.project(project_id)
        try:client=await hub.add(project_id,identity(request),p,decision_key,lambda:principal(request,touch=False))
        except Fault as exc:
            if exc.status==429:
                response=error(exc,request);response.headers["Retry-After"]="5";return response
            raise
        return BoundedStream(hub.events(project_id,client),media_type="text/event-stream",
                             headers={"Cache-Control":"no-store","X-Accel-Buffering":"no"})

    @app.get("/api/v1/status")
    def status(request:Request):
        return output(request,{"ok":True,"data":{"service":"Decision Tracker","version":"0.1.0.dev0","ready":True}})

    if legacy:
        @app.post("/api/v1/session")
        def login(request:Request,data:Login):
            require(request.headers.get("origin")==origin,"FORBIDDEN","Sign in from the application origin.",403)
            require(not request.headers.get("authorization"),"FORBIDDEN","Use the sign-in form without bearer authentication.",403)
            sid,session=auth.login(data.token)
            response=JSONResponse({"ok":True,"data":{"principal":session["principal"].id,"csrf_token":session["csrf"],
                         "capabilities":sorted(session["principal"].capabilities)}})
            response.set_cookie("dt_session",sid,httponly=True,samesite="strict",max_age=28800,path="/")
            return response

    @app.get("/api/v1/session")
    def session(request:Request):
        p=principal(request)
        value=auth.session(request.cookies.get("dt_session")) if request.cookies.get("dt_session") else None
        return output(request,{"ok":True,"data":{"principal":p.id,"capabilities":sorted(p.capabilities),
                                "csrf_token":value["csrf"] if value else None}})

    @app.delete("/api/v1/session")
    def logout(request:Request):
        principal(request);auth.logout(request.cookies.get("dt_session"))
        response=JSONResponse({"ok":True,"data":{"signed_out":True}})
        response.delete_cookie("dt_session",path="/")
        return response

    @app.get("/api/v1/schema")
    def schema(request:Request,contract:str|None=None):
        principal(request)
        from .legacy import schema as legacy_schema,contract_digest
        if contract is not None:
            require(contract=='legacy-import-v1','NOT_FOUND','Schema contract unavailable.',404)
            return legacy_schema()
        schema=app.openapi().copy()
        from .approvals import Approval, DeprecationEvent
        from .planning_links import PlanningLink
        schema['x-decision-tracker']={'capabilities':['approval_events_v1','deprecation_approval_v1','planning_links_v1','planning_applications_v1','legacy_history_v1','inactive_candidate_recovery_v1','saved_decisions_v1'],'ledger_schemas':[1,2,3,4],
                                     'legacy_contract_url':'/api/v1/schema?contract=legacy-import-v1','legacy_contract_sha256':contract_digest(),
                                     'approval_input':Approval.model_json_schema(),
                                     'deprecation_approval':{'input':Approval.model_json_schema(),'event_schema':'decision-tracker.deprecation-approval/v1','event':DeprecationEvent.model_json_schema(),'kind':'deprecate','minimum_runtime':'deprecation_approval_v1-capable binary','older_binary_new_history_compatible':False},
                                     'planning_link_input':PlanningLink.model_json_schema(),
                                     'planning_link_policy_write':'os_owner_cli_only',
                                     'application_input':PlanningLink.model_json_schema(),
                                     'application_policy_write':'os_owner_cli_only',
                                     'mutation_policy':{'ordinary_requires':'open_unlocked','relationship_endpoints':'both_open_unlocked',
                                                        'reopen':'separate_committed_request','edit_resolution':'withdrawn_for_new_writes',
                                                        'closed_lifecycle':['decision.reopen','decision.lock','decision.amend','decision.deprecate'],
                                                        'historical_receipts':'exact_replay_preserved'}}
        return schema

    @app.get("/api/v1/projects")
    def projects(request:Request):
        return output(request,service.catalog.listing(principal(request)))

    @app.post("/api/v1/projects")
    def project_create(request:Request,data:ProjectChange):
        return output(request,service.catalog.mutate(principal(request),data))

    @app.get("/api/v1/projects/{project_id}")
    def project_show(project_id:str,request:Request):
        result=service.catalog.listing(principal(request))
        match=next((x for x in result["data"] if x["project_id"]==project_id),None)
        require(match is not None,"NOT_FOUND","Project is unavailable.",404)
        # Explicit project show is the discovery/binding operation.
        supplied=request.headers.get("x-ledger-uuid")
        require(not supplied or supplied==match["ledger_uuid"],"LEDGER_IDENTITY_MISMATCH","Ledger identity changed.",409)
        result["data"]=match
        return output(request,result)

    @app.post("/api/v1/projects/{project_id}/state")
    def project_state(project_id:str,request:Request,data:ProjectState):
        p=principal(request)
        with service.catalog.coordinator, __import__("decision_tracker.store",fromlist=["connect"]).connect(service.catalog.path) as db:
            service.catalog.lookup(db,project_id,identity(request),p,enabled=False)
        return output(request,service.catalog.mutate(p,data,project_id))

    @app.post("/api/v1/projects/{project_id}/changes")
    def changes(project_id:str,request:Request,data:Change):
        p=principal(request)
        require(identity(request)==str(data.expected_ledger_uuid),"LEDGER_IDENTITY_MISMATCH","Header and request identity disagree.",409)
        return output(request,service.change(project_id,p,data))

    @app.get("/api/v1/projects/{project_id}/decisions")
    def decisions(project_id:str,request:Request,q:str="",status:str|None=None,work:str|None=None,
                  owner:str|None=None,cursor:str|None=None,limit:int=Query(50,ge=1,le=200),source_namespace:str|None=None,source_id:str|None=None):
        if source_namespace is not None or source_id is not None:
            p=principal(request);p.need('read');require(source_namespace and source_id,'VALIDATION_ERROR','Supply source namespace and source ID together.')
            with service.catalog.project(project_id,identity(request),p) as (db,_):key=service.legacy_reads.source_key(db,source_namespace,source_id)
            return output(request,service.detail(project_id,identity(request),p,key))
        return output(request,service.list_decisions(project_id,identity(request),principal(request),q,status,work,owner,cursor,limit))

    @app.get("/api/v1/projects/{project_id}/decisions/{key}")
    def detail(project_id:str,key:str,request:Request):
        return output(request,service.detail(project_id,identity(request),principal(request),key))

    @app.get("/api/v1/projects/{project_id}/decisions/{key}/as-of")
    def asof(project_id:str,key:str,request:Request,revision:int=Query(ge=0)):
        return output(request,service.detail(project_id,identity(request),principal(request),key,revision))

    @app.get("/api/v1/projects/{project_id}/decisions/{key}/history")
    def history(project_id:str,key:str,request:Request,cursor:str|None=None,limit:int=Query(50,ge=1,le=200)):
        return output(request,service.history(project_id,identity(request),principal(request),key,cursor,limit))

    @app.get("/api/v1/projects/{project_id}/decisions/{key}/fields/{field}")
    def field(project_id:str,key:str,field:str,request:Request,revision:int=Query(ge=0),
              offset:int=Query(0,ge=0),limit:int=Query(8192,ge=1,le=16384)):
        return output(request,service.field(project_id,identity(request),principal(request),key,field,revision,offset,limit))

    @app.get("/api/v1/projects/{project_id}/decisions/{key}/context")
    def context(project_id:str,key:str,request:Request):
        return output(request,service.related(project_id,identity(request),principal(request),key))

    @app.get("/api/v1/projects/{project_id}/decisions/{key}/impact")
    def impact(project_id:str,key:str,request:Request):
        return output(request,service.related(project_id,identity(request),principal(request),key,True))

    app.state.principal=principal
    app.state.identity=identity
    app.state.output=output
    if not legacy:
        from .account_api import mount as mount_account
        mount_account(app,origin,error)
    from .saved_decisions import mount as mount_saved_decisions
    mount_saved_decisions(app)
    from .artifacts import mount
    from fastapi.staticfiles import StaticFiles
    mount(app)
    from .legacy_api import mount as mount_legacy
    mount_legacy(app)
    from .approval_api import mount as mount_approvals
    mount_approvals(app)
    from .planning_links import mount as mount_planning_links
    mount_planning_links(app)
    @app.get("/api/v1/projects/{project_id}/decisions/{key}/{collection}")
    def children(project_id:str,key:str,collection:str,request:Request,cursor:str|None=None,
                 limit:int=Query(50,ge=1,le=200),revision:int|None=None):
        family="alternatives" if collection=="options" else collection
        return output(request,service.children(project_id,identity(request),principal(request),key,family,cursor,limit,revision))

    assets=Path(__file__).parent / "static"
    app.mount("/static",StaticFiles(directory=assets),name="static")
    @app.get("/",include_in_schema=False)
    def home():return FileResponse(assets / "index.html")
    return app
