"""SQLite v1 schema, complete snapshots and immutable transaction history."""
import hashlib
import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from .errors import Fault, require, missing
from .models import Decision, Option, Reference, Link, now

def encode(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)

def digest(value):
    return hashlib.sha256(encode(value).encode()).hexdigest()

@contextmanager
def connect(path, write=False):
    path = Path(path)
    require(path.is_file(), "NOT_FOUND", "Database is unavailable.", 404)
    db = sqlite3.connect(path.as_uri() + "?mode=rw", uri=True, isolation_level=None, timeout=5)
    db.row_factory = sqlite3.Row
    try:
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("PRAGMA synchronous=FULL")
        db.execute("PRAGMA busy_timeout=5000")
        db.execute("BEGIN IMMEDIATE" if write else "BEGIN")
        yield db
        db.commit()
    except sqlite3.OperationalError as exc:
        db.rollback()
        if "locked" in str(exc).lower() or "busy" in str(exc).lower():
            raise Fault("RETRY_LATER", "The database is busy.", 503, recovery="Retry the identical request later.") from None
        raise Fault("DATABASE_UNAVAILABLE", "Database operation failed.", 503,
                    recovery="Stop writes and inspect the retained database.") from None
    except BaseException:
        db.rollback()
        raise
    finally:
        db.close()

LEDGER_SQL = """
CREATE TABLE meta(id INTEGER PRIMARY KEY CHECK(id=1),ledger_uuid TEXT NOT NULL UNIQUE,
 schema_version INTEGER NOT NULL CHECK(schema_version=1),ledger_revision INTEGER NOT NULL CHECK(ledger_revision>=0),
 created_at TEXT NOT NULL) STRICT;
CREATE TABLE decisions(
 key TEXT PRIMARY KEY,title TEXT NOT NULL,question TEXT NOT NULL,answer TEXT,rationale TEXT,
 status TEXT NOT NULL CHECK(status IN ('open','closed','deprecated')),
 locked INTEGER NOT NULL CHECK(locked IN (0,1)),baseline TEXT,
 work_tag TEXT CHECK(work_tag IN ('queued','under-investigation','deferred')),
 contested INTEGER NOT NULL CHECK(contested IN (0,1)),owner_role TEXT,defer_reason TEXT,resume_trigger TEXT,
 deprecation_kind TEXT,deprecation_reason TEXT,replacement_key TEXT REFERENCES decisions(key),
 authority_refs TEXT NOT NULL CHECK(json_valid(authority_refs)),occurred_at TEXT,created_at TEXT NOT NULL,
 updated_at TEXT NOT NULL,revision INTEGER NOT NULL CHECK(revision>0),
 evidence_state TEXT NOT NULL CHECK(json_valid(evidence_state)),
 CHECK(locked=0 OR status='closed'),
 CHECK((status='open' AND work_tag IS NOT NULL) OR (status!='open' AND work_tag IS NULL)),
 CHECK(contested=0 OR (status='open' AND work_tag IN ('under-investigation','deferred')))) STRICT;
CREATE TABLE alternatives(id TEXT PRIMARY KEY,decision_key TEXT NOT NULL REFERENCES decisions(key),
 position INTEGER NOT NULL,title TEXT NOT NULL,description TEXT NOT NULL,benefit TEXT NOT NULL,cost TEXT NOT NULL,
 disposition TEXT NOT NULL CHECK(disposition IN ('unselected','selected','rejected','retired')),reason TEXT,
 revision INTEGER NOT NULL CHECK(revision>0)) STRICT;
CREATE TABLE "references"(id TEXT PRIMARY KEY,decision_key TEXT NOT NULL REFERENCES decisions(key),
 position INTEGER NOT NULL,label TEXT NOT NULL,locator TEXT NOT NULL,kind TEXT NOT NULL,
 version TEXT,sha256 TEXT,availability TEXT NOT NULL,authenticity TEXT NOT NULL,limitations TEXT NOT NULL,
 retired INTEGER NOT NULL CHECK(retired IN (0,1)),revision INTEGER NOT NULL CHECK(revision>0)) STRICT;
CREATE TABLE links(id TEXT PRIMARY KEY,source_key TEXT NOT NULL REFERENCES decisions(key),
 target_key TEXT NOT NULL REFERENCES decisions(key),type TEXT NOT NULL,active INTEGER NOT NULL CHECK(active IN(0,1)),
 reason TEXT NOT NULL,revision INTEGER NOT NULL CHECK(revision>0),impact TEXT,baseline_disposition TEXT,
 CHECK(source_key!=target_key)) STRICT;
CREATE UNIQUE INDEX active_links ON links(source_key,type,target_key) WHERE active=1;
CREATE INDEX decision_status ON decisions(status,updated_at,key);
CREATE INDEX outbound ON links(source_key,type,active);
CREATE INDEX inbound ON links(target_key,type,active);
CREATE TABLE transactions(ledger_revision INTEGER PRIMARY KEY,transaction_id TEXT NOT NULL UNIQUE,
 principal_id TEXT NOT NULL,request_id TEXT NOT NULL,request_hash TEXT NOT NULL,
 attribution TEXT NOT NULL CHECK(json_valid(attribution)),reason TEXT NOT NULL,
 authority_refs TEXT NOT NULL CHECK(json_valid(authority_refs)),recorded_at TEXT NOT NULL,occurred_at TEXT,
 result_json TEXT NOT NULL CHECK(json_valid(result_json)),request_json TEXT NOT NULL CHECK(json_valid(request_json)),UNIQUE(principal_id,request_id)) STRICT;
CREATE TABLE revisions(decision_key TEXT NOT NULL REFERENCES decisions(key),
 ledger_revision INTEGER NOT NULL REFERENCES transactions(ledger_revision),prior_decision_revision INTEGER NOT NULL,
 snapshot_json TEXT NOT NULL CHECK(json_valid(snapshot_json)),snapshot_sha256 TEXT NOT NULL,
 PRIMARY KEY(decision_key,ledger_revision)) STRICT;
CREATE TABLE artifacts(artifact_id TEXT PRIMARY KEY,kind TEXT NOT NULL,
 state TEXT NOT NULL CHECK(state IN ('pending','complete','failed')),revision INTEGER NOT NULL,
 relative_path TEXT NOT NULL,size INTEGER,sha256 TEXT,created_at TEXT NOT NULL,error_code TEXT) STRICT;
CREATE TABLE import_receipts(receipt_id TEXT PRIMARY KEY,source_hash TEXT NOT NULL,format_version TEXT NOT NULL,
 source_uuid TEXT NOT NULL,source_revision INTEGER NOT NULL,imported_at TEXT NOT NULL,
 validation_summary TEXT NOT NULL CHECK(json_valid(validation_summary))) STRICT;
CREATE TRIGGER immutable_transactions_update BEFORE UPDATE ON transactions BEGIN SELECT RAISE(ABORT,'Immutable history'); END;
CREATE TRIGGER immutable_transactions_delete BEFORE DELETE ON transactions BEGIN SELECT RAISE(ABORT,'Immutable history'); END;
CREATE TRIGGER immutable_revisions_update BEFORE UPDATE ON revisions BEGIN SELECT RAISE(ABORT,'Immutable history'); END;
CREATE TRIGGER immutable_revisions_delete BEFORE DELETE ON revisions BEGIN SELECT RAISE(ABORT,'Immutable history'); END;
"""
CATALOG_SQL = """
CREATE TABLE catalog_meta(id INTEGER PRIMARY KEY CHECK(id=1),schema_version INTEGER NOT NULL,
 catalog_revision INTEGER NOT NULL CHECK(catalog_revision>=0)) STRICT;
INSERT INTO catalog_meta VALUES(1,1,0);
CREATE TABLE projects(project_id TEXT PRIMARY KEY,name TEXT NOT NULL,ledger_uuid TEXT NOT NULL,
 db_path TEXT NOT NULL,enabled INTEGER NOT NULL CHECK(enabled IN(0,1)),row_revision INTEGER NOT NULL,
 created_at TEXT NOT NULL,updated_at TEXT NOT NULL) STRICT;
CREATE UNIQUE INDEX enabled_uuid ON projects(ledger_uuid) WHERE enabled=1;
CREATE UNIQUE INDEX enabled_path ON projects(db_path) WHERE enabled=1;
CREATE TABLE catalog_requests(principal_id TEXT NOT NULL,request_id TEXT NOT NULL,
 request_hash TEXT NOT NULL,response_json TEXT NOT NULL,catalog_revision INTEGER NOT NULL,
 PRIMARY KEY(principal_id,request_id)) STRICT;
"""

APPROVAL_SQL = """
CREATE TABLE approval_events(event_id TEXT PRIMARY KEY,decision_key TEXT NOT NULL REFERENCES decisions(key),
 ledger_revision INTEGER NOT NULL REFERENCES transactions(ledger_revision),operation_ordinal INTEGER NOT NULL CHECK(operation_ordinal>=0),
 supersedes_event_id TEXT REFERENCES approval_events(event_id),event_json TEXT NOT NULL CHECK(json_valid(event_json)),event_sha256 TEXT NOT NULL,
 UNIQUE(ledger_revision,operation_ordinal)) STRICT;
CREATE INDEX approval_history ON approval_events(decision_key,ledger_revision,event_id);
CREATE TABLE schema_upgrades(request_id TEXT PRIMARY KEY,principal_id TEXT NOT NULL,from_version INTEGER NOT NULL,to_version INTEGER NOT NULL,
 ledger_revision INTEGER NOT NULL,recorded_at TEXT NOT NULL,backup_artifact_id TEXT,request_hash TEXT NOT NULL,receipt_json TEXT NOT NULL CHECK(json_valid(receipt_json))) STRICT;
CREATE TRIGGER immutable_approval_update BEFORE UPDATE ON approval_events BEGIN SELECT RAISE(ABORT,'Immutable approval'); END;
CREATE TRIGGER immutable_approval_delete BEFORE DELETE ON approval_events BEGIN SELECT RAISE(ABORT,'Immutable approval'); END;
CREATE TRIGGER immutable_upgrade_update BEFORE UPDATE ON schema_upgrades BEGIN SELECT RAISE(ABORT,'Immutable upgrade'); END;
CREATE TRIGGER immutable_upgrade_delete BEFORE DELETE ON schema_upgrades BEGIN SELECT RAISE(ABORT,'Immutable upgrade'); END;
"""

APPLICATION_SQL = """
CREATE TABLE application_receipts(receipt_id TEXT PRIMARY KEY,decision_key TEXT NOT NULL REFERENCES decisions(key),
 ledger_revision INTEGER NOT NULL REFERENCES transactions(ledger_revision),operation_ordinal INTEGER NOT NULL,
 resolution_id TEXT NOT NULL,receipt_json TEXT NOT NULL CHECK(json_valid(receipt_json)),receipt_sha256 TEXT NOT NULL,
 UNIQUE(decision_key,resolution_id),UNIQUE(ledger_revision,operation_ordinal)) STRICT;
CREATE INDEX application_history ON application_receipts(decision_key,ledger_revision);
CREATE TABLE application_policy_events(policy_revision INTEGER PRIMARY KEY CHECK(policy_revision>0),
 request_id TEXT NOT NULL UNIQUE,request_hash TEXT NOT NULL,event_json TEXT NOT NULL CHECK(json_valid(event_json)),event_sha256 TEXT NOT NULL) STRICT;
CREATE TRIGGER immutable_application_update BEFORE UPDATE ON application_receipts BEGIN SELECT RAISE(ABORT,'Immutable application'); END;
CREATE TRIGGER immutable_application_delete BEFORE DELETE ON application_receipts BEGIN SELECT RAISE(ABORT,'Immutable application'); END;
CREATE TRIGGER immutable_policy_update BEFORE UPDATE ON application_policy_events BEGIN SELECT RAISE(ABORT,'Immutable policy'); END;
CREATE TRIGGER immutable_policy_delete BEFORE DELETE ON application_policy_events BEGIN SELECT RAISE(ABORT,'Immutable policy'); END;
"""

def initialize(path, uuid=None, schema_version=2):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb"):
        pass
    db = sqlite3.connect(path, isolation_level=None)
    try:
        db.execute("PRAGMA journal_mode=DELETE")
        db.execute("PRAGMA synchronous=FULL")
        db.execute("PRAGMA foreign_keys=ON")
        require(schema_version in (1,2,3),'UNSUPPORTED_SCHEMA','Unsupported ledger schema.',409)
        ledger_sql=LEDGER_SQL.replace('CHECK(schema_version=1)',f'CHECK(schema_version={schema_version})')
        db.executescript("BEGIN IMMEDIATE;\n" + (ledger_sql+(APPROVAL_SQL if schema_version>=2 else '')+(APPLICATION_SQL if schema_version==3 else '') if uuid else CATALOG_SQL))
        if uuid:
            db.execute("INSERT INTO meta VALUES(1,?,?,0,?)", (uuid,schema_version,now()))
            if schema_version>=2:
                receipt={'initialized':True,'ledger_uuid':str(uuid),'schema_version':schema_version,'revision':0}
                db.execute('INSERT INTO schema_upgrades VALUES(?,?,?,?,?,?,?,?,?)',
                           ('initialize','system',0,schema_version,0,now(),None,digest(receipt),encode(receipt)))
        db.commit()
    finally:
        db.close()

def metadata(db, uuid=None):
    row = db.execute("SELECT * FROM meta WHERE id=1").fetchone()
    require(row is not None and row["schema_version"] in (1,2,3), "UNSUPPORTED_SCHEMA", "Unsupported ledger schema.", 409)
    if row['schema_version']>=2:
        receipts=db.execute('SELECT * FROM schema_upgrades ORDER BY to_version').fetchall()
        chain=[(r['from_version'],r['to_version']) for r in receipts]
        valid=chain in ([(0,2)],[(1,2)]) if row['schema_version']==2 else chain in ([(0,3)],[(0,2),(2,3)],[(1,2),(2,3)])
        require(valid and all(0<=r['ledger_revision']<=row['ledger_revision'] for r in receipts),
                'INTEGRITY_FAILED','Schema receipt chain is missing or invalid.',409)
    if uuid is not None:
        require(row["ledger_uuid"] == str(uuid), "LEDGER_IDENTITY_MISMATCH", "Ledger identity does not match.", 409)
    return dict(row)

MODELS = {"decisions": Decision, "alternatives": Option, "references": Reference, "links": Link}
JSON_FIELDS = {"authority_refs", "evidence_state", "attribution", "result_json", "snapshot_json", "validation_summary", "request_json", "event_json", "receipt_json"}

def unpack(row):
    obj = dict(row)
    for key in JSON_FIELDS & obj.keys():
        obj[key] = json.loads(obj[key])
    for key in ("locked", "contested", "retired", "active", "enabled"):
        if key in obj:
            obj[key] = bool(obj[key])
    return obj

def save(db, table, obj):
    obj = MODELS[table].model_validate(obj).model_dump(mode="json")
    columns = list(obj)
    values = [encode(v) if k in JSON_FIELDS else int(v) if isinstance(v, bool) else v for k,v in obj.items()]
    key = "key" if table == "decisions" else "id"
    cols = ",".join('"' + c + '"' for c in columns)
    updates = ",".join('"' + c + '"=excluded."' + c + '"' for c in columns if c != key)
    db.execute(f'INSERT INTO "{table}" ({cols}) VALUES({",".join("?" for _ in columns)}) ON CONFLICT("{key}") DO UPDATE SET {updates}', values)
    return obj

def get(db, table, key):
    column = "key" if table == "decisions" else "id"
    row = db.execute(f'SELECT * FROM "{table}" WHERE "{column}"=?', (key,)).fetchone()
    if row is None:
        missing()
    return unpack(row)

def snapshot(db, key):
    decision = get(db, "decisions", key)
    for table in ("alternatives", "references"):
        decision[table] = [unpack(x) for x in db.execute(f'SELECT * FROM "{table}" WHERE decision_key=? ORDER BY position,id', (key,))]
    decision["links"] = [unpack(x) for x in db.execute("SELECT * FROM links WHERE source_key=? OR target_key=? ORDER BY id", (key,key))]
    return decision

def integrity(db):
    require(db.execute("PRAGMA integrity_check").fetchone()[0] == "ok" and not db.execute("PRAGMA foreign_key_check").fetchall(),
            "INTEGRITY_FAILED", "Database integrity verification failed.", 409)
