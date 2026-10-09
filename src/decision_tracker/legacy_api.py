"""Legacy reads and inactive maintenance within existing API families."""
from fastapi import Request, Query
from pydantic import Field
from .models import Model
from . import store, legacy
from .legacy_candidates import artifact, download
from .errors import require

def mount(app):
    service=app.state.service;principal,identity,output=app.state.principal,app.state.identity,app.state.output
    reads=service.legacy_reads
    class CandidateInput(Model):
        expected_candidate_digest:str=Field(pattern=r'^[0-9a-f]{64}$')
        artifact_id:str|None=None
    @app.get('/api/v1/projects/{project_id}/legacy/records/{family}')
    def records(project_id:str,family:str,request:Request,key:str|None=None,cursor:str|None=None,limit:int=Query(50,ge=1,le=200)):
        return output(request,reads.records(project_id,identity(request),principal(request),family,key,cursor,limit))
    @app.get('/api/v1/projects/{project_id}/legacy/members')
    def members(project_id:str,request:Request,version_id:str|None=None,source_id:str|None=None,cursor:str|None=None,limit:int=Query(50,ge=1,le=200)):
        return output(request,reads.read(project_id,identity(request),principal(request),'members',version_id=version_id,source_id=source_id,cursor=cursor,limit=limit))
    @app.get('/api/v1/projects/{project_id}/legacy/relations')
    def relations(project_id:str,request:Request,version_id:str|None=None,source_id:str|None=None,cursor:str|None=None,limit:int=Query(50,ge=1,le=200)):
        return output(request,reads.read(project_id,identity(request),principal(request),'relations',version_id=version_id,source_id=source_id,cursor=cursor,limit=limit))
    @app.get('/api/v1/projects/{project_id}/legacy/payloads/{payload_hash}')
    def payload(project_id:str,payload_hash:str,request:Request,offset:int=Query(0,ge=0),limit:int=Query(8192,ge=1,le=16384)):
        return output(request,reads.read(project_id,identity(request),principal(request),'payload',payload=payload_hash,offset=offset,limit=limit))
    @app.get('/api/v1/projects/{project_id}/decisions/{key}/legacy')
    def history(project_id:str,key:str,request:Request,version_id:str|None=None,cursor:str|None=None,limit:int=Query(50,ge=1,le=200)):
        return output(request,reads.read(project_id,identity(request),principal(request),'members',key=key,version_id=version_id,cursor=cursor,limit=limit))
    @app.get('/api/v1/projects/{project_id}/decisions/{key}/legacy/relations')
    def decision_relations(project_id:str,key:str,request:Request,version_id:str|None=None,cursor:str|None=None,limit:int=Query(50,ge=1,le=200)):
        return output(request,reads.read(project_id,identity(request),principal(request),'relations',key=key,version_id=version_id,cursor=cursor,limit=limit))
    @app.get('/api/v1/projects/{project_id}/decisions/{key}/legacy/as-of')
    def asof(project_id:str,key:str,request:Request,version_id:str):
        return output(request,reads.read(project_id,identity(request),principal(request),'as-of',key=key,version_id=version_id))
    @app.get('/api/v1/projects/{project_id}/decisions/{key}/legacy/payload/{payload_hash}')
    def decision_payload(project_id:str,key:str,payload_hash:str,request:Request,offset:int=Query(0,ge=0),limit:int=Query(8192,ge=1,le=16384)):
        return output(request,reads.read(project_id,identity(request),principal(request),'payload',key=key,payload=payload_hash,offset=offset,limit=limit))
    @app.post('/api/v1/candidates/{candidate_id}/{operation}')
    def maintenance(candidate_id:str,operation:str,request:Request,data:CandidateInput):
        kinds={'exports':'export','backups':'backup','verify':'verify','restore-check':'restore-check'}
        require(operation in kinds,'NOT_FOUND','Unknown candidate operation.',404)
        require(data.artifact_id is None or operation=='restore-check','VALIDATION_ERROR','Artifact ID is only used for restore-check.')
        return output(request,artifact(app.state.artifacts,principal(request),candidate_id,data.expected_candidate_digest,kinds[operation],data.artifact_id))
    @app.get('/api/v1/candidates/{candidate_id}/artifacts/{artifact_id}/content')
    def content(candidate_id:str,artifact_id:str,request:Request,expected_candidate_digest:str):
        from fastapi.responses import FileResponse
        path,_=download(app.state.artifacts,principal(request),candidate_id,expected_candidate_digest,artifact_id)
        return FileResponse(path,filename=artifact_id+path.suffix,media_type='application/octet-stream')
