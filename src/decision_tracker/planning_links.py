"""Immutable planning-link evidence and locally authorized anchor reads.

Policy history travels with a ledger. Filesystem authorization does not: the
owner CLI also binds the latest policy to this deployment's local data root.
Imports and restored copies cannot authorize new filesystem access by themselves.
"""
import hashlib
import json
import os
from pathlib import Path
from uuid import UUID, uuid4
from pydantic import Field, model_validator
from . import store
from .models import Model, now
from .errors import Fault, require

class PlanningLink(Model):
    planning_document: str | None = Field(default=None,min_length=1,max_length=1024)
    planning_section: str | None = Field(default=None,min_length=1,max_length=160)
    expected_document_sha256: str | None = Field(default=None,pattern=r'^[a-f0-9]{64}$')
    expected_projection_sha256: str | None = Field(default=None,pattern=r'^[a-f0-9]{64}$')
    expected_policy_revision: int = Field(ge=0)
    expected_resolution_id: str | None = Field(default=None,max_length=160)

    @model_validator(mode='after')
    def anchor(self):
        if bool(self.planning_document)!=bool(self.planning_section):
            raise ValueError('Supply both planning document and section.')
        if (self.expected_document_sha256 or self.expected_projection_sha256) and not self.planning_document:
            raise ValueError('Document hash requires an anchor.')
        return self

# Imported callers and schema-3 history retain the original model name.
Application = PlanningLink

class PolicyChange(Model):
    expected_policy_revision: int = Field(ge=0)
    request_id: UUID
    reason: str = Field(min_length=1,max_length=8192)
    anchor_required: bool | None = None
    planning_roots: list[str] | None = Field(default=None,max_length=16)

def policy(db):
    if store.metadata(db)['schema_version']<3:
        return {'policy_revision':0,'anchor_required':True,'planning_roots':[]}
    row=db.execute('SELECT event_json FROM application_policy_events ORDER BY policy_revision DESC LIMIT 1').fetchone()
    return json.loads(row[0]) if row else {'policy_revision':0,'anchor_required':True,'planning_roots':[]}

def binding_path(service,uuid):
    return service.root/'planning-access'/f'{uuid}.json'

def publish_binding(service,uuid,event):
    path=binding_path(service,uuid);path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_name(path.name+'.'+str(uuid4())+'.pending')
    with temp.open('x',encoding='utf-8') as out:
        out.write(store.encode({'ledger_uuid':uuid,'policy_sha256':store.digest(event)}));out.flush();os.fsync(out.fileno())
    os.replace(temp,path)

def set_policy(service,project_id,uuid,principal,request):
    # Called only by the OS-owner administration dispatch, never mounted as HTTP.
    principal.need('maintain')
    body=request.model_dump(mode='json');digest=store.digest(body)
    with service.catalog.coordinator:
        with service.catalog.project(project_id,uuid,principal,True) as (db,project):
            meta=store.metadata(db,uuid)
            require(meta['schema_version']==3,'UPGRADE_REQUIRED','Upgrade this ledger before configuring planning-link policy.',409)
            row=db.execute('SELECT * FROM application_policy_events WHERE request_id=?',(str(request.request_id),)).fetchone()
            if row:
                require(row['request_hash']==digest and json.loads(row['event_json'])['recorded_by']==principal.id,'REQUEST_ID_REUSED','Policy request ID has different content or actor.',409)
                event=json.loads(row['event_json']);replayed=True
            else:
                current=policy(db)
                require(current['policy_revision']==request.expected_policy_revision,'POLICY_CHANGED','Planning-link policy changed. Review it before retrying.',409)
                require(request.reason.strip(),'VALIDATION_ERROR','Supply a nonblank policy change reason.')
                roots=current['planning_roots']
                if request.planning_roots is not None:
                    roots=[]
                    for value in request.planning_roots:
                        require(isinstance(value,str) and 0<len(value)<=1024,'VALIDATION_ERROR','Invalid planning root.')
                        path=Path(value)
                        require(path.is_absolute() and path.is_dir(),'VALIDATION_ERROR','Planning roots must be existing absolute directories.')
                        require(not has_redirect(path),'FORBIDDEN','Planning roots cannot traverse symbolic links or junctions.',403)
                        resolved=str(path.resolve(strict=True))
                        require(path.resolve()!=Path(path.anchor),'FORBIDDEN','Register a project planning directory, not a drive root.',403)
                        if resolved not in roots:roots.append(resolved)
                event={'policy_revision':current['policy_revision']+1,'anchor_required':current['anchor_required'] if request.anchor_required is None else request.anchor_required,
                       'planning_roots':roots,'recorded_by':principal.id,'recorded_at':now(),'reason':request.reason,
                       'request_id':str(request.request_id),'ledger_uuid':meta['ledger_uuid'],'ledger_revision':meta['ledger_revision'],'request':body}
                response=service.envelope(project,meta,{**event,'replayed':False})
                require(len(json.dumps(response,separators=(',',':')).encode())<=15500,'LIMIT_EXCEEDED','Policy evidence exceeds local administration capacity.',413)
                db.execute('INSERT INTO application_policy_events VALUES(?,?,?,?,?)',(event['policy_revision'],str(request.request_id),digest,store.encode(event),store.digest(event)))
                replayed=False
        # Fail closed if publication fails. Retrying the same request repairs only
        # the current binding, without appending another policy event.
        with service.catalog.project(project_id,uuid,principal) as (db,_):current=policy(db)
        if current['policy_revision']==event['policy_revision']:publish_binding(service,str(uuid),current)
        return service.envelope(project,meta,{**event,'replayed':replayed})

def has_redirect(path):
    # Reject name redirection on every component. Cloud placeholder attributes
    # alone are not junctions; hydrated OneDrive planning files remain usable.
    for p in [path,*path.parents]:
        if p.is_symlink() or p.is_junction():return True
    return False

def authorized_policy(service,db):
    p=policy(db);uuid=store.metadata(db)['ledger_uuid']
    binding=binding_path(service,uuid)
    try:local=json.loads(binding.read_text(encoding='utf-8')) if binding.stat().st_size<=4096 else None
    except (OSError,ValueError):local=None
    require(local=={'ledger_uuid':uuid,'policy_sha256':store.digest(p)},'PLANNING_ACCESS_REQUIRED','Register this project’s planning roots through CLI administration.',409)
    return p

def document_inventory(service,db,directory=None):
    p=authorized_policy(service,db);roots=[Path(r) for r in p['planning_roots']]
    folders=[];candidates=set();parent=None;count=0
    if directory:
        path=Path(directory)
        require(path.is_absolute() and any(path.is_relative_to(r) for r in roots),'FORBIDDEN','Folder is outside this project’s registered planning roots.',403)
        require(not has_redirect(path),'FORBIDDEN','Planning folders cannot traverse symbolic links or junctions.',403)
        try:
            path=path.resolve(strict=True)
            require(path.is_dir() and any(path.is_relative_to(r) for r in roots),'FORBIDDEN','Folder is outside this project’s registered planning roots.',403)
        except OSError:raise Fault('DOCUMENT_UNAVAILABLE','Cannot access this folder.',409) from None
        directories=[path]
        if any(path!=r and path.parent.is_relative_to(r) for r in roots):parent=str(path.parent)
    else:
        directories=roots
        # Previously linked documents join the pool without creating another
        # mutable registry. Authorization still comes only from current roots.
        if store.metadata(db)['schema_version']==3:
            candidates.update(Path(r[0]) for r in db.execute("SELECT DISTINCT json_extract(receipt_json,'$.anchor.path') FROM application_receipts WHERE json_extract(receipt_json,'$.anchor.path') IS NOT NULL LIMIT 1000"))
    try:
        for root in directories:
            require(not has_redirect(root),'FORBIDDEN','Planning folders cannot traverse symbolic links or junctions.',403)
            with os.scandir(root) as entries:
                for entry in entries:
                    count+=1;require(count<=1000,'LIMIT_EXCEEDED','Planning folder inventory exceeds 1000 entries.',413)
                    child=Path(entry.path)
                    if entry.name.startswith('.') or has_redirect(child):continue
                    if directory and entry.is_dir(follow_symlinks=False):folders.append({'path':str(child),'name':entry.name})
                    elif entry.is_file(follow_symlinks=False) and child.suffix.lower()=='.json':candidates.add(child)
    except OSError:raise Fault('DOCUMENT_UNAVAILABLE','Cannot access this folder.',409) from None
    docs=[];remaining=[16*1024*1024]
    for path in sorted(candidates):
        if not any(path.is_relative_to(r) for r in roots) or has_redirect(path):continue
        try:
            size=path.stat().st_size
            if size>4*1024*1024:continue
            doc=read_document(service,db,str(path),byte_budget=remaining)
        except Fault as exc:
            if exc.code in ('DOCUMENT_UNAVAILABLE','UNSUPPORTED_ANCHOR','DOCUMENT_CHANGED'):continue
            raise
        except OSError:continue
        docs.append({k:doc[k] for k in ('path','document_id','version','sha256')})
    return {'documents':docs,'folders':sorted(folders,key=lambda x:x['path']),'roots':[{'path':str(r),'name':r.name} for r in roots],'directory':str(directories[0]) if directory else None,'parent':parent}

def read_document(service,db,locator,byte_budget=None):
    p=authorized_policy(service,db)
    try:
        path=Path(locator)
        require(path.is_absolute() and path.suffix.lower() in ('.json','.md'),'UNSUPPORTED_ANCHOR','Use a local canonical planning document (.json or .md).')
        source=path.with_suffix('.json')
        roots=[Path(r) for r in p['planning_roots']]
        # Check lexical containment before stat/open, then recheck resolved paths.
        require(any(source.is_relative_to(root) for root in roots),'FORBIDDEN','Document is outside this project’s registered planning roots.',403)
        require(not has_redirect(source),'FORBIDDEN','Planning documents cannot traverse symbolic links or junctions.',403)
        source=source.resolve(strict=True)
        require(any(source.is_relative_to(root.resolve(strict=True)) for root in roots),'FORBIDDEN','Document is outside this project’s registered planning roots.',403)
        with source.open('rb') as stream:
            limit=min(4*1024*1024,byte_budget[0]) if byte_budget is not None else 4*1024*1024
            before=os.fstat(stream.fileno());raw=stream.read(limit+1);after=os.fstat(stream.fileno())
        if byte_budget is not None:
            require(len(raw)<=limit,'LIMIT_EXCEEDED','Planning document inventory exceeds 16 MiB. Browse a specific folder.',413)
            byte_budget[0]-=len(raw)
        require(len(raw)<=4*1024*1024,'LIMIT_EXCEEDED','Planning document exceeds 4 MiB.',413)
        require((before.st_size,before.st_mtime_ns,before.st_ino)==(after.st_size,after.st_mtime_ns,after.st_ino),'DOCUMENT_CHANGED','Document changed. Refresh sections and retry.',409)
        value=json.loads(raw)
        require(isinstance(value,dict) and value.get('schema_version')=='codesentinel.canonical-document/v1','UNSUPPORTED_ANCHOR','Use a native canonical planning document.')
        require(isinstance(value.get('document_id'),str) and 0<len(value['document_id'])<=160,'UNSUPPORTED_ANCHOR','Planning document has no valid identity.')
        sections=value.get('sections');require(isinstance(sections,list) and len(sections)<=500,'UNSUPPORTED_ANCHOR','Planning document has no bounded sections.')
        choices=[];seen=set()
        for section in sections:
            require(isinstance(section,dict),'UNSUPPORTED_ANCHOR','Planning section is invalid.')
            for item,kind in [(section,'section'),*[(b,'block') for b in section.get('blocks',[])]]:
                require(isinstance(item,dict) and isinstance(item.get('id'),str) and 0<len(item['id'])<=160 and item['id'] not in seen,'UNSUPPORTED_ANCHOR','Planning anchor IDs must be unique.')
                seen.add(item['id'])
                heading=section.get('heading',section['id'])
                require(isinstance(heading,str) and len(heading)<=512,'UNSUPPORTED_ANCHOR','Planning heading is invalid.')
                choices.append({'id':item['id'],'kind':kind,'heading':heading if kind=='section' else heading+' · '+item['id'],'content_sha256':store.digest(item)})
        require(len(choices)<=2000,'LIMIT_EXCEEDED','Planning document has too many anchors.',413)
        versions=[m.get('value') for m in value.get('metadata',[]) if isinstance(m,dict) and m.get('label')=='Version']
        version=versions[0] if versions else None
        require(version is None or isinstance(version,str) and len(version)<=160,'UNSUPPORTED_ANCHOR','Invalid planning document version.')
        projection=None
        if path.suffix.lower()=='.md':
            require(not has_redirect(path),'FORBIDDEN','Planning documents cannot traverse symbolic links or junctions.',403)
            with path.open('rb') as stream:projected=stream.read(4*1024*1024+1)
            require(len(projected)<=4*1024*1024,'LIMIT_EXCEEDED','Planning projection exceeds 4 MiB.',413)
            require(projected.startswith(b'<!-- CODESENTINEL-GENERATED: canonical-markdown/v1'),'UNSUPPORTED_ANCHOR','Use the generated Markdown companion of a native canonical document.')
            marker=projected[:4096].decode('utf-8').split('-->',1)[0]
            fields=dict(line.split(': ',1) for line in marker.splitlines()[1:] if ': ' in line)
            canonical_sha=hashlib.sha256(json.dumps(value,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode()).hexdigest()
            require(fields.get('schema')=='codesentinel.canonical-document/v1' and fields.get('source-sha256')==canonical_sha,'DOCUMENT_CHANGED','Document changed. Regenerate its Markdown companion, refresh sections and retry.',409)
            projection={'path':str(path.resolve(strict=True)),'sha256':hashlib.sha256(projected).hexdigest(),'source_marker_sha256':canonical_sha}
        return {'document_id':value['document_id'],'path':str(source),'version':version,'sha256':hashlib.sha256(raw).hexdigest(),
                'projection':projection,'anchors':choices,'generator_verification':'not_checked'}
    except (OSError,ValueError,TypeError,KeyError):
        raise Fault('DOCUMENT_UNAVAILABLE','Cannot access this document.',409) from None

def resolution(db,key,revision):
    row=db.execute('SELECT r.ledger_revision,r.snapshot_json,r.snapshot_sha256,t.request_json FROM revisions r JOIN transactions t USING(ledger_revision) WHERE decision_key=? AND ledger_revision<=? ORDER BY ledger_revision',(key,revision)).fetchall()
    prior=None;closure=None
    for r in row:
        snap=json.loads(r['snapshot_json'])
        approved=any(op['op'] in ('decision.close','decision.edit-resolution') and op['key']==key for op in json.loads(r['request_json'])['operations'])
        if snap['status']=='closed' and (approved or prior is None or prior['status']!='closed' or (snap['answer'],snap['rationale'])!=(prior['answer'],prior['rationale'])):closure=r
        prior=snap
    if prior is None or prior['status']!='closed':return None
    require(closure is not None,'INTEGRITY_FAILED','Closed decision has no historical closure.',409)
    event=db.execute('SELECT event_id FROM approval_events WHERE decision_key=? AND ledger_revision=? ORDER BY operation_ordinal DESC LIMIT 1',(key,closure['ledger_revision'])).fetchone() if store.metadata(db)['schema_version']>=2 else None
    return {'resolution_id':'approval:'+event[0] if event else 'legacy:'+str(closure['ledger_revision'])+':'+closure['snapshot_sha256'],
            'closure_revision':closure['ledger_revision'],'closure_snapshot_sha256':closure['snapshot_sha256'],'approval_event_id':event[0] if event else None}

def current(db,key,revision):
    r=resolution(db,key,revision)
    if r is None:return None
    receipt=None
    if store.metadata(db)['schema_version']==3:
        row=db.execute('SELECT receipt_json FROM application_receipts WHERE decision_key=? AND resolution_id=? AND ledger_revision<=?',(key,r['resolution_id'],revision)).fetchone()
        receipt=json.loads(row[0]) if row else None
    return {**r,'recorded':bool(receipt),'linked':bool(receipt and receipt['anchor']),'receipt':receipt}

def legacy_current(value):
    """Read-only compatibility view; never rewrite stored receipt bytes."""
    return None if value is None else {k:v for k,v in value.items() if k not in ('recorded','linked')} | {'applied':value['recorded']}

def prepare(service,db,principal,request,stamp,transaction_id):
    result={};meta=store.metadata(db)
    for ordinal,op in enumerate(request.operations):
        if op.op not in ('decision.link','decision.apply'):continue
        require(meta['schema_version']==3,'UPGRADE_REQUIRED','Upgrade this ledger before recording a planning link.',409)
        data=PlanningLink.model_validate(op.data);p=policy(db)
        require(data.expected_policy_revision==p['policy_revision'],'POLICY_CHANGED','Planning-link policy changed. Review it before retrying.',409)
        state=current(db,op.key,meta['ledger_revision'])
        require(state is not None,'INVALID_TRANSITION','Only closed decisions can be linked to planning.')
        require(not state['recorded'],'ALREADY_APPLIED' if op.op=='decision.apply' else 'ALREADY_LINKED' if state['linked'] else 'ALREADY_RECORDED','This resolution already has a planning-link record. Reopen to begin a new cycle.',409)
        require(data.expected_resolution_id is None or data.expected_resolution_id==state['resolution_id'],'RESOLUTION_CHANGED','Decision resolution changed. Review before linking.',409)
        require(data.planning_document or not p['anchor_required'],'ANCHOR_REQUIRED','Select a planning document and section.')
        anchor=None
        if data.planning_document:
            doc=read_document(service,db,data.planning_document)
            require(data.expected_document_sha256 is None or data.expected_document_sha256==doc['sha256'],'DOCUMENT_CHANGED','Document changed. Refresh sections and retry.',409)
            require(data.expected_projection_sha256 is None or doc['projection'] and data.expected_projection_sha256==doc['projection']['sha256'],'DOCUMENT_CHANGED','Document changed. Refresh sections and retry.',409)
            choice=next((a for a in doc['anchors'] if a['id']==data.planning_section),None)
            require(choice is not None,'ANCHOR_NOT_FOUND','Section not found in this document.',409)
            anchor={k:v for k,v in doc.items() if k!='anchors'};anchor['section']=choice
        result[ordinal]={'schema_version':'decision-tracker.application/v1','receipt_id':str(uuid4()),'decision_key':op.key,
                         'ledger_uuid':meta['ledger_uuid'],'ledger_revision':meta['ledger_revision']+1,'operation_ordinal':ordinal,
                         **{k:state[k] for k in ('resolution_id','closure_revision','closure_snapshot_sha256','approval_event_id')},
                         'recorded_by':principal.id,'auth_method':principal.auth_method,'recorded_at':stamp,'request_id':str(request.request_id),
                         'transaction_id':transaction_id,
                         'policy_revision':p['policy_revision'],'policy_sha256':store.digest(p),'anchor_status':'found' if anchor else 'omitted',
                         'anchor':anchor,'attestation':'Resolution incorporated into the designated authoritative planning section.'}
    return result

def insert(db,receipt):
    db.execute('INSERT INTO application_receipts VALUES(?,?,?,?,?,?,?)',(receipt['receipt_id'],receipt['decision_key'],receipt['ledger_revision'],receipt['operation_ordinal'],receipt['resolution_id'],store.encode(receipt),store.digest(receipt)))

def confirm(service,db,receipts):
    # An observed change before commit must not be recorded as linked. This
    # recheck does not claim atomicity with external filesystem editors.
    for receipt in receipts.values():
        if receipt['anchor']:
            anchor=receipt['anchor'];doc=read_document(service,db,anchor['projection']['path'] if anchor['projection'] else anchor['path'])
            require(doc['sha256']==anchor['sha256'] and doc['projection']==anchor['projection'],'DOCUMENT_CHANGED','Document changed. Refresh sections and retry.',409)

def validate(db,meta):
    def check(ok):require(ok,'INTEGRITY_FAILED','Planning-link history is inconsistent.',409)
    policies={0:{'policy_revision':0,'anchor_required':True,'planning_roots':[]}}
    previous=0
    for row in db.execute('SELECT * FROM application_policy_events ORDER BY policy_revision'):
        e=json.loads(row['event_json']);UUID(e['request_id'])
        check(row['policy_revision']==previous+1 and e['policy_revision']==row['policy_revision'] and e['request_id']==row['request_id'])
        check(store.digest(e)==row['event_sha256'] and e['ledger_uuid']==meta['ledger_uuid'] and type(e['anchor_required']) is bool)
        request=PolicyChange.model_validate(e['request']);check(store.digest(e['request'])==row['request_hash'] and request.expected_policy_revision==previous)
        check(request.anchor_required is None or request.anchor_required==e['anchor_required'])
        check(0<=e['ledger_revision']<=meta['ledger_revision'] and isinstance(e['planning_roots'],list) and len(e['planning_roots'])<=16)
        check(all(isinstance(r,str) and len(r)<=1024 and Path(r).is_absolute() for r in e['planning_roots']))
        check(bool(e['recorded_by']) and bool(e['reason'].strip()))
        policies[e['policy_revision']]=e;previous=e['policy_revision']
    covered=set()
    for row in db.execute('SELECT * FROM application_receipts ORDER BY ledger_revision,operation_ordinal'):
        r=json.loads(row['receipt_json']);UUID(r['receipt_id'])
        check(store.digest(r)==row['receipt_sha256'] and all(row[k]==r[k] for k in ('receipt_id','decision_key','ledger_revision','operation_ordinal','resolution_id')))
        check(r['schema_version']=='decision-tracker.application/v1' and r['ledger_uuid']==meta['ledger_uuid'])
        p=policies.get(r['policy_revision']);check(p is not None and r['policy_sha256']==store.digest(p))
        old=resolution(db,r['decision_key'],r['ledger_revision']-1);check(old is not None and all(r[k]==old[k] for k in old))
        tx=db.execute('SELECT * FROM transactions WHERE ledger_revision=?',(r['ledger_revision'],)).fetchone();check(tx is not None)
        check(r['recorded_by']==tx['principal_id'] and r['recorded_at']==tx['recorded_at'] and r['request_id']==tx['request_id'] and r['transaction_id']==tx['transaction_id'])
        ops=json.loads(tx['request_json'])['operations'];check(0<=r['operation_ordinal']<len(ops))
        op=ops[r['operation_ordinal']];check(op['op'] in ('decision.link','decision.apply') and op['key']==r['decision_key'])
        data=PlanningLink.model_validate(op['data']);check(data.expected_policy_revision==r['policy_revision'])
        check(r['anchor_status'] in ('found','omitted') and (r['anchor'] is not None)==(r['anchor_status']=='found'))
        if r['anchor']:
            a=r['anchor'];check(a['section']['id']==data.planning_section and a['generator_verification']=='not_checked')
            check(isinstance(a['sha256'],str) and len(a['sha256'])==64 and (data.expected_document_sha256 is None or data.expected_document_sha256==a['sha256']))
            check(isinstance(a['section']['content_sha256'],str) and len(a['section']['content_sha256'])==64)
            check(data.expected_projection_sha256 is None or a['projection'] and data.expected_projection_sha256==a['projection']['sha256'])
        else:check(not p['anchor_required'] and data.planning_document is None)
        before=json.loads(db.execute('SELECT snapshot_json FROM revisions WHERE decision_key=? AND ledger_revision<? ORDER BY ledger_revision DESC LIMIT 1',(r['decision_key'],r['ledger_revision'])).fetchone()[0])
        after=json.loads(db.execute('SELECT snapshot_json FROM revisions WHERE decision_key=? AND ledger_revision=?',(r['decision_key'],r['ledger_revision'])).fetchone()[0])
        check({k:v for k,v in before.items() if k not in ('revision','updated_at')}=={k:v for k,v in after.items() if k not in ('revision','updated_at')})
        covered.add((r['ledger_revision'],r['operation_ordinal']))
    for tx in db.execute('SELECT ledger_revision,request_json FROM transactions'):
        for ordinal,op in enumerate(json.loads(tx['request_json'])['operations']):
            if op['op'] in ('decision.link','decision.apply'):check((tx['ledger_revision'],ordinal) in covered)
    for row in db.execute('SELECT * FROM schema_upgrades WHERE from_version=2 AND to_version=3'):
        e=json.loads(row['receipt_json']);check(bool(row['backup_artifact_id']) and e.get('backup_artifact_id')==row['backup_artifact_id'])
        check(e.get('ledger_uuid')==meta['ledger_uuid'] and e.get('revision')==row['ledger_revision'])
        check(row['request_hash']==store.digest({'expected_revision':row['ledger_revision'],'request_id':row['request_id']}))

def mount(app):
    from fastapi import Request, Query
    service=app.state.service;principal,identity,output=app.state.principal,app.state.identity,app.state.output
    @app.get('/api/v1/projects/{project_id}/policy')
    def show_policy(project_id:str,request:Request):
        p=principal(request);p.need('read')
        with service.catalog.project(project_id,identity(request),p) as (db,project):
            return output(request,service.envelope(project,store.metadata(db),policy(db)))
    @app.get('/api/v1/projects/{project_id}/planning-documents')
    def documents(project_id:str,request:Request,directory:str|None=Query(None,min_length=1,max_length=1024),cursor:str|None=None,limit:int=Query(50,ge=1,le=200)):
        p=principal(request);p.need('read')
        with service.catalog.project(project_id,identity(request),p) as (db,project):
            inventory=document_inventory(service,db,directory);meta=store.metadata(db)
            items=[('document:'+store.digest(d['path']),{'kind':'document',**d}) for d in inventory['documents']]+[('folder:'+store.digest(f['path']),{'kind':'folder',**f}) for f in inventory['folders']]
            context={k:v for k,v in inventory.items() if k not in ('documents','folders')}
            reserve=len(store.encode(service.envelope(project,meta,context)).encode())+2048
            data,cur,complete=service.page(items,meta,{'kind':'planning-documents','directory':directory,'inventory':store.digest(inventory),'policy':store.digest(policy(db))},cursor,limit,budget=62000-reserve)
            return output(request,service.envelope(project,meta,context|{'entries':data},next_cursor=cur,complete=complete))
    @app.get('/api/v1/projects/{project_id}/planning-document')
    def document(project_id:str,request:Request,locator:str=Query(min_length=1,max_length=1024),cursor:str|None=None,limit:int=Query(50,ge=1,le=200)):
        p=principal(request);p.need('read')
        with service.catalog.project(project_id,identity(request),p) as (db,project):
            doc=read_document(service,db,locator);meta=store.metadata(db)
            anchors,cur,complete=service.page([(a['id'],a) for a in doc['anchors']],meta,{'kind':'planning-anchors','locator':doc['path'],'sha256':doc['sha256'],'projection':doc['projection'],'policy':store.digest(policy(db))},cursor,limit)
            return output(request,service.envelope(project,meta,{**doc,'anchors':anchors},next_cursor=cur,complete=complete))
    @app.get('/api/v1/projects/{project_id}/decisions/{key}/applications',deprecated=True)
    @app.get('/api/v1/projects/{project_id}/decisions/{key}/planning-links')
    def planning_link_history(project_id:str,key:str,request:Request,cursor:str|None=None,limit:int=Query(50,ge=1,le=200)):
        p=principal(request);p.need('read')
        with service.catalog.project(project_id,identity(request),p) as (db,project):
            store.get(db,'decisions',key);meta=store.metadata(db)
            rows=[(f"{r['ledger_revision']:020d}",json.loads(r['receipt_json'])) for r in db.execute('SELECT * FROM application_receipts WHERE decision_key=?',(key,))] if meta['schema_version']==3 else []
            # Preserve cursor identity for clients resuming an older route.
            data,cur,complete=service.page(rows,meta,{'kind':'applications','key':key},cursor,limit)
            return output(request,service.envelope(project,meta,data,next_cursor=cur,complete=complete))
