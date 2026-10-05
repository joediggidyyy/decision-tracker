"""Registry transactions and serialized project access."""
import hashlib
from contextlib import closing
import json
import os
import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4, uuid5, NAMESPACE_URL
from . import store
from .config import contained
from .errors import require, missing, stale, Fault
from .models import now

class Catalog:
    def __init__(self, root):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.path = contained(self.root, "catalog.sqlite")
        self.coordinator = threading.RLock()
        if not self.path.exists():
            store.initialize(self.path)
        with store.connect(self.path) as db:
            require(db.execute("SELECT schema_version FROM catalog_meta").fetchone()[0] == 1,
                    "UNSUPPORTED_SCHEMA", "Unsupported project catalog.", 409)

    def revision(self, db):
        return db.execute("SELECT catalog_revision FROM catalog_meta WHERE id=1").fetchone()[0]

    def listing(self, principal):
        principal.need("read")
        with self.coordinator, store.connect(self.path) as db:
            rows = [self.public(dict(x)) for x in db.execute("SELECT * FROM projects ORDER BY project_id")
                    if "*" in principal.projects or x["project_id"] in principal.projects]
            return {"ok": True, "catalog_revision": self.revision(db), "data": rows, "complete": True}

    def public(self, row):
        return {k: bool(v) if k == "enabled" else v for k,v in row.items() if k != "db_path"}

    def lookup(self, db, project_id, uuid, principal, enabled=True):
        principal.project(project_id)
        row = db.execute("SELECT * FROM projects WHERE project_id=?", (project_id,)).fetchone()
        if row is None:
            missing()
        require(not enabled or row["enabled"], "PROJECT_DISABLED", "Project is disabled.", 409)
        require(str(uuid) == row["ledger_uuid"], "LEDGER_IDENTITY_MISMATCH", "Project identity changed.", 409)
        return dict(row)

    @contextmanager
    def project(self, project_id, uuid, principal, write=False):
        # The bounded local service serializes registry and ledger operations.
        # Holding this coordinator through commit prevents disable/write races.
        with self.coordinator, store.connect(self.path) as catalog:
            row = self.lookup(catalog, project_id, uuid, principal)
            path = contained(self.root, row["db_path"])
            with store.connect(path, write) as db:
                store.metadata(db, uuid)
                yield db, row

    def backup_before_change(self):
        folder=contained(self.root,"catalog-backups");folder.mkdir(exist_ok=True)
        path=folder/(str(uuid4())+".sqlite")
        with store.connect(self.path) as source,closing(sqlite3.connect(path)) as target:
            revision=self.revision(source);source.backup(target)
        with store.connect(path) as candidate:store.integrity(candidate)
        receipt={"catalog_revision":revision,"sha256":hashlib.sha256(path.read_bytes()).hexdigest(),"purpose":"before-registry-mutation"}
        path.with_suffix(".receipt.json").write_text(store.encode(receipt),encoding="utf-8")

    def mutate(self, principal, request, project_id=None):
        principal.need("registry")
        payload = request.model_dump(mode="json")
        payload["target"] = project_id
        digest = store.digest(payload)
        request_id = str(request.request_id)
        with self.coordinator:
            self.backup_before_change()
            with store.connect(self.path, True) as db:
                old = db.execute("SELECT * FROM catalog_requests WHERE principal_id=? AND request_id=?",
                                 (principal.id, request_id)).fetchone()
                if old:
                    require(old["request_hash"] == digest, "REQUEST_ID_REUSED", "Request ID has different content.", 409)
                    result = json.loads(old["response_json"]); result["replayed"] = True
                    return result
                rev = self.revision(db)
                if rev != request.expected_catalog_revision:
                    stale(rev)
                if project_id is None:
                    principal.project(request.project_id)
                    require(db.execute("SELECT 1 FROM projects WHERE project_id=?", (request.project_id,)).fetchone() is None,
                            "PROJECT_EXISTS", "Project ID already exists.", 409)
                    if request.kind == "create":
                        require(request.relative_path is None, "VALIDATION_ERROR", "Create does not accept a path.")
                        candidate = str(uuid5(NAMESPACE_URL, principal.id + ":" + request_id))
                        folder = contained(self.root, "ledgers/" + candidate)
                        folder.mkdir(parents=True, exist_ok=True)
                        manifest = contained(self.root, "ledgers/" + candidate + "/creation.json")
                        if manifest.exists():
                            claim = json.loads(manifest.read_text())
                            require(claim["request_hash"] == digest, "REQUEST_ID_REUSED", "Candidate belongs to another request.", 409)
                        else:
                            claim = {"request_hash": digest, "ledger_uuid": str(uuid4())}
                            with manifest.open("x", encoding="utf-8") as out:
                                out.write(store.encode(claim)); out.flush(); os.fsync(out.fileno())
                        path = contained(self.root, "ledgers/" + candidate + "/ledger.sqlite")
                        if not path.exists():
                            staging = contained(self.root, "ledgers/" + candidate + "/pending.sqlite")
                            require(not staging.exists(), "CANDIDATE_INCOMPLETE", "An interrupted candidate requires inspection.", 409)
                            store.initialize(staging, claim["ledger_uuid"])
                            os.replace(staging, path)
                        with store.connect(path) as ledger:
                            meta = store.metadata(ledger, claim["ledger_uuid"]); store.integrity(ledger)
                    else:
                        require(bool(request.relative_path), "VALIDATION_ERROR", "Registration requires relative_path.")
                        path = contained(self.root, request.relative_path)
                        require(path.suffix == ".sqlite" and path != self.path, "VALIDATION_ERROR", "Register a project SQLite ledger.")
                        with store.connect(path) as ledger:
                            meta = store.metadata(ledger)
                            from .artifacts import validate_history
                            validate_history(ledger)
                    relative = path.relative_to(self.root).as_posix()
                    require(db.execute("SELECT 1 FROM projects WHERE enabled=1 AND (ledger_uuid=? OR lower(db_path)=lower(?))",
                                       (meta["ledger_uuid"], relative)).fetchone() is None,
                            "DUPLICATE_LEDGER", "This ledger identity or path is already enabled.", 409)
                    row = {"project_id": request.project_id, "name": request.name,
                           "ledger_uuid": meta["ledger_uuid"], "db_path": relative, "enabled": 1,
                           "row_revision": 1, "created_at": now(), "updated_at": now()}
                    db.execute("INSERT INTO projects VALUES(?,?,?,?,?,?,?,?)", tuple(row.values()))
                else:
                    principal.project(project_id)
                    existing = db.execute("SELECT * FROM projects WHERE project_id=?", (project_id,)).fetchone()
                    if existing is None: missing()
                    row = dict(existing)
                    if request.enabled:
                        with store.connect(contained(self.root, row["db_path"])) as ledger:
                            store.metadata(ledger, row["ledger_uuid"]); store.integrity(ledger)
                        require(db.execute("SELECT 1 FROM projects WHERE enabled=1 AND project_id!=? AND (ledger_uuid=? OR lower(db_path)=lower(?))",
                                           (project_id,row["ledger_uuid"],row["db_path"])).fetchone() is None,
                                "DUPLICATE_LEDGER", "Another enabled registration uses this ledger.", 409)
                    row.update(enabled=int(request.enabled), row_revision=row["row_revision"]+1, updated_at=now())
                    db.execute("UPDATE projects SET enabled=?,row_revision=?,updated_at=? WHERE project_id=?",
                               (row["enabled"],row["row_revision"],row["updated_at"],project_id))
                result = {"ok": True, "request_id": request_id, "catalog_revision": rev+1,
                          "data": self.public(row), "replayed": False}
                db.execute("UPDATE catalog_meta SET catalog_revision=? WHERE id=1", (rev+1,))
                db.execute("INSERT INTO catalog_requests VALUES(?,?,?,?,?)",
                           (principal.id,request_id,digest,store.encode(result),rev+1))
                return result
