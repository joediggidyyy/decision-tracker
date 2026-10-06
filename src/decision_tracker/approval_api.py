"""Bounded approval reads and explicit, recoverable ledger upgrades."""
import json, sqlite3
from uuid import UUID
from pydantic import Field
from . import store
from .models import Model, now
from .errors import require, stale, missing
from .artifacts import validate_history

class Upgrade(Model):
    expected_revision:int=Field(ge=0)
    request_id:UUID

def upgrade(objects,project_id,uuid,principal,request=None):
    principal.need('maintain');catalog=objects.catalog
    with catalog.coordinator:
        with catalog.project(project_id,uuid,principal) as (db,project):
            meta=store.metadata(db,uuid);validate_history(db)
            payload=request.model_dump(mode='json') if request else None
            if request and meta['schema_version']>=2:
                row=db.execute('SELECT * FROM schema_upgrades WHERE request_id=?',(str(request.request_id),)).fetchone()
                if row:
                    require(row['principal_id']==principal.id and row['request_hash']==store.digest(payload),'REQUEST_ID_REUSED','Upgrade request ID has different content.',409)
                    return objects.service.envelope(project,meta,{**json.loads(row['receipt_json']),'replayed':True})
                require(meta['schema_version']<3,'ALREADY_UPGRADED','This project already uses the current data format.',409)
            target=2 if meta['schema_version']==1 else 3
            if request and meta['ledger_revision']!=request.expected_revision:stale(meta['ledger_revision'])
            if request is None:
                size=db.execute('PRAGMA page_count').fetchone()[0]*db.execute('PRAGMA page_size').fetchone()[0]
                return objects.service.envelope(project,meta,{'from_version':meta['schema_version'],'to_version':target,'upgrade_required':meta['schema_version']<3,'history':'verified','database_bytes':size,'estimated_backup_bytes':size,'compatibility':{'schema1_readable':True,'schema1_writable':False,'older_binary_can_read_schema2':False,'older_binary_can_read_schema3':False}})
        backup=objects.create(project_id,uuid,principal,'backup')['data']
        objects.restore_check(project_id,uuid,principal,backup['artifact_id'])
        with catalog.project(project_id,uuid,principal,True) as (db,project):
            current=store.metadata(db,uuid)
            require(current==meta,'REVISION_CONFLICT','Project changed during upgrade.',409)
            # execute, not executescript: the complete upgrade must remain one transaction.
            db.execute('ALTER TABLE meta RENAME TO meta_v1')
            db.execute(f'CREATE TABLE meta(id INTEGER PRIMARY KEY CHECK(id=1),ledger_uuid TEXT NOT NULL UNIQUE,schema_version INTEGER NOT NULL CHECK(schema_version={target}),ledger_revision INTEGER NOT NULL CHECK(ledger_revision>=0),created_at TEXT NOT NULL) STRICT')
            db.execute(f'INSERT INTO meta SELECT id,ledger_uuid,{target},ledger_revision,created_at FROM meta_v1')
            db.execute('DROP TABLE meta_v1')
            statement=''
            for line in (store.APPROVAL_SQL if target==2 else store.APPLICATION_SQL).splitlines(True):
                statement+=line
                if sqlite3.complete_statement(statement):db.execute(statement);statement=''
            receipt={'ledger_uuid':str(uuid),'revision':meta['ledger_revision'],'from_version':meta['schema_version'],'to_version':target,'backup_artifact_id':backup['artifact_id'],'recorded_at':now(),'replayed':False}
            db.execute('INSERT INTO schema_upgrades VALUES(?,?,?,?,?,?,?,?,?)',(str(request.request_id),principal.id,meta['schema_version'],target,meta['ledger_revision'],receipt['recorded_at'],backup['artifact_id'],store.digest(payload),store.encode(receipt)))
            validate_history(db)
            return objects.service.envelope(project,store.metadata(db),receipt)

def mount(app):
    from fastapi import Request, Query
    from .approvals import summary
    objects=app.state.artifacts;service=app.state.service
    principal,identity,output=app.state.principal,app.state.identity,app.state.output
    class Empty(Model):pass
    @app.post('/api/v1/projects/{project_id}/schema-upgrade/check')
    def check(project_id:str,request:Request,data:Empty):return output(request,upgrade(objects,project_id,identity(request),principal(request)))
    @app.post('/api/v1/projects/{project_id}/schema-upgrade')
    def apply(project_id:str,request:Request,data:Upgrade):return output(request,upgrade(objects,project_id,identity(request),principal(request),data))
    def read(project_id,request,key,event_id=None,cursor=None,limit=50):
        p=principal(request);p.need('read')
        with service.catalog.project(project_id,identity(request),p) as (db,project):
            meta=store.metadata(db);store.get(db,'decisions',key)
            rows=list(db.execute('SELECT * FROM approval_events WHERE decision_key=? ORDER BY ledger_revision,operation_ordinal',(key,))) if meta['schema_version']>=2 else []
            if event_id:
                row=next((r for r in rows if r['event_id']==event_id),None)
                if row is None:missing()
                event=json.loads(row['event_json'])
                # Large event text uses existing revision-pinned field retrieval.
                base=f'/api/v1/projects/{project_id}/decisions/{key}'
                event=service.compact(event,base,event['ledger_revision'])
                if event.get('selected_option'):
                    option=event['selected_option'];event['selected_option']=service.compact(option,base,event['ledger_revision']-1,'alternatives.'+option['id']+'.')
                return service.envelope(project,meta,event)
            data,cur,complete=service.page([(f"{r['ledger_revision']:020d}:{r['operation_ordinal']:03d}",summary(json.loads(r['event_json']))) for r in rows],meta,{'kind':'approvals','key':key},cursor,limit)
            return service.envelope(project,meta,data,next_cursor=cur,complete=complete)
    @app.get('/api/v1/projects/{project_id}/decisions/{key}/approvals')
    def listing(project_id:str,key:str,request:Request,cursor:str|None=None,limit:int=Query(50,ge=1,le=200)):return output(request,read(project_id,request,key,cursor=cursor,limit=limit))
    @app.get('/api/v1/projects/{project_id}/decisions/{key}/approvals/{event_id}')
    def detail(project_id:str,key:str,event_id:str,request:Request):return output(request,read(project_id,request,key,event_id))
