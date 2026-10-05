"""Explicit preparation of contained imported ledgers for registration."""
import json
import os
import sqlite3
from uuid import UUID, uuid4
from . import store
from .config import contained
from .errors import Fault, require
from .models import now


def paths(catalog, candidate_id):
    try:
        key = str(UUID(str(candidate_id)))
    except (ValueError, TypeError):
        raise Fault("VALIDATION_ERROR", "Invalid candidate ID.") from None
    relative = f"candidates/{key}/ledger.sqlite"
    return key, relative, contained(catalog.root, relative), contained(catalog.root, f"candidates/{key}/prepared.json")


def inspect(catalog, candidate_id, allow_registered=False):
    from .artifacts import validate_history
    key, relative, path, receipt = paths(catalog, candidate_id)
    require(path.is_file(), "CANDIDATE_UNAVAILABLE", "Candidate is unavailable.", 409)
    with store.connect(path) as db:
        result = validate_history(db)
        meta = store.metadata(db)
    with store.connect(catalog.path) as db:
        require(allow_registered or db.execute("SELECT 1 FROM projects WHERE ledger_uuid=? OR lower(db_path)=lower(?)",
                           (meta['ledger_uuid'], relative)).fetchone() is None,
                "DUPLICATE_LEDGER", "This project is already registered. Enable it if disabled.", 409)
    return {"candidate_id": key, "ledger_uuid": meta['ledger_uuid'], "schema_version": meta['schema_version'],
            "ledger_revision": meta['ledger_revision'], "logical_digest": result['logical_sha256']}


def prepared(catalog, candidate_id, expected=None):
    _, _, _, receipt = paths(catalog, candidate_id)
    require(receipt.is_file() and receipt.stat().st_size <= 4096, "CANDIDATE_UNPREPARED", "Prepare this candidate before adding it.", 409)
    try:
        saved = json.loads(receipt.read_text(encoding='utf-8'))
    except (ValueError, OSError):
        raise Fault("CANDIDATE_UNPREPARED", "Candidate preparation record is unreadable.", 409) from None
    current = inspect(catalog, candidate_id)
    require(isinstance(saved, dict) and set(saved) == set(current) | {'prepared_at'}
            and isinstance(saved['prepared_at'], str) and all(saved.get(k) == v for k, v in current.items()),
            "CANDIDATE_CHANGED", "Candidate changed. Prepare it again before adding it.", 409)
    require(expected is None or current['logical_digest'] == expected,
            "CANDIDATE_CHANGED", "Candidate changed. Review the prepared project again.", 409)
    return saved


def prepare(catalog, principal, candidate_id, imported=False):
    principal.need('maintain')
    if not imported:
        principal.need('registry')
    with catalog.coordinator:
        current = inspect(catalog, candidate_id, allow_registered=imported)
        try:
            return {"ok": True, "data": prepared(catalog, candidate_id)}
        except Fault as error:
            if error.code not in ('CANDIDATE_UNPREPARED', 'CANDIDATE_CHANGED') and not (imported and error.code == 'DUPLICATE_LEDGER'):
                raise
        _, _, _, receipt = paths(catalog, candidate_id)
        current['prepared_at'] = now()
        temporary = contained(catalog.root, receipt.relative_to(catalog.root).as_posix() + '.' + str(uuid4()) + '.pending')
        with temporary.open('x', encoding='utf-8') as out:
            out.write(store.encode(current)); out.flush(); os.fsync(out.fileno())
        os.replace(temporary, receipt)
        return {"ok": True, "data": current}


def listing(service, principal, cursor=None, limit=50):
    principal.need('maintain'); principal.need('registry')
    catalog = service.catalog
    with catalog.coordinator:
        folder = contained(catalog.root, 'candidates')
        rows = []
        for child in folder.iterdir() if folder.exists() else []:
            try:
                rows.append(prepared(catalog, child.name))
            except (Fault, ValueError, OSError, sqlite3.DatabaseError):
                continue
        with store.connect(catalog.path) as db:
            revision = catalog.revision(db)
        rows.sort(key=lambda row: row['candidate_id'])
        data, next_cursor, complete = service.page([(r['candidate_id'], r) for r in rows],
            {'ledger_uuid': 'candidate-inventory', 'ledger_revision': revision},
            {'inventory': store.digest(rows)}, cursor, limit)
        return {'ok': True, 'catalog_revision': revision, 'data': data, 'next_cursor': next_cursor, 'complete': complete}
