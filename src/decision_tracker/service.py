"""Project-aware application service: the sole decision writer."""
import base64
import json
from uuid import uuid4
from . import store
from .catalog import Catalog
from .state import Mutator
from .models import now
from .errors import require, missing, stale, Fault

class Service:
    def __init__(self, root):
        self.catalog=Catalog(root)
        self.root=self.catalog.root
        self.on_commit=lambda project_id: None
        from .legacy import Reads
        self.legacy_reads=Reads(self)

    def envelope(self, project, meta, data, **extra):
        return {"ok":True,"project_id":project["project_id"],"ledger_uuid":meta["ledger_uuid"],
                "revision":meta["ledger_revision"],"schema_version":meta['schema_version'],"data":data,
                "complete":True,"next_cursor":None,**extra}

    def change(self, project_id, principal, request):
        # Check capabilities again before a replay so revoked permission cannot
        # disclose an outcome or replay a previously privileged operation.
        for op in request.operations:
            from .state import DECIDE
            cap="decide" if op.op in DECIDE else "propose" if request.validate_only and "write" not in principal.capabilities else "write"
            principal.need(cap)
            if isinstance(op.data.get('approval'),dict) and op.data['approval'].get('mode')=='authenticated_now':
                require(principal.auth_method=='human_password_session','FORBIDDEN','Only a signed-in person can approve now.',403)
        payload=request.model_dump(mode="json",exclude={"request_id","validate_only"})
        digest=store.digest(payload)
        with self.catalog.project(project_id,str(request.expected_ledger_uuid),principal,True) as (db,project):
            meta=store.metadata(db,request.expected_ledger_uuid)
            previous=db.execute("SELECT request_hash,result_json FROM transactions WHERE principal_id=? AND request_id=?",
                                (principal.id,str(request.request_id))).fetchone()
            if previous:
                require(previous["request_hash"]==digest,"REQUEST_ID_REUSED","Request ID was used with different content.",409)
                result=json.loads(previous["result_json"]);result["replayed"]=True
                return result
            require(meta['schema_version']>=2,'UPGRADE_REQUIRED','This project needs a data-format upgrade before changes can be saved.',409)
            if meta["ledger_revision"]!=request.expected_revision:stale(meta["ledger_revision"])
            from .state import check_new_request
            check_new_request(db, request)
            from . import approvals
            stamp=now()
            transaction_id=str(uuid4())
            require(not any(k.startswith('dt_') for k in request.attribution),'VALIDATION_ERROR','Server attribution fields cannot be supplied.')
            events=approvals.prepare(db,principal,request,stamp)
            from . import planning_links
            receipts=planning_links.prepare(self,db,principal,request,stamp,transaction_id)
            effective=request.model_copy(deep=True)
            mutation=Mutator(db,principal,effective)
            for ordinal,op in enumerate(effective.operations):
                # Internal evidence includes one server reference beyond the 32 caller sources.
                mutation.request=effective.model_copy(update={'authority_refs':events[ordinal]['sources'] if ordinal in events else request.authority_refs})
                if ordinal in events:
                    op.data.pop('approval',None);op.data.pop('expected_option_revision',None)
                mutation.apply(op)
            mutation.validate()
            for event in events.values():
                if event['kind']=='deprecate':
                    event['replacement_key']=store.get(db,'decisions',event['decision_key'])['replacement_key']
                require(len(store.encode(store.snapshot(db,event['decision_key'])).encode())+len(store.encode(event).encode())<=131072,
                        'LIMIT_EXCEEDED','Decision and approval together exceed 128 KiB.',413)
            rev=meta["ledger_revision"]+1
            for key,old in mutation.original.items():
                db.execute("UPDATE decisions SET revision=?,updated_at=? WHERE key=?",(old+1,stamp,key))
            summaries=[{k:store.get(db,"decisions",key)[k] for k in ("key","title","status","locked","revision")}
                       for key in sorted(mutation.original)]
            meta["ledger_revision"]=rev
            result=self.envelope(project,meta,summaries,request_id=str(request.request_id),
                                 replayed=False,aliases=mutation.aliases,validated=request.validate_only)
            if receipts:
                result['planning_link_receipts']=list(receipts.values())
                result['application_receipts']=list(receipts.values())  # Compatibility alias.
            require(len(store.encode(result).encode())<=60000,'LIMIT_EXCEEDED','Change outcome exceeds response capacity.',413)
            if request.validate_only:
                result["revision"]=request.expected_revision
                result["planned_revision"]=rev
                db.rollback()
                return result
            planning_links.confirm(self,db,receipts)
            db.execute("INSERT INTO transactions VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                       (rev,transaction_id,principal.id,str(request.request_id),digest,store.encode(request.attribution),
                        request.reason,store.encode(request.authority_refs),stamp,
                        request.occurred_at.isoformat() if request.occurred_at else None,store.encode(result),store.encode(payload)))
            for event in events.values():approvals.insert(db,event)
            for receipt in receipts.values():planning_links.insert(db,receipt)
            for key,old in mutation.original.items():
                snapshot=store.snapshot(db,key)
                db.execute("INSERT INTO revisions VALUES(?,?,?,?,?)",
                           (key,rev,old,store.encode(snapshot),store.digest(snapshot)))
            db.execute("UPDATE meta SET ledger_revision=? WHERE id=1",(rev,))
        # Commit occurs when the project context exits. Notifications cannot undo it.
        try:self.on_commit(project_id)
        except Exception:pass
        return result

    def _cursor(self, uuid, revision, query, last):
        obj={"v":1,"uuid":uuid,"revision":revision,"query_hash":store.digest(query),"last_key":last}
        return base64.urlsafe_b64encode(store.encode(obj).encode()).decode()

    def page(self, items, meta, query, cursor=None, limit=50, budget=62000):
        require(1<=limit<=200,"VALIDATION_ERROR","Page size must be1–200.")
        last=None
        if cursor:
            require(len(cursor)<=2048,"VALIDATION_ERROR","Invalid cursor.")
            try: parsed=json.loads(base64.urlsafe_b64decode(cursor.encode()))
            except (ValueError,UnicodeError):raise Fault("VALIDATION_ERROR","Invalid cursor.") from None
            require(isinstance(parsed,dict) and set(parsed)=={"v","uuid","revision","query_hash","last_key"} and parsed["v"]==1,
                    "VALIDATION_ERROR","Invalid cursor shape.")
            require(parsed["uuid"]==meta["ledger_uuid"] and parsed["revision"]==meta["ledger_revision"] and parsed["query_hash"]==store.digest(query),
                    "CURSOR_STALE","The result set changed. Restart pagination.",409)
            last=parsed["last_key"]
            require(isinstance(last,str),"VALIDATION_ERROR","Invalid cursor key.")
        items=sorted(items,key=lambda pair:pair[0])
        if last is not None:items=[x for x in items if x[0]>last]
        output=[];size=1024;index=0
        for key,item in items:
            item_size=len(store.encode(item).encode())
            require(item_size<=min(60000,budget-1024),"LIMIT_EXCEEDED","Item requires field chunk retrieval.",413)
            if len(output)>=limit or size+item_size>budget:break
            output.append(item);size+=item_size;index+=1
        next_cursor=self._cursor(meta["ledger_uuid"],meta["ledger_revision"],query,items[index-1][0]) if index<len(items) and index else None
        return output,next_cursor,index==len(items)

    def list_decisions(self,project_id,uuid,principal,q="",status=None,work=None,owner=None,cursor=None,limit=50):
        principal.need("read")
        query={"q":q,"status":status,"work":work,"owner":owner,"kind":"decisions"}
        require(status in (None,"","open","closed","deprecated") and work in (None,"","queued","under-investigation","deferred"),"VALIDATION_ERROR","Unknown decision filter.")
        require(len(q)<=512,"VALIDATION_ERROR","Search query too long.")
        with self.catalog.project(project_id,uuid,principal) as (db,project):
            meta=store.metadata(db,uuid);items=[]
            for row in db.execute("SELECT * FROM decisions ORDER BY key"):
                obj=store.unpack(row)
                if status and obj["status"]!=status:continue
                if work and obj["work_tag"]!=work:continue
                if owner and obj["owner_role"]!=owner:continue
                if q and q.casefold() not in " ".join(str(obj[k] or "") for k in ("key","title","question","answer","rationale")).casefold():continue
                item={k:obj[k] for k in ("key","title","status","locked","work_tag","contested","owner_role","revision","updated_at")}
                from .planning_links import current
                planning_link=current(db,obj['key'],meta['ledger_revision'])
                item['linked']=bool(planning_link and planning_link['linked'])
                item['planning_link_recorded']=bool(planning_link and planning_link['recorded'])
                item['applied']=item['planning_link_recorded']  # Compatibility alias.
                items.append((obj['key'],item))
            data,next_cursor,complete=self.page(items,meta,query,cursor,limit)
            return self.envelope(project,meta,data,next_cursor=next_cursor,complete=complete)

    def _snapshot(self,db,key,revision=None):
        if revision is None:return store.snapshot(db,key)
        require(revision>=0 and revision<=store.metadata(db)["ledger_revision"],"VALIDATION_ERROR","Invalid as-of revision.")
        row=db.execute("SELECT snapshot_json FROM revisions WHERE decision_key=? AND ledger_revision<=? ORDER BY ledger_revision DESC LIMIT 1",
                       (key,revision)).fetchone()
        if row is None:
            from .legacy import initial
            origin=initial(db,key)
            if origin is not None:return origin
            missing()
        return json.loads(row[0])

    def compact(self,item,base,revision,prefix=""):
        value=dict(item)
        for key,text in item.items():
            if isinstance(text,str) and len(text.encode())>8192:
                field=prefix+key
                value[key]={"field":field,"total_utf8_bytes":len(text.encode()),
                            "chunks_url":base+"/fields/"+field+"?revision="+str(revision)}
        return value

    def detail(self,project_id,uuid,principal,key,revision=None):
        principal.need("read")
        with self.catalog.project(project_id,uuid,principal) as (db,project):
            meta=store.metadata(db,uuid);snapshot=self._snapshot(db,key,revision)
            base=f"/api/v1/projects/{project_id}/decisions/{key}"
            snaprev=meta["ledger_revision"] if revision is None else revision
            collections={}
            for family in ("alternatives","references","links"):
                collections[family]={"count":len(snapshot.pop(family)),
                                     "url":base+"/"+("options" if family=="alternatives" else family)+"?revision="+str(snaprev)}
            data=self.compact(snapshot,base,snaprev);data["collections"]=collections
            from .approvals import latest
            data['latest_resolution_approval']=latest(db,key,snaprev)
            data['latest_deprecation_approval']=latest(db,key,snaprev,'deprecate')
            from .planning_links import current,policy,legacy_current
            data['planning_link']=current(db,key,snaprev)
            data['planning_link_policy_revision']=policy(db)['policy_revision']
            data['planning_application']=legacy_current(data['planning_link'])
            data['application_policy_revision']=data['planning_link_policy_revision']
            if meta['schema_version']==4:
                origin=db.execute('SELECT i.namespace,i.source_id,s.import_id FROM legacy_identities i JOIN legacy_native_seeds s ON s.native_key=i.native_key WHERE i.native_key=?',(key,)).fetchone()
                if origin:
                    data['legacy_origin']={**dict(origin),'fields':[{k:r[k] for k in ('field','known_state','projection_kind','origin_member_id','selector')} for r in db.execute('SELECT * FROM legacy_projections WHERE native_key=? ORDER BY field',(key,))]}
            return self.envelope(project,meta,data,as_of_revision=revision)

    def children(self,project_id,uuid,principal,key,family,cursor=None,limit=50,revision=None):
        principal.need("read")
        require(family in ("alternatives","references","links"),"VALIDATION_ERROR","Unknown collection.")
        with self.catalog.project(project_id,uuid,principal) as (db,project):
            meta=store.metadata(db,uuid);snapshot=self._snapshot(db,key,revision)
            base=f"/api/v1/projects/{project_id}/decisions/{key}"
            snaprev=meta["ledger_revision"] if revision is None else revision
            items=[(x["id"],self.compact(x,base,snaprev,family+"."+x["id"]+".")) for x in snapshot[family]]
            data,cur,complete=self.page(items,meta,{"key":key,"family":family,"asof":revision},cursor,limit)
            return self.envelope(project,meta,data,next_cursor=cur,complete=complete)

    def field(self,project_id,uuid,principal,key,field,revision,offset=0,limit=8192):
        principal.need("read")
        require(offset>=0 and 1<=limit<=16384,"VALIDATION_ERROR","Invalid chunk range.")
        with self.catalog.project(project_id,uuid,principal) as (db,project):
            meta=store.metadata(db,uuid);snapshot=self._snapshot(db,key,revision)
            parts=field.split(".");value=None
            if len(parts)==1:value=snapshot.get(field)
            elif len(parts)==3 and parts[0] in ("alternatives","references","links"):
                value=next((x.get(parts[2]) for x in snapshot[parts[0]] if x["id"]==parts[1]),None)
            require(isinstance(value,str),"VALIDATION_ERROR","Field is not a text value.")
            raw=value.encode()
            require(offset<=len(raw),"VALIDATION_ERROR","Offset exceeds field length.")
            try:raw[:offset].decode()
            except UnicodeDecodeError:raise Fault("VALIDATION_ERROR","Offset must be a UTF8 boundary.") from None
            end=min(len(raw),offset+limit)
            while end>offset:
                try:chunk=raw[offset:end].decode();break
                except UnicodeDecodeError as exc:
                    end-=1
            require(end>offset or offset==len(raw),"VALIDATION_ERROR","Chunk limit cannot hold the next character.")
            chunk=raw[offset:end].decode()
            return self.envelope(project,meta,{"text":chunk,"offset":offset,"next_offset":end if end<len(raw) else None,
                       "total_utf8_bytes":len(raw),"sha256":__import__("hashlib").sha256(raw).hexdigest()})

    def history(self,project_id,uuid,principal,key,cursor=None,limit=50):
        principal.need("read")
        with self.catalog.project(project_id,uuid,principal) as (db,project):
            store.get(db,"decisions",key);meta=store.metadata(db,uuid)
            items=[]
            for row in db.execute("SELECT r.ledger_revision,r.prior_decision_revision,r.snapshot_sha256,t.principal_id,t.reason,t.authority_refs,t.recorded_at,t.attribution FROM revisions r JOIN transactions t USING(ledger_revision) WHERE decision_key=? ORDER BY r.ledger_revision",(key,)):
                item=store.unpack(row)
                from .approvals import latest
                item['approval']=latest(db,key,item['ledger_revision'])
                row_event=db.execute("SELECT event_json FROM approval_events WHERE decision_key=? AND ledger_revision=? AND json_extract(event_json,'$.kind')='deprecate'",(key,item['ledger_revision'])).fetchone() if meta['schema_version']>=2 else None
                from .approvals import summary
                item['deprecation_approval']=summary(json.loads(row_event[0])) if row_event else None
                items.append((f'{item["ledger_revision"]:020d}',item))
            data,cur,complete=self.page(items,meta,{"key":key,"kind":"history"},cursor,limit)
            return self.envelope(project,meta,data,next_cursor=cur,complete=complete)

    def related(self,project_id,uuid,principal,key,impact=False):
        principal.need("read")
        with self.catalog.project(project_id,uuid,principal) as (db,project):
            store.get(db,"decisions",key);meta=store.metadata(db,uuid)
            edges=[store.unpack(x) for x in db.execute("SELECT * FROM links WHERE active=1 ORDER BY source_key,target_key")]
            seen={key};frontier=[key];depth=0;complete=True
            for _ in range(3 if impact else 1):
                candidates=sorted(
                    {e["source_key"] for e in edges if e["type"]=="depends_on" and e["target_key"] in frontier}
                    if impact else
                    {e["target_key"] if e["source_key"]==key else e["source_key"]
                     for e in edges if key in (e["source_key"],e["target_key"])})
                candidates=[x for x in candidates if x not in seen]
                if not candidates:frontier=[];break
                allowed=candidates[:200-(len(seen)-1)]
                if len(allowed)<len(candidates):complete=False
                frontier=allowed;seen.update(allowed);depth+=1
                if not complete:break
            if impact and frontier and any(e["target_key"] in frontier and e["source_key"] not in seen and e["type"]=="depends_on" for e in edges):complete=False
            neighbors=[]
            for k in sorted(seen-{key}):
                obj=store.get(db,"decisions",k)
                neighbors.append({f:obj[f] for f in ("key","title","status","locked","revision")})
            return self.envelope(project,meta,{"key":key,"neighbors":neighbors,"visited":len(neighbors),
                    "frontier":frontier,"depth":depth,"links_url":f"/api/v1/projects/{project_id}/decisions/{key}/links",
                    "truncated":not complete,"context_fingerprint":self.context_fingerprint(db,key)},complete=complete)

    @staticmethod
    def context_fingerprint(db,key):
        selected=store.get(db,"decisions",key)
        edges=[dict(x) for x in db.execute("SELECT * FROM links WHERE active=1 AND (source_key=? OR target_key=?) ORDER BY id",(key,key))]
        keys=sorted({e["target_key"] if e["source_key"]==key else e["source_key"] for e in edges}-{key})
        neighbors=[(k,store.get(db,"decisions",k)["revision"]) for k in keys[:200]]
        return store.digest({"key":key,"revision":selected["revision"],"edges":edges,"neighbors":neighbors,"complete":len(keys)<=200})

    def event_snapshot(self,project_id,uuid,principal,key=None):
        principal.need("read")
        with self.catalog.project(project_id,uuid,principal) as (db,project):
            meta=store.metadata(db,uuid)
            row=db.execute("SELECT revision FROM decisions WHERE key=?",(key,)).fetchone() if key else None
            return {"version":1,"project_id":project_id,"ledger_uuid":meta["ledger_uuid"],
                    "ledger_revision":meta["ledger_revision"],"decision_key":key,
                    "decision_revision":row[0] if row else None,"selected_exists":bool(row) if key else None,
                    "context_fingerprint":self.context_fingerprint(db,key) if row else None}
