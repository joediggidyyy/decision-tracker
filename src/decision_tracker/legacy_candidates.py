"""Durable import intent and inactive candidate artifact/recovery operations."""
from contextlib import closing
import hashlib
import json
import os
import shutil
import sqlite3
from uuid import uuid4
from . import store, legacy
from .config import contained
from .models import now
from .errors import Fault, require, missing
from .candidates import paths, inspect, prepare

def journal(catalog):
    path=contained(catalog.root,'import-journal.sqlite')
    if not path.exists():
        with path.open('xb'):pass
    with closing(sqlite3.connect(path)) as db:
        db.execute('CREATE TABLE IF NOT EXISTS intents(principal_id TEXT NOT NULL,request_id TEXT NOT NULL,request_hash TEXT NOT NULL,import_id TEXT NOT NULL,namespace TEXT NOT NULL UNIQUE,target_uuid TEXT NOT NULL UNIQUE,candidate_id TEXT NOT NULL UNIQUE,state TEXT NOT NULL CHECK(state IN (\'validated\',\'preparing\',\'prepared\',\'failed\')),outcome_json TEXT,error_code TEXT,PRIMARY KEY(principal_id,request_id)) STRICT')
        db.commit()
    return path

def checkpoint(stage):
    """Internal fault-injection seam; never exposed through request data."""

def atomic_json(path,value):
    temp=path.with_name(path.name+'.'+str(uuid4())+'.pending')
    with temp.open('x',encoding='utf-8') as out:out.write(store.encode(value));out.flush();os.fsync(out.fileno())
    os.replace(temp,path)

def import_legacy(objects,principal,value,promote):
    principal.need('maintain')
    require('*' in principal.projects or value.get('namespace') in principal.projects,'FORBIDDEN','Import namespace is outside your project scope.',403)
    import_id=legacy.validate_request(value)
    request_hash=legacy.digest(value)
    with objects.catalog.coordinator:
        if not promote:
            candidate_id=str(uuid4());path=contained(objects.root,'scratch/'+candidate_id+'/validated.sqlite');path.parent.mkdir(parents=True)
            build(path,value,principal)
            from .artifacts import validate_history
            with store.connect(path) as db:result=validate_history(db)
            return {'ok':True,'data':{**result,'import_id':import_id,'candidate_id':candidate_id,'registered':False,'validated_only':True}}
        jpath=journal(objects.catalog)
        with store.connect(jpath,True) as db:
            row=db.execute('SELECT * FROM intents WHERE principal_id=? AND request_id=?',(principal.id,value['request_id'])).fetchone()
            if row:
                require(row['request_hash']==request_hash,'REQUEST_ID_REUSED','Import request ID has different content.',409)
                candidate_id=row['candidate_id']
                if row['state']=='prepared':
                    saved=json.loads(row['outcome_json']);current=inspect(objects.catalog,candidate_id,allow_registered=True)
                    _,relative,candidate_path,_=paths(objects.catalog,candidate_id)
                    with store.connect(objects.catalog.path) as cat:
                        registered=cat.execute('SELECT 1 FROM projects WHERE ledger_uuid=? AND lower(db_path)=lower(?)',(current['ledger_uuid'],relative)).fetchone() is not None
                    with store.connect(candidate_path) as candidate:
                        origin=candidate.execute('SELECT import_id FROM legacy_imports').fetchone()
                    require(current['ledger_uuid']==value['target_ledger_uuid'] and origin and origin[0]==import_id and (registered or current['logical_digest']==saved['logical_digest']),'CANDIDATE_CHANGED','Prepared import no longer matches its receipt.',409)
                    # A registered ledger can legitimately gain native revisions.
                    # Replay is the original import outcome, not current verification.
                    return {'ok':True,'data':{**saved,'replayed':True}}
            else:
                with store.connect(objects.catalog.path) as cat:
                    require(cat.execute('SELECT 1 FROM projects WHERE ledger_uuid=?',(value['target_ledger_uuid'],)).fetchone() is None,'DUPLICATE_LEDGER','Import target is already registered.',409)
                require(db.execute('SELECT 1 FROM intents WHERE namespace=? OR target_uuid=?',(value['namespace'],value['target_ledger_uuid'])).fetchone() is None,'IMPORT_IDENTITY_COLLISION','Import namespace or target UUID is already reserved.',409)
                folder=contained(objects.root,'candidates')
                if folder.exists():
                    for directory in folder.iterdir():
                        if not directory.is_dir():continue
                        other=paths(objects.catalog,directory.name)[2]
                        if other.is_file():
                            with store.connect(other) as candidate:
                                require(store.metadata(candidate)['ledger_uuid']!=value['target_ledger_uuid'],'IMPORT_IDENTITY_COLLISION','Import target UUID belongs to a retained candidate.',409)
                candidate_id=str(uuid4())
                db.execute('INSERT INTO intents VALUES(?,?,?,?,?,?,?,\'validated\',NULL,NULL)',(principal.id,value['request_id'],request_hash,import_id,value['namespace'],value['target_ledger_uuid'],candidate_id))
        checkpoint('intent')
        _,_,path,_=paths(objects.catalog,candidate_id);path.parent.mkdir(parents=True,exist_ok=True)
        with store.connect(jpath,True) as db:db.execute('UPDATE intents SET state=\'preparing\',error_code=NULL WHERE candidate_id=?',(candidate_id,))
        try:
            if not path.exists():
                pending=path.with_suffix('.pending.sqlite')
                if pending.exists():os.replace(pending,pending.with_name('interrupted-'+str(uuid4())+'.sqlite'))
                build(pending,value,principal);checkpoint('built')
                os.replace(pending,path);checkpoint('published')
            current=inspect(objects.catalog,candidate_id,allow_registered=True)
            with store.connect(path) as db:
                origin=db.execute('SELECT import_id,target_ledger_uuid FROM legacy_imports').fetchone()
                require(origin and origin[0]==import_id and origin[1]==value['target_ledger_uuid'],'INTEGRITY_FAILED','Reserved candidate contains a different import.',409)
            prepare(objects.catalog,principal,candidate_id,imported=True);checkpoint('prepared')
            outcome={'request_id':value['request_id'],'request_hash':request_hash,'principal_id':principal.id,
                'candidate_id':candidate_id,'ledger_uuid':current['ledger_uuid'],'logical_digest':current['logical_digest'],
                'import_id':import_id,'state':'prepared','replayed':False}
            legacy.check_shape(outcome,'candidate_receipt')
            with store.connect(jpath,True) as db:db.execute('UPDATE intents SET state=\'prepared\',outcome_json=? WHERE candidate_id=?',(store.encode(outcome),candidate_id))
            checkpoint('outcome')
            return {'ok':True,'data':outcome}
        except Exception as exc:
            with store.connect(jpath,True) as db:db.execute('UPDATE intents SET state=\'failed\',error_code=? WHERE candidate_id=?',(exc.code if isinstance(exc,Fault) else 'PREPARATION_FAILED',candidate_id))
            raise

def build(path,value,principal):
    from .artifacts import validate_history
    store.initialize(path,value['target_ledger_uuid'],schema_version=4)
    with store.connect(path,True) as db:
        db.execute('PRAGMA defer_foreign_keys=ON')
        legacy.populate(db,value,principal,now())
        validate_history(db)

def bound(objects,principal,candidate_id,expected):
    principal.need('maintain')
    require(isinstance(expected,str) and __import__('re').fullmatch(r'[0-9a-f]{64}',expected),'VALIDATION_ERROR','Supply the expected candidate digest.')
    current=inspect(objects.catalog,candidate_id)
    require(current['logical_digest']==expected,'CANDIDATE_CHANGED','Candidate digest differs.',409)
    path=paths(objects.catalog,candidate_id)[2]
    with store.connect(path) as db:
        origin=db.execute('SELECT namespace,imported_by FROM legacy_imports').fetchone() if current['schema_version']==4 else None
        require('*' in principal.projects or origin and origin[0] in principal.projects and origin[1]==principal.id,'FORBIDDEN','Candidate is outside your scope.',403)
    return path,current

def artifact(objects,principal,candidate_id,expected,kind,artifact_id=None):
    from .artifacts import bundle,validate_history
    with objects.catalog.coordinator:
        path,current=bound(objects,principal,candidate_id,expected)
        if kind=='verify':return {'ok':True,'data':{**current,'integrity':'ok'}}
        folder=contained(objects.root,'candidate-artifacts/'+candidate_id);folder.mkdir(parents=True,exist_ok=True)
        if kind=='restore-check':
            try:artifact_id=str(__import__('uuid').UUID(artifact_id))
            except (ValueError,TypeError,AttributeError):raise Fault('VALIDATION_ERROR','Invalid backup artifact ID.') from None
            record=folder/(artifact_id+'.json')
            require(record.is_file() and record.stat().st_size<=4096,'NOT_FOUND','Candidate backup unavailable.',404)
            receipt=json.loads(record.read_text(encoding='utf-8'));backup=folder/(artifact_id+'.sqlite')
            require(receipt['kind']=='backup' and receipt['candidate_id']==candidate_id and receipt['logical_digest']==expected and backup.is_file(),'INTEGRITY_FAILED','Candidate backup receipt differs.',409)
            require(backup.stat().st_size<=20*1024*1024 and hashlib.sha256(backup.read_bytes()).hexdigest()==receipt['sha256'],'INTEGRITY_FAILED','Candidate backup hash differs.',409)
            restored=str(uuid4());destination=paths(objects.catalog,restored)[2];destination.parent.mkdir(parents=True)
            shutil.copyfile(backup,destination)
            with store.connect(destination) as db:verified=validate_history(db)
            require(verified['logical_sha256']==expected and verified['ledger_uuid']==current['ledger_uuid'],'INTEGRITY_FAILED','Independent restore differs.',409)
            result=prepare(objects.catalog,principal,restored,imported=True)['data']
            return {'ok':True,'data':{**result,'source_candidate_id':candidate_id,'artifact_id':artifact_id,'activated':False,'registered':False}}
        require(kind in ('export','backup'),'VALIDATION_ERROR','Unknown candidate artifact operation.')
        artifact_id=str(uuid4());target=folder/(artifact_id+('.json.bundle' if kind=='export' else '.sqlite'));pending=target.with_suffix(target.suffix+'.pending')
        with store.connect(path) as db:
            if kind=='export':
                raw=store.encode(bundle(db)).encode();require(len(raw)<=legacy.MAX_BYTES,'LIMIT_EXCEEDED','Native export exceeds 10MiB.',413)
                with pending.open('xb') as out:out.write(raw);out.flush();os.fsync(out.fileno())
            else:
                with closing(sqlite3.connect(pending)) as targetdb:db.backup(targetdb)
                with store.connect(pending) as restored:require(validate_history(restored)['logical_sha256']==expected,'INTEGRITY_FAILED','Backup content differs.',409)
        require(pending.stat().st_size<=20*1024*1024,'LIMIT_EXCEEDED','Candidate artifact exceeds 20MiB.',413)
        os.replace(pending,target)
        receipt={'artifact_id':artifact_id,'candidate_id':candidate_id,'kind':kind,'logical_digest':expected,'ledger_uuid':current['ledger_uuid'],'revision':current['ledger_revision'],'sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'size':target.stat().st_size,'created_at':now()}
        atomic_json(folder/(artifact_id+'.json'),receipt)
        return {'ok':True,'data':receipt}

def download(objects,principal,candidate_id,expected,artifact_id):
    with objects.catalog.coordinator:
        bound(objects,principal,candidate_id,expected)
        try:artifact_id=str(__import__('uuid').UUID(artifact_id))
        except (ValueError,TypeError,AttributeError):raise Fault('VALIDATION_ERROR','Invalid artifact ID.') from None
        folder=contained(objects.root,'candidate-artifacts/'+candidate_id);record=folder/(artifact_id+'.json')
        require(record.is_file() and record.stat().st_size<=4096,'NOT_FOUND','Candidate artifact unavailable.',404)
        r=json.loads(record.read_text(encoding='utf-8'));target=folder/(artifact_id+('.json.bundle' if r['kind']=='export' else '.sqlite'))
        require(r['candidate_id']==candidate_id and r['logical_digest']==expected and target.is_file() and target.stat().st_size<=20*1024*1024 and hashlib.sha256(target.read_bytes()).hexdigest()==r['sha256'],'INTEGRITY_FAILED','Candidate artifact differs.',409)
        return target,r
