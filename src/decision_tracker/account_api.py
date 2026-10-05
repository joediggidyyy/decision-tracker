"""Password/setup endpoints and draft/service controls; deliberately no recovery HTTP route."""
from uuid import UUID
from fastapi import Request
from fastapi.responses import JSONResponse,Response
from pydantic import Field,SecretStr
from .models import Model
from .errors import require

class PasswordLogin(Model):
    password: SecretStr=Field(max_length=512)
class Setup(Model):
    new_password: SecretStr=Field(max_length=512)
    bootstrap_code: SecretStr=Field(max_length=128)
    confirmation: SecretStr=Field(max_length=512)
class PasswordChange(Model):
    current_password: SecretStr=Field(max_length=512)
    new_password: SecretStr=Field(max_length=512)
    confirmation: SecretStr=Field(max_length=512)
class SessionRevoke(Model):
    current_password: SecretStr=Field(max_length=512)
class Lease(Model):
    project_id:str=Field(pattern=r'^[a-z][a-z0-9-]{0,47}$')
    expected_ledger_uuid:UUID
    tab_nonce:UUID

def mount(app,origin,error):
    auth=app.state.auth;life=app.state.lifecycle
    def precheck(request):
        require(request.headers.get('origin')==origin and not request.headers.get('authorization'),'FORBIDDEN','Use the application sign-in form.',403)
        auth.precheck(request.cookies.get('dt_preauth'),request.headers.get('x-csrf-token',''))
    def cookie(response,sid):response.set_cookie('dt_session',sid,httponly=True,samesite='strict',max_age=28800,path='/')
    def human(request):
        require(not request.headers.get('authorization'),'FORBIDDEN','Use a human account session.',403)
        app.state.principal(request)
        return auth.session(request.cookies.get('dt_session'),touch=False)

    @app.get('/api/v1/session/setup')
    def setup_state():
        sid,csrf=auth.challenge();state=auth.store.state()
        response=JSONResponse({'ok':True,'data':{'setup_available':state['state']=='uninitialized','recovery_pending':state['state']=='recovery_pending','csrf_token':csrf}})
        response.set_cookie('dt_preauth',sid,httponly=True,samesite='strict',max_age=300,path='/')
        return response

    @app.post('/api/v1/session/setup')
    def setup(request:Request,data:Setup):
        precheck(request);life.enter(touch=False);success=False
        try:auth.store.redeem('bootstrap',data.bootstrap_code.get_secret_value(),data.new_password.get_secret_value(),data.confirmation.get_secret_value());success=True
        finally:life.leave(touch=success)
        auth.consume(request.cookies.get('dt_preauth'));response=Response(status_code=204);response.delete_cookie('dt_preauth',path='/');return response

    @app.post('/api/v1/session')
    def login(request:Request,data:PasswordLogin):
        precheck(request);life.enter(touch=False);success=False
        try:sid,value=auth.login(data.password.get_secret_value());success=True
        finally:life.leave(touch=success)
        auth.consume(request.cookies.get('dt_preauth'))
        response=JSONResponse({'ok':True,'data':{'principal':'operator','csrf_token':value['csrf'],'capabilities':sorted(value['principal'].capabilities)}})
        cookie(response,sid);response.delete_cookie('dt_preauth',path='/');return response

    @app.get('/api/v1/account')
    def account(request:Request):
        current=human(request)
        with auth.lock:
            count=sum(x['epoch']==current['epoch'] for x in auth.sessions.values())-1
        return {'ok':True,'data':{'state':'active','other_sessions':max(0,count)}}

    @app.post('/api/v1/account/password')
    def change(request:Request,data:PasswordChange):
        current=human(request)
        epoch=auth.store.change(data.current_password.get_secret_value(),data.new_password.get_secret_value(),data.confirmation.get_secret_value(),current['epoch'])
        sid,_=auth.new_session(epoch);response=Response(status_code=204);cookie(response,sid);return response

    @app.post('/api/v1/account/sessions/revoke-others')
    def revoke(request:Request,data:SessionRevoke):
        current=human(request);epoch=auth.store.revoke_sessions(data.current_password.get_secret_value(),current['epoch'])
        sid,_=auth.new_session(epoch);response=Response(status_code=204);cookie(response,sid);return response

    def allowed_lease(request,data):
        require(not request.headers.get('authorization'),'FORBIDDEN','Draft leases require a browser session.',403)
        p=app.state.principal(request,touch=False);p.need('read');p.project(data.project_id)
        app.state.service.event_snapshot(data.project_id,str(data.expected_ledger_uuid),p,None)
        return request.cookies.get('dt_session')
    @app.post('/api/v1/service/draft-leases',status_code=201)
    def create_lease(request:Request,data:Lease):
        sid=allowed_lease(request,data)
        return {'ok':True,'data':life.lease(sid,data.project_id,str(data.expected_ledger_uuid),str(data.tab_nonce))}
    @app.put('/api/v1/service/draft-leases/{lease_id}')
    def renew_lease(lease_id:UUID,request:Request,data:Lease):
        sid=allowed_lease(request,data)
        return {'ok':True,'data':life.lease(sid,data.project_id,str(data.expected_ledger_uuid),str(data.tab_nonce),str(lease_id))}
    @app.delete('/api/v1/service/draft-leases/{lease_id}',status_code=204)
    def delete_lease(lease_id:UUID,request:Request):
        require(not request.headers.get('authorization'),'FORBIDDEN','Draft leases require a browser session.',403)
        app.state.principal(request,touch=False);life.release(request.cookies.get('dt_session'),str(lease_id));return Response(status_code=204)
    def maintainer(request):
        p=app.state.principal(request,touch=False);p.need('maintain');require('*' in p.projects,'FORBIDDEN','Service administration requires deployment-wide scope.',403)
    @app.get('/api/v1/service/lifecycle')
    def lifecycle(request:Request):maintainer(request);return {'ok':True,'data':life.status()}
    @app.post('/api/v1/service/stop',status_code=202)
    def stop(request:Request):
        maintainer(request);life.stop(explicit=True);return {'ok':True,'data':{'state':'DRAINING'}}
