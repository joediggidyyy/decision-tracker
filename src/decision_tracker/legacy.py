"""Immutable source attachments and token-preserving legacy interchange.

The packaged schema is the wire authority. Imported source history never
becomes a backdated native transaction or a fabricated approval event.
"""
import base64
import hashlib
import hmac
import json
import re
from functools import lru_cache
from pathlib import Path
from uuid import UUID
from .errors import Fault, require, missing
from . import store

MAX_BYTES = 10 * 1024 * 1024
from .legacy_encoding import Number,parse,e1,digest,literal_type,pointer

@lru_cache(maxsize=1)
def schema():return json.loads((Path(__file__).parent/'schemas/legacy-import-v1.json').read_text(encoding='utf-8'))
def contract_digest():return hashlib.sha256((Path(__file__).parent/'schemas/legacy-import-v1.json').read_bytes()).hexdigest()

def check_shape(value,name):
    """Validate the restricted, closed schema vocabulary shipped with this version."""
    def check(value,s,path):
        if '$ref' in s:return check(value,schema()['$defs'][s['$ref'].split('/')[-1]],path)
        if 'anyOf' in s:
            for alt in s['anyOf']:
                try:check(value,alt,path);return
                except Fault:pass
            raise Fault('VALIDATION_ERROR','Schema union mismatch.',422,{'field':path})
        require('const' not in s or value==s['const'],'VALIDATION_ERROR','Schema constant mismatch.',field=path)
        require('enum' not in s or value in s['enum'],'VALIDATION_ERROR','Schema enum mismatch.',field=path)
        kind=s.get('type')
        types={'object':dict,'array':list,'string':str,'integer':int,'boolean':bool,'null':type(None)}
        require(kind is None or type(value) is types[kind],'VALIDATION_ERROR','Schema type mismatch.',field=path)
        if kind=='object':
            require(set(s.get('required',[]))<=value.keys() and (s.get('additionalProperties') is not False or value.keys()<=s['properties'].keys()),'VALIDATION_ERROR','Schema fields mismatch.',field=path)
            for k,v in value.items():check(v,s['properties'][k],path+'.'+k)
        if kind=='array':
            require(len(value)<=20000,'LIMIT_EXCEEDED','Legacy table exceeds 20,000 rows.',413)
            for i,v in enumerate(value):check(v,s['items'],path+'['+str(i)+']')
        if kind=='string':
            require(len(value.encode('utf-8'))<=MAX_BYTES,'LIMIT_EXCEEDED','Legacy value exceeds capacity.',413)
            require('pattern' not in s or re.fullmatch(s['pattern'],value) is not None,'VALIDATION_ERROR','Schema pattern mismatch.',field=path)
            if s.get('format')=='uuid':
                try:require(str(UUID(value))==value,'VALIDATION_ERROR','Use a canonical UUID.',field=path)
                except ValueError:raise Fault('VALIDATION_ERROR','Invalid UUID.') from None
        if kind=='integer':require(value>=s.get('minimum',value),'VALIDATION_ERROR','Schema integer bound.',field=path)
    try:check(value,schema()['$defs'][name],name)
    except (UnicodeError,RecursionError):raise Fault('VALIDATION_ERROR','Invalid bounded Unicode or nesting.') from None

# Every row is immutable; JSON columns preserve the exact closed wire fields.
FAMILIES={'identities':'identity','versions':'version','payloads':'payload','members':'member',
          'associations':'association','relations':'relation','projections':'projection',
          'source_anchors':'anchor','absences':'absence','appearances':'appearance'}
WIRE={'source_anchors':'anchors'}
PK={'identities':['namespace','source_id'],'versions':['version_id'],'payloads':['payload_sha256'],
    'members':['member_id'],'associations':['member_id','namespace','source_id','association_kind'],
    'relations':['relation_id'],'projections':['native_key','field'],'source_anchors':['native_key','member_id'],
    'absences':['absence_id'],'appearances':['namespace','locator','source_revision']}
JSON_COLUMNS={'aliases','source_revisions','parent_commit_ids','provenance_member_ids',
              'source_endpoint','target_endpoint','accounting_member_ids'}
SORT={'identities':'namespace,source_id','versions':'namespace,locator,file_sha256',
      'payloads':'payload_sha256','members':'version_id,source_order,member_id',
      'associations':'member_id,namespace,source_id,association_kind','relations':'relation_id',
      'projections':'native_key,field','source_anchors':'native_key,member_id','absences':'version_id,selector',
      'appearances':'namespace,locator,source_order,source_revision'}
TABLES=('legacy_imports',)+tuple('legacy_'+x for x in FAMILIES)+('legacy_native_seeds',)

def sql():
    statements=['CREATE TABLE legacy_imports(import_id TEXT PRIMARY KEY,namespace TEXT NOT NULL UNIQUE,manifest_sha256 TEXT NOT NULL,contract_sha256 TEXT NOT NULL,format_version TEXT NOT NULL,target_ledger_uuid TEXT NOT NULL,request_id TEXT NOT NULL,imported_by TEXT NOT NULL,imported_at TEXT NOT NULL,receipt_json TEXT NOT NULL CHECK(json_valid(receipt_json))) STRICT',
      'CREATE TABLE legacy_native_seeds(native_key TEXT PRIMARY KEY REFERENCES decisions(key),import_id TEXT NOT NULL REFERENCES legacy_imports(import_id),origin_source_id TEXT NOT NULL,initial_snapshot_json TEXT NOT NULL CHECK(json_valid(initial_snapshot_json)),snapshot_sha256 TEXT NOT NULL) STRICT']
    for family,definition in FAMILIES.items():
        columns=[]
        for key,s in schema()['$defs'][definition]['properties'].items():
            nullable=any(a.get('type')=='null' for a in s.get('anyOf',[]))
            kind=s.get('type');typ='INTEGER' if kind=='integer' else 'TEXT'
            columns.append('"'+key+'" '+typ+('' if nullable else ' NOT NULL')+(' CHECK(json_valid("'+key+'"))' if key in JSON_COLUMNS else ''))
        statements.append('CREATE TABLE legacy_'+family+'('+','.join(columns)+',import_id TEXT NOT NULL REFERENCES legacy_imports(import_id),PRIMARY KEY('+','.join(PK[family])+')) STRICT')
    statements += ['CREATE INDEX legacy_member_order ON legacy_members(version_id,source_order,member_id)',
      'CREATE INDEX legacy_decision_members ON legacy_associations(namespace,source_id,member_id)',
      'CREATE INDEX legacy_native_identity ON legacy_identities(native_key)']
    for table in TABLES:
        for operation in ('UPDATE','DELETE'):
            statements.append('CREATE TRIGGER immutable_'+table+'_'+operation.lower()+' BEFORE '+operation+' ON '+table+" BEGIN SELECT RAISE(ABORT,'Immutable legacy history'); END")
    return ';\n'.join(statements)+';\n'

def rows(db,family):
    output=[]
    for row in db.execute('SELECT * FROM legacy_'+family+' ORDER BY '+SORT[family]):
        item=dict(row)
        for k in JSON_COLUMNS&item.keys():item[k]=json.loads(item[k])
        output.append(item)
    return output

def initial(db,key):
    if store.metadata(db)['schema_version']<4:return None
    row=db.execute('SELECT initial_snapshot_json,snapshot_sha256,import_id FROM legacy_native_seeds WHERE native_key=?',(key,)).fetchone()
    if row is None:return None
    snap=json.loads(row[0]);require(store.digest(snap)==row[1],'INTEGRITY_FAILED','Import seed snapshot hash differs.',409)
    return snap

SPARSE={'question','answer','rationale','authority_refs','work_tag','deprecation_kind','deprecation_reason','defer_reason','resume_trigger'}
def context(db,key):
    origin=initial(db,key)
    if not origin:return None
    sparse={}
    for r in db.execute('SELECT field,known_state,projection_json FROM legacy_projections WHERE native_key=?',(key,)):
        if r['field'] in SPARSE:
            v=json.loads(r['projection_json'])
            if v in (None,'',[]):
                require(v==origin[r['field']],'INTEGRITY_FAILED','Invalid sparse origin projection.',409)
                sparse[r['field']]=v
    return {'legacy_sparse':sparse}

def validate_request(value):
    check_shape(value,'request')
    require(len(e1(value).encode())<=MAX_BYTES,'LIMIT_EXCEEDED','Legacy import exceeds 10MiB.',413)
    require(value['contract_sha256']==contract_digest(),'CONTRACT_CHANGED','Legacy import contract differs from the installed schema.',409)
    require(value==canonical_order(value),'VALIDATION_ERROR','Use deterministic legacy table ordering.')
    require(re.fullmatch(r'[a-z][a-z0-9-]{0,47}',value['namespace']) is not None,'VALIDATION_ERROR','Invalid source namespace.')
    require(len(value['identities'])<=500,'LIMIT_EXCEEDED','Legacy project exceeds 500 decisions.',413)
    def index(family,key):
        result={}
        for row in value[family]:
            k=key(row);require(k not in result,'VALIDATION_ERROR','Duplicate legacy identity.',table=family);result[k]=row
        return result
    versions=index('versions',lambda r:r['version_id']);payloads=index('payloads',lambda r:r['payload_sha256'])
    members=index('members',lambda r:r['member_id']);identities=index('identities',lambda r:(r['namespace'],r['source_id']))
    projections=index('projections',lambda r:(r['native_key'],r['field']));seeds=index('native_seeds',lambda r:r['native_key'])
    native={r['native_key'] for r in identities.values()}
    require(len(native)==len(identities) and native==set(seeds),'VALIDATION_ERROR','Seed/identity cardinality differs.')
    for family,definition in FAMILIES.items():
        wire=WIRE.get(family,family);index(wire,lambda r:tuple(e1(r[k]) for k in PK[family]))
    aliases={}
    for ident in identities.values():
        require(ident['namespace']==value['namespace'],'VALIDATION_ERROR','Cross-namespace identity.')
        for alias in [ident['source_id']]+ident['aliases']:
            require(alias and (alias not in aliases or aliases[alias]==ident['source_id']),'AMBIGUOUS_SOURCE_ID','Ambiguous source identity.',409)
            aliases[alias]=ident['source_id']
    decoded={}
    for p in payloads.values():
        v=parse(p['value_json']);raw=e1(v).encode()
        require(raw.decode()==p['value_json'] and hashlib.sha256(raw).hexdigest()==p['payload_sha256'] and len(raw)==p['encoded_bytes'] and literal_type(v)==p['literal_type'],'INTEGRITY_FAILED','Payload encoding/type/hash differs.',409)
        decoded[p['payload_sha256']]=v
    for v in versions.values():
        require(v['namespace']==value['namespace'] and v['locator']==v['locator'].replace('\\','/'),'VALIDATION_ERROR','Use the exact slash-normalized source locator.')
        require(v['version_id']==digest(['legacy-version/v1',v['namespace'],v['locator'],v['file_sha256']]),'INTEGRITY_FAILED','Version identity differs.',409)
        require(set(v['provenance_member_ids'])<=members.keys(),'VALIDATION_ERROR','Unknown provenance member.')
    for m in members.values():
        require(m['version_id'] in versions and m['payload_sha256'] in payloads,'VALIDATION_ERROR','Unknown member version or payload.')
        require(m['member_id']==digest(['legacy-member/v1',m['version_id'],m['selector']]),'INTEGRITY_FAILED','Member identity differs.',409)
    for a in value['associations']:
        require(a['member_id'] in members and (a['namespace'],a['source_id']) in identities,'VALIDATION_ERROR','Unknown association endpoint.')
    association={(a['member_id'],a['namespace'],a['source_id']) for a in value['associations']}
    for r in value['relations']:
        require(r['member_id'] in members and members[r['member_id']]['version_id']==r['version_id'],'VALIDATION_ERROR','Relation version/member differs.')
        require(r['relation_id']==digest(['legacy-relation/v1',r['member_id'],r['relation_type'],r['source_endpoint'],r['target_endpoint'],r['source_order']]),'INTEGRITY_FAILED','Relation identity differs.',409)
        pointer(decoded[members[r['member_id']]['payload_sha256']],r['literal_pointer'])
        for endpoint in (r['source_endpoint'],r['target_endpoint']):
            require(endpoint['namespace']==value['namespace'] and (endpoint['literal_member_id'] is None or endpoint['literal_member_id'] in members),'VALIDATION_ERROR','Unknown relation literal endpoint.')
            if endpoint['kind']=='decision':require((endpoint['namespace'],endpoint['source_id']) in identities,'VALIDATION_ERROR','Unknown decision relation endpoint.')
    allowed=set(__import__('decision_tracker.models',fromlist=['Decision']).Decision.model_fields)-{'key','revision','created_at','updated_at','evidence_state'}
    for p in projections.values():
        require(p['native_key'] in native and p['field'] in allowed,'VALIDATION_ERROR','Unknown projection field or decision.')
        v=parse(p['projection_json']);require(e1(v)==p['projection_json'] and digest(v)==p['projection_sha256'],'INTEGRITY_FAILED','Projection encoding/hash differs.',409)
        if p['projection_kind'] in ('exact','attributed-summary'):
            require(p['origin_member_id'] in members and p['selector'] is not None,'VALIDATION_ERROR','Source projection needs a literal origin.')
            ident=next(x for x in identities.values() if x['native_key']==p['native_key'])
            require((p['origin_member_id'],ident['namespace'],ident['source_id']) in association,'VALIDATION_ERROR','Projection origin is not associated with its decision.')
            original=pointer(decoded[members[p['origin_member_id']]['payload_sha256']],p['selector'])
            require(e1(project_value(p['field'],original))==p['projection_json'],'INTEGRITY_FAILED','Projection does not match its source.',409)
            require(p['known_state']==('exact_source' if p['projection_kind']=='exact' else 'attributed_source_summary'),'VALIDATION_ERROR','Projection attribution differs.')
        elif p['projection_kind']=='none':
            require(v is None or (p['field']=='authority_refs' and v==[]),'VALIDATION_ERROR','Nonprojection must remain unknown.')
            require(p['known_state'] in ('not_projected','explicit_source_unknown'),'VALIDATION_ERROR','Unknown projection state.')
        else:
            require(p['field'] in ('title','baseline') and p['known_state']=='not_projected','VALIDATION_ERROR','Import provenance is not a source fact.')
    for key,s in seeds.items():
        ident=next(x for x in identities.values() if x['native_key']==key)
        require(s['origin_source_id']==ident['source_id'] and s['projection_fields']==[p for p in value['projections'] if p['native_key']==key],'VALIDATION_ERROR','Seed projection inventory differs.')
        fields={p['field'] for p in s['projection_fields']}
        require({'title','question','answer','rationale','status','locked','work_tag','authority_refs'}<=fields,'VALIDATION_ERROR','Seed must explicitly map required fields and unknowns.')
    for a in value['anchors']:
        require(a['native_key'] in native and a['member_id'] in members,'VALIDATION_ERROR','Unknown source anchor.')
        version=versions[members[a['member_id']]['version_id']]
        require(a['file_sha256']==version['file_sha256'] and a['original_locator']==version['locator'],'INTEGRITY_FAILED','Source anchor identity differs.',409)
    for a in value['absences']:
        require(a['version_id'] in versions and set(a['accounting_member_ids'])<=members.keys(),'VALIDATION_ERROR','Unknown absence context.')
        require(a['absence_id']==digest(['legacy-absence/v1',a['version_id'],a['selector']]) and not any(m['version_id']==a['version_id'] and m['selector']==a['selector'] for m in members.values()),'INTEGRITY_FAILED','Absence identity or presence differs.',409)
    for a in value['appearances']:
        require(a['namespace']==value['namespace'] and (a['version_id'] in versions if a['file_presence']=='present' else a['version_id'] is None),'VALIDATION_ERROR','Appearance presence differs.')
        if a['version_id']:
            v=versions[a['version_id']];require(a['locator']==v['locator'] and a['source_revision'] in v['source_revisions'],'VALIDATION_ERROR','Appearance version/revision differs.')
    for v in versions.values():
        require(set(v['source_revisions'])=={a['source_revision'] for a in value['appearances'] if a['version_id']==v['version_id']},'VALIDATION_ERROR','Version appearances are incomplete.')
    return digest({k:v for k,v in value.items() if k!='request_id'})

def populate(db,value,principal,stamp):
    import_id=validate_request(value)
    receipt={'request_hash':digest(value),'source_manifest_sha256':value['source_manifest_sha256'],'contract_sha256':value['contract_sha256'],'target_ledger_uuid':value['target_ledger_uuid']}
    db.execute('INSERT INTO legacy_imports VALUES(?,?,?,?,?,?,?,?,?,?)',(import_id,value['namespace'],value['source_manifest_sha256'],value['contract_sha256'],value['format'],value['target_ledger_uuid'],value['request_id'],principal.id,stamp,store.encode(receipt)))
    # Deferred FKs allow identities to bind the subsequently materialized decisions.
    for family in FAMILIES:
        wire=WIRE.get(family,family)
        for row in value[wire]:
            data={**row,'import_id':import_id};cols=list(data)
            vals=[store.encode(data[k]) if k in JSON_COLUMNS else data[k] for k in cols]
            db.execute('INSERT INTO legacy_'+family+'('+','.join('"'+k+'"' for k in cols)+') VALUES('+','.join('?' for _ in cols)+')',vals)
    from .models import Decision
    for s in value['native_seeds']:
        fields={p['field']:json.loads(p['projection_json']) for p in s['projection_fields']}
        # None is explicit; never let model defaults invent source work state.
        obj={'key':s['native_key'],'created_at':stamp,'updated_at':stamp,**fields}
        context={'legacy_sparse':{p['field']:fields[p['field']] for p in s['projection_fields'] if p['field'] in SPARSE and fields[p['field']] in (None,'',[])}}
        obj=Decision.model_validate(obj,context=context).model_dump(mode='json')
        store.save(db,'decisions',obj,context=context)
        snap=store.snapshot(db,obj['key'])
        db.execute('INSERT INTO legacy_native_seeds VALUES(?,?,?,?,?)',(obj['key'],import_id,s['origin_source_id'],store.encode(snap),store.digest(snap)))
    return import_id

def validate(db):
    # Reconstruct the immutable request and validate every ID, type, association
    # and inverse projection, independently of current native mutations.
    origins=db.execute('SELECT * FROM legacy_imports').fetchall()
    require(len(origins)<=1,'INTEGRITY_FAILED','A ledger has at most one legacy origin.',409)
    for origin in origins:
        value={'format':origin['format_version'],'contract_sha256':origin['contract_sha256'],'source_manifest_sha256':origin['manifest_sha256'],'namespace':origin['namespace'],'request_id':origin['request_id'],'target_ledger_uuid':origin['target_ledger_uuid']}
        for family in FAMILIES:
            value[WIRE.get(family,family)]=[{k:v for k,v in r.items() if k!='import_id'} for r in rows(db,family) if r['import_id']==origin['import_id']]
        value['native_seeds']=[]
        for row in db.execute('SELECT * FROM legacy_native_seeds WHERE import_id=? ORDER BY native_key',(origin['import_id'],)):
            snap=initial(db,row['native_key']);require(snap['revision']==1 and snap['key']==row['native_key'],'INTEGRITY_FAILED','Invalid origin revision.',409)
            value['native_seeds'].append({'native_key':row['native_key'],'origin_source_id':row['origin_source_id'],'projection_fields':[p for p in value['projections'] if p['native_key']==row['native_key']]})
            for p in value['native_seeds'][-1]['projection_fields']:
                expected=json.loads(p['projection_json']);actual=snap[p['field']]
                if p['field']=='occurred_at' and expected and actual:
                    from datetime import datetime
                    same=datetime.fromisoformat(expected)==datetime.fromisoformat(actual)
                else:same=expected==actual
                require(same,'INTEGRITY_FAILED','Seed projection differs.',409)
        # Canonical table order is required at admission so reconstruction is exact.
        require(validate_request(value)==origin['import_id'] and digest(value)==json.loads(origin['receipt_json'])['request_hash'],'INTEGRITY_FAILED','Immutable import identity differs.',409)
        require(origin['target_ledger_uuid']==store.metadata(db)['ledger_uuid'],'INTEGRITY_FAILED','Import target differs.',409)

def canonical_order(value):
    orders={'identities':lambda r:(r['namespace'],r['source_id']),'versions':lambda r:(r['namespace'],r['locator'],r['file_sha256']),
      'payloads':lambda r:r['payload_sha256'],'members':lambda r:(r['version_id'],r['source_order'],r['member_id']),
      'associations':lambda r:(r['member_id'],r['namespace'],r['source_id'],r['association_kind']),'relations':lambda r:r['relation_id'],
      'projections':lambda r:(r['native_key'],r['field']),'anchors':lambda r:(r['native_key'],r['member_id']),
      'absences':lambda r:(r['version_id'],r['selector']),'appearances':lambda r:(r['namespace'],r['locator'],r['source_order'],r['source_revision']),
      'native_seeds':lambda r:r['native_key']}
    return {**value,**{k:sorted(value[k],key=order) for k,order in orders.items()}}

def project_value(field,original):
    """Only the exact semantic adapters already documented in the source maps."""
    if field=='authority_refs' and isinstance(original,str):return [original] if original else []
    if field in ('status','locked','work_tag') and isinstance(original,str) and original.startswith('['):
        tags=re.findall(r'\[([^\]]+)\]',original)
        require(' '.join('['+t+']' for t in tags)==original and set(tags)<={'locked','closed','open','queued','deferred','under-investigation'},'VALIDATION_ERROR','Unsupported source status tags.')
        statuses=set(tags)&{'locked','closed','open'};require(len(statuses)==1,'VALIDATION_ERROR','Ambiguous source status.')
        if field=='status':return 'open' if 'open' in tags else 'closed'
        if field=='locked':return 'locked' in tags
        work=set(tags)&{'queued','deferred','under-investigation'};require(len(work)<=1,'VALIDATION_ERROR','Ambiguous source work state.')
        return next(iter(work),None)
    return original

class Reads:
    def __init__(self,service):
        self.service=service
        folder=service.root/'legacy-cursors';folder.mkdir(exist_ok=True)
        path=folder/'key'
        if not path.exists():
            import os
            with path.open('xb') as f:f.write(os.urandom(32));f.flush();os.fsync(f.fileno())
        self.secret=path.read_bytes()
    def source_key(self,db,namespace,source_id):
        require(store.metadata(db)['schema_version']==4,'NOT_FOUND','This project has no legacy history.',404)
        matches=[r['native_key'] for r in rows(db,'identities') if r['namespace']==namespace and source_id in [r['source_id']]+r['aliases']]
        if not matches:missing()
        require(len(set(matches))==1,'AMBIGUOUS_SOURCE_ID','Ambiguous source identity.',409)
        return matches[0]
    def page(self,items,meta,query,cursor,limit):
        require(type(limit) is int and 1<=limit<=200,'VALIDATION_ERROR','Page size must be 1–200.')
        binding={'uuid':meta['ledger_uuid'],'revision':meta['ledger_revision'],'query':store.digest(query),'limit':limit};start=0
        if cursor:
            try:
                require(len(cursor)<=2048,'VALIDATION_ERROR','Invalid cursor.')
                raw,signature=cursor.split('.');raw=base64.urlsafe_b64decode(raw)
                require(hmac.compare_digest(signature,hmac.new(self.secret,raw,hashlib.sha256).hexdigest()),'VALIDATION_ERROR','Invalid cursor signature.')
                data=json.loads(raw);require(set(data)==set(binding)|{'start'} and all(data[k]==v for k,v in binding.items()),'CURSOR_STALE','Legacy result changed. Restart pagination.',409)
                start=data['start'];require(type(start) is int and 0<=start<=len(items),'VALIDATION_ERROR','Invalid cursor position.')
            except (ValueError,UnicodeError):raise Fault('VALIDATION_ERROR','Invalid cursor.') from None
        out=[];size=2048
        for item in items[start:]:
            n=len(store.encode(item).encode())
            require(n<=58000,'LIMIT_EXCEEDED','Legacy descriptor exceeds capacity.',413)
            if len(out)==limit or size+n>60000:break
            out.append(item);size+=n
        end=start+len(out);following=None
        if end<len(items):
            raw=store.encode({**binding,'start':end}).encode();following=base64.urlsafe_b64encode(raw).decode()+'.'+hmac.new(self.secret,raw,hashlib.sha256).hexdigest()
        return out,following,following is None
    def read(self,project_id,uuid,principal,kind,key=None,namespace=None,source_id=None,version_id=None,payload=None,offset=0,limit=50,cursor=None):
        principal.need('read')
        with self.service.catalog.project(project_id,uuid,principal) as (db,project):
            meta=store.metadata(db);require(meta['schema_version']==4,'NOT_FOUND','This project has no legacy history.',404)
            origins=db.execute('SELECT * FROM legacy_imports').fetchall();require(len(origins)==1,'NOT_FOUND','Legacy origin unavailable.',404);origin=origins[0]
            if source_id:
                selected=self.source_key(db,namespace or origin['namespace'],source_id)
                require(key is None or key==selected,'NOT_FOUND','Source decision differs.',404);key=selected
            if key:
                store.get(db,'decisions',key)
                ids=db.execute('SELECT namespace,source_id FROM legacy_identities WHERE native_key=?',(key,)).fetchall()
                allowed={r[0] for n,s in ids for r in db.execute('SELECT member_id FROM legacy_associations WHERE namespace=? AND source_id=?',(n,s))}
            else:allowed=None
            if version_id:require(db.execute('SELECT 1 FROM legacy_versions WHERE version_id=?',(version_id,)).fetchone() is not None,'NOT_FOUND','Source version unavailable.',404)
            data={'import_id':origin['import_id'],'namespace':origin['namespace'],'source_version_id':version_id}
            members=rows(db,'members')
            selected=[m for m in members if (allowed is None or m['member_id'] in allowed) and (version_id is None or m['version_id']==version_id)]
            if kind=='payload':
                require(type(offset) is int and offset>=0 and type(limit) is int and 1<=limit<=16384,'VALIDATION_ERROR','Invalid payload chunk bounds.')
                require(allowed is None or any(m['member_id'] in allowed and m['payload_sha256']==payload for m in members),'NOT_FOUND','Payload is not associated with this decision.',404)
                row=db.execute('SELECT * FROM legacy_payloads WHERE payload_sha256=?',(payload,)).fetchone()
                if row is None:missing()
                raw=row['value_json'].encode();require(hashlib.sha256(raw).hexdigest()==payload and len(raw)==row['encoded_bytes'],'INTEGRITY_FAILED','Payload hash differs.',409)
                require(offset<=len(raw),'VALIDATION_ERROR','Offset exceeds payload length.')
                end=min(len(raw),offset+limit)
                data={'import_id':origin['import_id'],'payload_sha256':payload,'literal_type':row['literal_type'],'encoded_bytes':len(raw),'offset':offset,'chunk_base64':base64.b64encode(raw[offset:end]).decode(),'next_offset':end if end<len(raw) else None}
                return self.service.envelope(project,meta,data,complete=end==len(raw))
            if kind=='as-of':
                require(version_id,'VALIDATION_ERROR','Supply a source version.')
                absences=[r for r in rows(db,'absences') if r['version_id']==version_id and (allowed is None or set(r['accounting_member_ids'])&allowed)]
                require(bool(selected or absences),'NOT_FOUND','Decision is unavailable at this source version.',404)
                require(len(selected)+len(absences)<=200,'LIMIT_EXCEEDED','Use paginated history for this source version.',413)
                data={'import_id':origin['import_id'],'version_id':version_id,'presence':'present' if selected else 'absent','member_ids':[m['member_id'] for m in selected],'absence_ids':[a['absence_id'] for a in absences],'source_status_member_id':None,'source_status_pointer':None}
                for p in rows(db,'projections'):
                    if p['native_key']==key and p['field']=='status' and p['origin_member_id'] in data['member_ids']:data.update(source_status_member_id=p['origin_member_id'],source_status_pointer=p['selector'])
                return self.service.envelope(project,meta,data)
            family='relations' if kind=='relations' else 'members'
            items=rows(db,'relations') if family=='relations' else selected
            if family=='relations':items=[r for r in items if (allowed is None or r['member_id'] in allowed) and (version_id is None or r['version_id']==version_id)]
            items=[{k:v for k,v in r.items() if k!='import_id'} for r in items]
            items.sort(key=lambda r:(r['version_id'],r['source_order'],r.get('member_id'),r.get('relation_id','')))
            query={'kind':family,'import_id':origin['import_id'],'key':key,'version_id':version_id}
            out,cur,complete=self.page(items,meta,query,cursor,limit);data[family]=out
            return self.service.envelope(project,meta,data,next_cursor=cur,complete=complete)

    def records(self,project_id,uuid,principal,family,key=None,cursor=None,limit=50):
        principal.need('read');require(family in FAMILIES,'VALIDATION_ERROR','Unknown legacy collection.')
        with self.service.catalog.project(project_id,uuid,principal) as (db,project):
            meta=store.metadata(db);require(meta['schema_version']==4,'NOT_FOUND','Legacy history unavailable.',404)
            origin=db.execute('SELECT import_id,namespace FROM legacy_imports').fetchone()
            require(origin is not None,'NOT_FOUND','Legacy history unavailable.',404)
            items=rows(db,family)
            if key:
                store.get(db,'decisions',key)
                identities=[r for r in rows(db,'identities') if r['native_key']==key]
                sources={(r['namespace'],r['source_id']) for r in identities}
                member_ids={r['member_id'] for r in rows(db,'associations') if (r['namespace'],r['source_id']) in sources}
                members=[r for r in rows(db,'members') if r['member_id'] in member_ids]
                versions={r['version_id'] for r in members};payloads={r['payload_sha256'] for r in members}
                if family in ('identities','projections','source_anchors'):items=[r for r in items if r['native_key']==key]
                elif family=='payloads':items=[r for r in items if r['payload_sha256'] in payloads]
                elif family in ('members','relations','associations'):items=[r for r in items if r['member_id'] in member_ids]
                elif family in ('versions','appearances'):items=[r for r in items if r['version_id'] in versions]
                elif family=='absences':items=[r for r in items if set(r['accounting_member_ids'])&member_ids]
            # Payload bytes always use the hashed, base64 chunk route.
            items=[{k:v for k,v in r.items() if k not in ('import_id','value_json')} for r in items]
            out,cur,complete=self.page(items,meta,{'kind':family,'key':key,'import_id':origin['import_id']},cursor,limit)
            return self.service.envelope(project,meta,{'import_id':origin['import_id'],'namespace':origin['namespace'],'kind':family,'rows':out},next_cursor=cur,complete=complete)
