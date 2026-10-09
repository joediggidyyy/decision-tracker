"""Contained immutable exports, verified backups and candidate-only imports."""
from contextlib import closing
import base64
import hashlib
import json
import os
import shutil
import sqlite3
from pathlib import Path
from uuid import uuid4
from . import store
from .config import contained
from .models import Decision, Option, Reference, Link, now
from .errors import require, Fault, missing

TABLES=("decisions","alternatives","references","links","transactions","revisions")
SORT={"decisions":"key","alternatives":"id","references":"id","links":"id",
      "transactions":"ledger_revision","revisions":"decision_key,ledger_revision",
      "approval_events":"ledger_revision,operation_ordinal","schema_upgrades":"recorded_at,request_id",
      "application_receipts":"ledger_revision,operation_ordinal","application_policy_events":"policy_revision"}

def tables(version):
    base=TABLES+('approval_events','schema_upgrades')+('application_receipts','application_policy_events') if version>=3 else TABLES+('approval_events','schema_upgrades') if version==2 else TABLES
    if version==4:
        from .legacy import TABLES as legacy_tables, SORT as legacy_sort
        SORT.update({'legacy_'+k:v for k,v in legacy_sort.items()})
        SORT.update(legacy_imports='import_id',legacy_native_seeds='native_key')
        base+=legacy_tables
    return base

def bundle(db):
    meta=store.metadata(db)
    return {"format":f"decision-tracker/v{meta['schema_version']}","schema_version":meta['schema_version'],"ledger_uuid":meta["ledger_uuid"],
            "ledger_revision":meta["ledger_revision"],"meta":meta,
            **{table:[store.unpack(row) for row in db.execute(f'SELECT * FROM "{table}" ORDER BY {SORT[table]}')] for table in tables(meta['schema_version'])}}

def validate_history(db):
    store.integrity(db);meta=store.metadata(db)
    transactions=[x[0] for x in db.execute("SELECT ledger_revision FROM transactions ORDER BY ledger_revision")]
    require(transactions==list(range(1,meta["ledger_revision"]+1)),"INTEGRITY_FAILED","Transaction sequence is incomplete.",409)
    for tx in db.execute("SELECT * FROM transactions"):
        request=json.loads(tx["request_json"])
        require(store.digest(request)==tx["request_hash"],"INTEGRITY_FAILED","Transaction request hash differs.",409)
        require(db.execute("SELECT 1 FROM revisions WHERE ledger_revision=?",(tx["ledger_revision"],)).fetchone() is not None,
                "INTEGRITY_FAILED","Transaction has no recorded decision revision.",409)
        result=json.loads(tx["result_json"])
        require(result.get("ledger_uuid")==meta["ledger_uuid"] and result.get("revision")==tx["ledger_revision"],
                "INTEGRITY_FAILED","Transaction outcome metadata differs.",409)
    for row in db.execute("SELECT * FROM decisions ORDER BY key"):
        obj=store.unpack(row);store.validate_decision(db,obj)
        from .legacy import initial
        key=obj["key"];latest=initial(db,key);previous=1 if latest else 0
        for rev in db.execute("SELECT * FROM revisions WHERE decision_key=? ORDER BY ledger_revision",(key,)):
            snap=json.loads(rev["snapshot_json"])
            require(store.digest(snap)==rev["snapshot_sha256"],"INTEGRITY_FAILED","Historical snapshot hash differs.",409)
            require(rev["prior_decision_revision"]==previous and snap["revision"]==previous+1 and snap["key"]==key,
                    "INTEGRITY_FAILED","Historical decision revisions are inconsistent.",409)
            current={k:v for k,v in snap.items() if k not in ("alternatives","references","links")}
            store.validate_decision(db,current)
            for family,model in (("alternatives",Option),("references",Reference),("links",Link)):
                for child in snap[family]:
                    model.model_validate(child)
                    require((key in (child["source_key"],child["target_key"])) if family=="links" else child["decision_key"]==key,
                            "INTEGRITY_FAILED","Snapshot contains an unrelated child.",409)
            latest=snap;previous=snap["revision"]
        require(latest==store.snapshot(db,key),"INTEGRITY_FAILED","Current state differs from its final historical snapshot.",409)
    # Validate final aggregate constraints and graph cycles without creating a write.
    from .state import Mutator
    validator=Mutator(db,None,None)
    validator.original={r[0]:0 for r in db.execute("SELECT key FROM decisions")}
    validator.validate()
    for table,model in store.MODELS.items():
        for row in db.execute(f'SELECT * FROM "{table}"'):
            store.validate_decision(db,store.unpack(row)) if table=='decisions' else model.model_validate(store.unpack(row))
    if meta['schema_version']>=2:
        from .approval_history import validate
        validate(db,meta)
    if meta['schema_version']>=3:
        from .planning_links import validate
        validate(db,meta)
    if meta['schema_version']==4:
        from .legacy import validate
        validate(db)
    return {"integrity":"ok","ledger_uuid":meta["ledger_uuid"],"revision":meta["ledger_revision"],
            "logical_sha256":store.digest(bundle(db))}

class Artifacts:
    def __init__(self,service):
        self.service=service;self.catalog=service.catalog;self.root=service.root

    def list(self,project_id,uuid,principal,cursor=None,limit=50,kind=None,order='artifact_id'):
        principal.need("read")
        require(kind in (None,'backup','export') and order in ('artifact_id','newest'),
                'VALIDATION_ERROR','Unknown file filter or order.')
        require(order!='newest' or kind is not None,'VALIDATION_ERROR','Newest order requires a file kind.')
        require(type(limit) is int and 1<=limit<=200,'VALIDATION_ERROR','Page size must be 1–200.')
        with self.catalog.project(project_id,uuid,principal) as (db,project):
            meta=store.metadata(db,uuid)
            if order=='newest':return self.manager_page(db,project,meta,kind,cursor,limit)
            rows=[dict(x) for x in db.execute("SELECT * FROM artifacts ORDER BY artifact_id")]
            for row in rows:row.pop("relative_path",None)
            if kind:rows=[r for r in rows if r['kind']==kind]
            query={"kind":"artifacts"}
            if kind:query['file_kind']=kind
            data,cur,complete=self.service.page([(x["artifact_id"],x) for x in rows],meta,query,cursor,limit)
            return self.service.envelope(project,meta,data,next_cursor=cur,complete=complete)

    def manager_page(self,db,project,meta,kind,cursor,limit):
        # Stream public metadata twice: inventory/page boundaries, then just the requested page.
        sql='SELECT * FROM artifacts WHERE kind=? ORDER BY created_at DESC, artifact_id DESC'
        digest=hashlib.sha256();boundaries=[];count=0;size=1024;page_rows=0
        for row in db.execute(sql,(kind,)):
            item=dict(row);item.pop('relative_path',None);raw=store.encode(item).encode()
            require(len(raw)<=60000,'LIMIT_EXCEEDED','File metadata exceeds response capacity.',413)
            digest.update(len(raw).to_bytes(4,'big'));digest.update(raw)
            if not page_rows or page_rows>=limit or size+len(raw)>62000:
                boundaries.append(count);page_rows=0;size=1024
            count+=1;page_rows+=1;size+=len(raw)
        inventory=digest.hexdigest();index=0
        binding={'v':2,'uuid':meta['ledger_uuid'],'revision':meta['ledger_revision'],
                 'kind':kind,'order':'newest','limit':limit,'inventory':inventory}
        if cursor:
            require(isinstance(cursor,str) and len(cursor)<=2048,'VALIDATION_ERROR','Invalid cursor.')
            try:parsed=json.loads(base64.b64decode(cursor.encode(),altchars=b'-_',validate=True))
            except (ValueError,UnicodeError):raise Fault('VALIDATION_ERROR','Invalid cursor.') from None
            require(isinstance(parsed,dict) and set(parsed)==set(binding)|{'page'} and parsed['v']==2
                    and type(parsed['page']) is int and parsed['page']>=0,'VALIDATION_ERROR','Invalid manager cursor.')
            require(all(parsed[k]==binding[k] for k in ('uuid','kind','order','limit')),
                    'VALIDATION_ERROR','Cursor does not match this manager.')
            require(parsed['revision']==binding['revision'] and parsed['inventory']==inventory,
                    'CURSOR_STALE','Files changed; refresh the list.',409)
            index=parsed['page']
            require(index<len(boundaries),'VALIDATION_ERROR','Invalid page index.')
        def token(page):return base64.urlsafe_b64encode(store.encode({**binding,'page':page}).encode()).decode()
        data=[]
        if boundaries:
            start=boundaries[index];end=boundaries[index+1] if index+1<len(boundaries) else count
            for row in db.execute(sql+' LIMIT ? OFFSET ?',(kind,end-start,start)):
                item=dict(row);item.pop('relative_path',None);data.append(item)
        following=token(index+1) if index+1<len(boundaries) else None
        return self.service.envelope(project,meta,data,next_cursor=following,complete=following is None,
            previous_cursor=token(index-1) if index else None,total_count=count,
            page_index=index+1 if count else 0,page_count=len(boundaries),inventory_sha256=inventory)

    def create(self,project_id,uuid,principal,kind):
        principal.need("read" if kind=="export" else "maintain")
        require(kind in ("export","backup"),"VALIDATION_ERROR","Unknown artifact kind.")
        artifact_id=str(uuid4());relative=f"artifacts/{uuid}/{artifact_id}/"+("native.json" if kind=="export" else "backup.sqlite")
        path=contained(self.root,relative);path.parent.mkdir(parents=True,exist_ok=True)
        pending=contained(self.root,relative+".pending")
        # Lock covers the capture and publication; database transactions remain short.
        with self.catalog.coordinator:
            with self.catalog.project(project_id,uuid,principal,True) as (db,project):
                meta=store.metadata(db,uuid)
                db.execute("INSERT INTO artifacts VALUES(?,?,?, ?,?,NULL,NULL,?,NULL)",
                           (artifact_id,kind,"pending",meta["ledger_revision"],relative,now()))
            try:
                with self.catalog.project(project_id,uuid,principal) as (db,project):
                    if kind=="export":
                        value=bundle(db);raw=store.encode(value).encode()
                        require(len(raw)<=10*1024*1024,"LIMIT_EXCEEDED","Native export exceeds the v1 import limit.",413)
                        with pending.open("xb") as out:out.write(raw);out.flush();os.fsync(out.fileno())
                        logical=store.digest(value)
                    else:
                        with closing(sqlite3.connect(pending)) as target:db.backup(target)
                        with store.connect(pending) as target:
                            verified=validate_history(target);logical=verified["logical_sha256"]
                    require(pending.stat().st_size<=20*1024*1024,"LIMIT_EXCEEDED","Artifact exceeds20MiB.",413)
                digest=hashlib.sha256(pending.read_bytes()).hexdigest();size=pending.stat().st_size
                require(not path.exists(),"ARTIFACT_EXISTS","Artifact destination already exists.",409)
                os.replace(pending,path)
                with self.catalog.project(project_id,uuid,principal,True) as (db,project):
                    db.execute("UPDATE artifacts SET state='complete',size=?,sha256=? WHERE artifact_id=?",(size,digest,artifact_id))
                    result={"artifact_id":artifact_id,"kind":kind,"state":"complete","revision":meta["ledger_revision"],
                            "size":size,"sha256":digest,"logical_sha256":logical}
                    receipt=path.with_suffix(path.suffix+".receipt.json")
                    with receipt.open("x",encoding="utf-8") as out:
                        out.write(store.encode(result));out.flush();os.fsync(out.fileno())
                    return self.service.envelope(project,store.metadata(db,uuid),result)
            except Exception as exc:
                with self.catalog.project(project_id,uuid,principal,True) as (db,_):
                    db.execute("UPDATE artifacts SET state='failed',error_code=? WHERE artifact_id=?",
                               (exc.code if isinstance(exc,Fault) else "ARTIFACT_FAILED",artifact_id))
                raise

    def download(self,project_id,uuid,principal,artifact_id):
        principal.need("read")
        with self.catalog.project(project_id,uuid,principal) as (db,_):
            row=db.execute("SELECT * FROM artifacts WHERE artifact_id=?",(artifact_id,)).fetchone()
            if row is None:missing()
            require(row["state"]=="complete","ARTIFACT_INCOMPLETE","Artifact is not verified complete.",409)
            path=contained(self.root,row["relative_path"])
            require(path.is_file() and path.stat().st_size<=20*1024*1024,"ARTIFACT_UNAVAILABLE","Artifact is unavailable or oversized.",409)
            require(hashlib.sha256(path.read_bytes()).hexdigest()==row["sha256"],"INTEGRITY_FAILED","Artifact hash differs.",409)
            return path,dict(row)

    def verify(self,project_id,uuid,principal):
        principal.need("maintain")
        with self.catalog.project(project_id,uuid,principal) as (db,project):
            result=validate_history(db)
            return self.service.envelope(project,store.metadata(db,uuid),result)

    def restore_check(self,project_id,uuid,principal,artifact_id):
        principal.need("maintain")
        path,row=self.download(project_id,uuid,principal,artifact_id)
        require(row["kind"]=="backup","VALIDATION_ERROR","Restore-check requires a backup artifact.")
        scratch=contained(self.root,f"scratch/{uuid4()}/candidate.sqlite");scratch.parent.mkdir(parents=True)
        shutil.copyfile(path,scratch)
        with store.connect(scratch) as db:
            result=validate_history(db)
            require(result["ledger_uuid"]==str(uuid) and result["revision"]==row["revision"],
                    "INTEGRITY_FAILED","Backup identity or revision differs from its receipt.",409)
        return {"ok":True,"project_id":project_id,"ledger_uuid":str(uuid),"data":{**result,"activated":False}}

    def import_native(self,principal,value,promote=False):
        principal.need("maintain")
        if isinstance(value,dict) and value.get('format')=='decision-tracker.legacy-import/v1':
            from .legacy_candidates import import_legacy
            return import_legacy(self,principal,value,promote)
        # Import privilege does not grant registry access; candidate registration is separate.
        version=value.get('schema_version') if isinstance(value,dict) else None
        require(type(version) is int and version in (1,2,3,4),'UNSUPPORTED_SCHEMA','Unsupported interchange format.',409)
        require(isinstance(value,dict) and set(value)==set(tables(version))|{"format","schema_version","ledger_uuid","ledger_revision","meta"},
                "VALIDATION_ERROR","Native bundle fields do not match v1.")
        require(value["format"]==f"decision-tracker/v{version}",
                "UNSUPPORTED_SCHEMA","Unsupported interchange format.",409)
        require(len(store.encode(value).encode())<=10*1024*1024 and len(value["decisions"])<=500,
                "LIMIT_EXCEEDED","Import exceeds v1 capacity.",413)
        from uuid import UUID
        try:UUID(value["ledger_uuid"])
        except (ValueError,TypeError,AttributeError):raise Fault("VALIDATION_ERROR","Invalid ledger UUID.") from None
        require(isinstance(value["ledger_revision"],int) and 0<=value["ledger_revision"]<=100000,
                "LIMIT_EXCEEDED","Invalid import revision count.",413)
        candidate_id=str(uuid4());relative=f"candidates/{candidate_id}/ledger.sqlite"
        path=contained(self.root,relative);path.parent.mkdir(parents=True)
        store.initialize(path,value["ledger_uuid"],schema_version=version)
        with store.connect(path,True) as db:
            db.execute("PRAGMA defer_foreign_keys=ON")
            require(set(value["meta"])=={"id","ledger_uuid","schema_version","ledger_revision","created_at"}
                    and value["meta"]["id"]==1 and value["meta"]["schema_version"]==version
                    and value["meta"]["ledger_uuid"]==value["ledger_uuid"]
                    and value["meta"]["ledger_revision"]==value["ledger_revision"],
                    "VALIDATION_ERROR","Bundle metadata is inconsistent.")
            db.execute("UPDATE meta SET ledger_revision=?,created_at=? WHERE id=1",
                       (value["ledger_revision"],value["meta"]["created_at"]))
            if version>=2:
                # Empty candidate initialization is replaced by the source initialization/upgrade receipt.
                db.execute('DROP TRIGGER immutable_upgrade_delete')
                db.execute('DELETE FROM schema_upgrades')
                db.execute("CREATE TRIGGER immutable_upgrade_delete BEFORE DELETE ON schema_upgrades BEGIN SELECT RAISE(ABORT,'Immutable upgrade'); END")
            for table in tables(version):
                require(isinstance(value[table],list),"VALIDATION_ERROR","Native table must be an array.")
                columns=[r[1] for r in db.execute(f'PRAGMA table_info("{table}")')]
                for row in value[table]:
                    require(isinstance(row,dict) and set(row)==set(columns),"VALIDATION_ERROR","Native row fields do not match schema.",table=table)
                    if table in store.MODELS and not (version==4 and table=='decisions'):store.MODELS[table].model_validate(row)
                    vals=[store.encode(row[c]) if c in store.JSON_FIELDS else int(row[c]) if isinstance(row[c],bool) else row[c] for c in columns]
                    db.execute(f'INSERT INTO "{table}" ({",".join(chr(34)+c+chr(34) for c in columns)}) VALUES({",".join("?" for c in columns)})',vals)
            result=validate_history(db)
            require(store.digest(bundle(db))==store.digest(value),"INTEGRITY_FAILED","Import did not round-trip exactly.",409)
            db.execute("INSERT INTO import_receipts VALUES(?,?,?,?,?,?,?)",
                       (candidate_id,store.digest(value),value['format'],value["ledger_uuid"],value["ledger_revision"],now(),store.encode(result)))
        # Validated-only candidates are retained as evidence, never registered.
        if promote:
            from .candidates import prepare
            prepare(self.catalog, principal, candidate_id, imported=True)
        return {"ok":True,"data":{**result,"candidate_id":candidate_id,
                "relative_path":relative if promote else None,"registered":False,"validated_only":not promote}}

    def catalog_backup(self,principal):
        principal.need("registry")
        artifact_id=str(uuid4());relative=f"catalog-backups/{artifact_id}.sqlite"
        path=contained(self.root,relative);path.parent.mkdir(parents=True,exist_ok=True)
        with self.catalog.coordinator,store.connect(self.catalog.path) as db:
            rev=self.catalog.revision(db)
            with closing(sqlite3.connect(path)) as target:db.backup(target)
        with store.connect(path) as db:store.integrity(db)
        result={"ok":True,"catalog_revision":rev,"data":{"artifact_id":artifact_id,"relative_path":relative,
                "sha256":hashlib.sha256(path.read_bytes()).hexdigest()}}
        path.with_suffix(".receipt.json").write_text(store.encode(result),encoding="utf-8")
        return result

def mount(app):
    from fastapi import Request, Query
    from fastapi.responses import FileResponse
    from .models import Model
    class EmptyInput(Model):pass
    class ArtifactInput(Model):
        artifact_id:str
    objects=Artifacts(app.state.service)
    app.state.artifacts=objects
    principal,identity,output=app.state.principal,app.state.identity,app.state.output

    @app.get("/api/v1/candidates")
    def candidates(request:Request,cursor:str|None=None,limit:int=Query(50,ge=1,le=200)):
        from .candidates import listing
        return output(request,listing(app.state.service,principal(request),cursor,limit))

    @app.post("/api/v1/candidates/{candidate_id}/prepare")
    def prepare_candidate(candidate_id:str,request:Request,data:EmptyInput):
        from .candidates import prepare
        return output(request,prepare(objects.catalog,principal(request),candidate_id))

    @app.post("/api/v1/projects/{project_id}/exports")
    def export(project_id:str,request:Request,data:EmptyInput):
        return output(request,objects.create(project_id,identity(request),principal(request),"export"))
    @app.post("/api/v1/projects/{project_id}/backups")
    def backup(project_id:str,request:Request,data:EmptyInput):
        return output(request,objects.create(project_id,identity(request),principal(request),"backup"))
    @app.post("/api/v1/projects/{project_id}/verify")
    def verify(project_id:str,request:Request,data:EmptyInput):
        return output(request,objects.verify(project_id,identity(request),principal(request)))
    @app.post("/api/v1/projects/{project_id}/restore-check")
    def restore(project_id:str,request:Request,data:ArtifactInput):
        return output(request,objects.restore_check(project_id,identity(request),principal(request),data.artifact_id))
    @app.get("/api/v1/projects/{project_id}/artifacts")
    def listing(project_id:str,request:Request,cursor:str|None=None,limit:int=Query(50,ge=1,le=200),kind:str|None=None,order:str='artifact_id'):
        return output(request,objects.list(project_id,identity(request),principal(request),cursor,limit,kind,order))
    @app.get("/api/v1/projects/{project_id}/artifacts/{artifact_id}/content")
    def download(project_id:str,artifact_id:str,request:Request):
        path,row=objects.download(project_id,identity(request),principal(request),artifact_id)
        return FileResponse(path,filename=artifact_id+path.suffix,media_type="application/octet-stream")
    @app.post("/api/v1/imports/validate")
    def validate(request:Request,data:dict):
        return output(request,objects.import_native(principal(request),data))
    @app.post("/api/v1/imports/new")
    def import_new(request:Request,data:dict):
        return output(request,objects.import_native(principal(request),data,True))
    @app.post("/api/v1/catalog/backups")
    def catalog_backup(request:Request,data:EmptyInput):
        return output(request,objects.catalog_backup(principal(request)))
