"""Only these transitions may change a decision aggregate."""
from uuid import uuid4
from . import store
from .models import Decision, Option, Reference, Link
from .errors import require, stale

DECIDE = {"decision.close", "decision.reopen", "decision.lock", "decision.amend",
          "decision.deprecate", "decision.edit-resolution"}
CREATE_FIELDS = {"title","question","answer","rationale","owner_role","work_tag","defer_reason","resume_trigger","occurred_at","evidence_state"}

def fields(data, allowed):
    require(not (set(data)-set(allowed)), "VALIDATION_ERROR", "Unknown operation fields.",
            fields=sorted(set(data)-set(allowed)))
    return data

class Mutator:
    def __init__(self, db, principal, request):
        self.db, self.principal, self.request = db, principal, request
        self.original, self.aliases = {}, {}

    def key(self, value):
        if value and value.startswith("@"):
            require(value[1:] in self.aliases, "VALIDATION_ERROR", "Unknown batch reference.")
            return self.aliases[value[1:]]
        return value

    def touch(self, key, protected=False):
        obj = store.get(self.db, "decisions", self.key(key))
        key = obj["key"]
        if key not in self.original:
            expected = self.request.expected_decision_revisions.get(key)
            require(expected is not None, "VALIDATION_ERROR", "Supply every affected decision revision.", key=key)
            if expected != obj["revision"]: stale(obj["revision"])
            self.original[key] = obj["revision"]
        require(len(self.original) <= 25, "LIMIT_EXCEEDED", "A batch may touch at most25 decisions.", 413)
        if not protected:
            require(not obj["locked"], "LOCKED_BASELINE", "Amend the protected baseline instead.", 409)
            require(obj["status"] != "deprecated", "INVALID_TRANSITION", "Deprecated decisions are terminal.")
        return obj

    def authority(self):
        self.principal.need("decide")
        require(bool(self.request.authority_refs) and all(x.strip() for x in self.request.authority_refs),
                "VALIDATION_ERROR", "This transition requires scoped authority references.")

    def create(self, data):
        fields(data, CREATE_FIELDS)
        require(self.db.execute("SELECT count(*) FROM decisions").fetchone()[0] < 500,
                "LIMIT_EXCEEDED", "The v1 project capacity is500 decisions.", 413)
        last = self.db.execute("SELECT max(key) FROM decisions").fetchone()[0]
        key = f"D{int(last[1:])+1 if last else 1:06d}"
        obj = Decision(key=key, **data).model_dump(mode="json")
        store.save(self.db,"decisions",obj)
        self.original[key] = 0
        require(len(self.original) <= 25, "LIMIT_EXCEEDED", "Too many affected decisions.", 413)
        return key

    def add_link(self, source, target, kind, **extra):
        require(source != target, "INVALID_TRANSITION", "Self relationships are not allowed.")
        require(self.db.execute("SELECT 1 FROM links WHERE source_key=? AND target_key=? AND type=? AND active=1",
                               (source,target,kind)).fetchone() is None, "RELATION_EXISTS", "Relationship already exists.", 409)
        obj = Link(id=uuid4(),source_key=source,target_key=target,type=kind,reason=self.request.reason,**extra)
        store.save(self.db, "links", obj.model_dump(mode="json"))

    def apply(self, operation):
        op, data = operation.op, dict(operation.data)
        needed = "decide" if op in DECIDE else "propose" if self.request.validate_only and "write" not in self.principal.capabilities else "write"
        self.principal.need(needed)
        require(bool(self.request.reason.strip()), "VALIDATION_ERROR", "Supply a nonblank change reason.")
        if op in DECIDE:
            self.authority()
        if op == "decision.create":
            key = self.create(data)
            if operation.client_ref:
                require(operation.client_ref not in self.aliases, "VALIDATION_ERROR", "Duplicate batch reference.")
                self.aliases[operation.client_ref] = key
            return
        obj = self.touch(operation.key, protected=op in {"decision.amend","decision.deprecate"})
        key = obj["key"]
        if op.startswith("decision."):
            action = op.split(".")[1]
            if action in ("edit","edit-resolution"):
                allowed = {"title","question","owner_role","occurred_at","evidence_state"}
                if obj["status"] == "open" or action == "edit-resolution": allowed |= {"answer","rationale"}
                if action == "edit-resolution":allowed.add("selected_option")
                fields(data, allowed)
                if action == "edit-resolution":
                    require(obj["status"] == "closed", "INVALID_TRANSITION", "Resolution editing requires a closed decision.")
                    obj["authority_refs"] = self.request.authority_refs
                if "selected_option" in data:
                    selected=data.pop("selected_option")
                    self.db.execute("UPDATE alternatives SET disposition='unselected',revision=revision+1 WHERE decision_key=? AND disposition='selected'",(key,))
                    if selected:
                        option=store.get(self.db,"alternatives",selected)
                        require(option["decision_key"]==key and option["disposition"]!="retired","INVALID_TRANSITION","Choose a current option of this decision.")
                        option["disposition"]="selected";option["revision"]+=1;store.save(self.db,"alternatives",option)
                obj.update(data)
            elif action == "close":
                fields(data, {"answer","rationale","selected_option"})
                require(obj["status"] == "open", "INVALID_TRANSITION", "Only open decisions can close.")
                obj.update(status="closed",work_tag=None,contested=False,defer_reason=None,resume_trigger=None,
                           answer=data.get("answer",obj["answer"]),rationale=data.get("rationale",obj["rationale"]),
                           authority_refs=self.request.authority_refs)
                if data.get("selected_option"):
                    option = store.get(self.db,"alternatives",data["selected_option"])
                    require(option["decision_key"]==key and option["disposition"]!="retired", "INVALID_TRANSITION", "Choose a current option of this decision.")
                    option["disposition"]="selected";option["revision"]+=1;store.save(self.db,"alternatives",option)
            elif action == "reopen":
                fields(data, {"impact"})
                require(obj["status"]=="closed" and data.get("impact"), "INVALID_TRANSITION", "Reopening needs a closed decision and impact statement.")
                obj.update(status="open",work_tag="under-investigation",authority_refs=self.request.authority_refs)
                self.db.execute("UPDATE alternatives SET disposition='unselected',revision=revision+1 WHERE decision_key=? AND disposition='selected'",(key,))
            elif action == "lock":
                fields(data, {"baseline"})
                require(obj["status"]=="closed" and bool(data.get("baseline","").strip()), "INVALID_TRANSITION", "Lock a closed decision with a baseline identifier.")
                obj.update(locked=True,baseline=data["baseline"],authority_refs=self.request.authority_refs)
            elif action == "deprecate":
                fields(data, {"kind","replacement_key"})
                require(obj["status"]!="deprecated", "INVALID_TRANSITION", "Decision already deprecated.")
                kind=data.get("kind"); replacement=self.key(data.get("replacement_key"))
                require(kind in ("superseded","obsolete","withdrawn","duplicate","error"),"VALIDATION_ERROR","Choose a deprecation subtype.")
                if kind in ("superseded","duplicate"):
                    require(replacement and replacement!=key,"INVALID_TRANSITION","This subtype needs a distinct replacement.")
                    target=self.touch(replacement,protected=True)
                    require(target["status"]!="deprecated","INVALID_TRANSITION","Replacement cannot be deprecated.")
                    if kind=="superseded":
                        require(target["status"]=="closed","INVALID_TRANSITION","Superseding decision must be closed.")
                        self.add_link(replacement,key,"supersedes")
                elif replacement:
                    self.touch(replacement,protected=True)
                obj.update(status="deprecated",locked=False,work_tag=None,contested=False,defer_reason=None,resume_trigger=None,
                           deprecation_kind=kind,deprecation_reason=self.request.reason,replacement_key=replacement,
                           authority_refs=self.request.authority_refs)
            elif action == "amend":
                fields(data, {"title","question","impact","baseline_disposition"})
                require(obj["locked"] and data.get("impact") and data.get("baseline_disposition") in ("continue","pause"),
                        "INVALID_TRANSITION","Amendment needs a locked baseline, impact and continue/pause disposition.")
                child=self.create({"title":data.get("title",obj["title"]+" amendment"),"question":data.get("question",""),
                                   "work_tag":"under-investigation"})
                self.add_link(child,key,"amends",impact=data["impact"],baseline_disposition=data["baseline_disposition"])
                if operation.client_ref:
                    require(operation.client_ref not in self.aliases,"VALIDATION_ERROR","Duplicate batch reference.")
                    self.aliases[operation.client_ref]=child
                return
            else:
                require(obj["status"]=="open","INVALID_TRANSITION","Work-state actions require an open decision.")
                if action=="defer":
                    fields(data, {"resume_trigger"})
                    require(data.get("resume_trigger"),"VALIDATION_ERROR","Supply a resumption trigger.")
                    obj.update(work_tag="deferred",defer_reason=self.request.reason,resume_trigger=data["resume_trigger"])
                elif action=="resume":
                    fields(data, set())
                    require(obj["work_tag"]=="deferred","INVALID_TRANSITION","Decision is not deferred.")
                    obj.update(work_tag="under-investigation",defer_reason=None,resume_trigger=None)
                elif action in ("challenge","resolve-challenge"):
                    fields(data, set())
                    require(obj["work_tag"] in ("under-investigation","deferred"),"INVALID_TRANSITION","Investigate or defer before recording a challenge.")
                    obj["contested"]=action=="challenge"
                elif action=="set-work":
                    fields(data, {"work_tag"})
                    require(obj["work_tag"]!="deferred" and data.get("work_tag") in ("queued","under-investigation"),
                            "INVALID_TRANSITION","Resume deferred work before changing its tag.")
                    obj["work_tag"]=data["work_tag"]
            store.save(self.db,"decisions",obj)
        elif op.startswith(("option.","reference.")):
            family,action=op.split(".");table="alternatives" if family=="option" else "references"
            model=Option if family=="option" else Reference
            permitted=set(model.model_fields)-{"id","decision_key","revision"}
            fields(data,permitted)
            if family=="option":
                require(data.get("disposition")!="selected","INVALID_TRANSITION","Select an option through close or edit-resolution.")
            if action=="add":
                child=model(id=uuid4(),decision_key=key,**data).model_dump(mode="json")
            else:
                child=store.get(self.db,table,operation.id)
                require(child["decision_key"]==key,"INVALID_TRANSITION","Child belongs to another decision.")
                require(child.get("disposition")!="retired" and not child.get("retired"),"INVALID_TRANSITION","Retired child is immutable.")
                if child.get("disposition")=="selected" or data.get("disposition") in ("selected","rejected"):
                    self.authority()
                if child.get("disposition")=="selected":
                    require(not data or set(data)<= {"position"},"INVALID_TRANSITION","Edit resolution before modifying the selected option.")
                child.update(data);child["revision"]+=1
                if action=="retire":
                    require(not data,"VALIDATION_ERROR","Retire accepts no fields.")
                    require(child.get("disposition")!="selected","INVALID_TRANSITION","Resolve the selected option before retirement.")
                    child["disposition" if family=="option" else "retired"]="retired" if family=="option" else True
            if child.get("disposition") in ("selected","rejected"):self.authority()
            require(child.get("disposition")!="rejected" or bool(child.get("reason")), "VALIDATION_ERROR","Rejected options need a reason.")
            store.save(self.db,table,child)
        elif op=="link.add":
            fields(data, {"target_key","type"})
            target=self.touch(self.key(data.get("target_key")))
            kind=data.get("type")
            require(kind in ("relates_to","depends_on"),"INVALID_TRANSITION","Amendment and supersession links require lifecycle transitions.")
            source,dest=key,target["key"]
            if kind=="relates_to":source,dest=sorted((source,dest))
            self.add_link(source,dest,kind)
        elif op=="link.unlink":
            fields(data,set())
            link=store.get(self.db,"links",operation.id)
            require(key==link["source_key"] and link["active"],"INVALID_TRANSITION","Select an active outbound relationship.")
            require(link["type"] in ("relates_to","depends_on"),"INVALID_TRANSITION","Lifecycle relationships cannot be unlinked.")
            self.touch(link["target_key"]);link["active"]=False;link["revision"]+=1;store.save(self.db,"links",link)

    def validate(self):
        for key in self.original:
            snap=store.snapshot(self.db,key)
            require(len(store.encode(snap).encode())<=131072,"LIMIT_EXCEEDED","Decision aggregate exceeds128KiB.",413)
            require(len(snap["alternatives"])<=50 and len(snap["references"])<=100,"LIMIT_EXCEEDED","Too many child records.",413)
            require(sum(x["active"] and x["source_key"]==key for x in snap["links"])<=100,"LIMIT_EXCEEDED","Too many outbound links.",413)
            selected=[x for x in snap["alternatives"] if x["disposition"]=="selected"]
            require(len(selected)<=1 and (not selected or snap["status"] in ("closed","deprecated")),
                    "INVALID_TRANSITION","Selected option requires a resolved decision and must be unique.")
        for kind in ("depends_on","supersedes"):
            graph={}
            for edge in self.db.execute("SELECT source_key,target_key FROM links WHERE active=1 AND type=?",(kind,)):
                graph.setdefault(edge[0],[]).append(edge[1])
            done=set()
            def visit(key,path):
                require(key not in path,"RELATION_CYCLE","Relationship cycle is not allowed.",409)
                if key in done:return
                for target in graph.get(key,[]):visit(target,path|{key})
                done.add(key)
            for key in graph:visit(key,set())
