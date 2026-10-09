"""Saved drafting content. Tags end at staging; publication uses ordinary Change."""
from contextlib import closing
import json
from pathlib import Path
import sqlite3
import threading
from typing import Literal
from uuid import UUID, uuid4, uuid5

from pydantic import Field, model_validator
from .models import Model, now
from .errors import Fault, require
from . import store
from .approvals import Approval
from .models import Change


class SavedOption(Model):
    title: str = Field(min_length=1, max_length=160)
    description: str = Field(default='', max_length=8192)
    benefit: str = Field(default='', max_length=8192)
    cost: str = Field(default='', max_length=8192)


class SavedReference(Model):
    label: str = Field(min_length=1, max_length=160)
    locator: str = Field(min_length=1, max_length=8192)
    kind: Literal['evidence', 'authority', 'external-decision'] = 'evidence'
    version: str | None = Field(default=None, max_length=160)
    sha256: str | None = Field(default=None, pattern=r'^[0-9a-f]{64}$')
    limitations: str = Field(default='', max_length=8192)


class SavedContent(Model):
    title: str = Field(min_length=1, max_length=160)
    question: str = Field(min_length=1, max_length=8192)
    answer: str | None = Field(default=None, max_length=32768)
    rationale: str | None = Field(default=None, max_length=32768)
    owner_role: str | None = Field(default=None, max_length=160)
    options: list[SavedOption] = Field(default_factory=list, max_length=24)
    references: list[SavedReference] = Field(default_factory=list, max_length=24)

    @model_validator(mode='after')
    def bounded(self):
        require(bool(self.title.strip() and self.question.strip()), 'VALIDATION_ERROR', 'Title and question cannot be blank.')
        require(1 + len(self.options) + len(self.references) <= 25, 'LIMIT_EXCEEDED', 'One saved decision must fit the existing 25-operation creation batch.')
        require(len(store.encode(self.model_dump()).encode()) <= 58000, 'LIMIT_EXCEEDED', 'Saved content is too large for a single record response.', 413)
        return self


class SavedRecord(Model):
    id: UUID
    content: SavedContent
    group_ids: list[UUID] = Field(default_factory=list, max_length=500)

    @model_validator(mode='after')
    def bounded(self):
        require(len(store.encode(self.model_dump(mode='json')).encode()) <= 60000, 'LIMIT_EXCEEDED', 'Saved record and tags exceed the single-record response budget.', 413)
        return self


class SavedGroup(Model):
    id: UUID
    name: str = Field(min_length=1, max_length=160)

    @model_validator(mode='after')
    def named(self):
        require(bool(self.name.strip()), 'VALIDATION_ERROR', 'Group name cannot be blank.')
        return self


class Bundle(Model):
    format: Literal['decision-tracker.saved-decisions/v1'] = 'decision-tracker.saved-decisions/v1'
    decisions: list[SavedRecord] = Field(default_factory=list, max_length=5000)
    groups: list[SavedGroup] = Field(default_factory=list, max_length=500)

    @model_validator(mode='after')
    def relationships(self):
        ids = [str(x.id) for x in self.decisions]
        groups = [str(x.id) for x in self.groups]
        require(len(ids) == len(set(ids)) and len(groups) == len(set(groups)), 'VALIDATION_ERROR', 'Bundle IDs must be unique.')
        require(all(str(g) in groups for x in self.decisions for g in x.group_ids), 'VALIDATION_ERROR', 'A group tag refers to a missing group.')
        require(all(len(x.group_ids) == len(set(x.group_ids)) for x in self.decisions), 'VALIDATION_ERROR', 'Group tags must be unique.')
        require(len(store.encode(self.model_dump(mode='json')).encode()) <= 10 * 1024 * 1024, 'LIMIT_EXCEEDED', 'Saved content bundle exceeds 10MiB.', 413)
        return self


class SavedChange(Model):
    expected_revision: int = Field(ge=0)
    request_id: UUID
    reason: str = Field(min_length=1, max_length=8192)
    action: Literal['save', 'delete', 'group-save', 'group-delete', 'import']
    id: UUID | None = None
    content: SavedContent | None = None
    group_ids: list[UUID] | None = Field(default=None, max_length=500)
    name: str | None = Field(default=None, min_length=1, max_length=160)
    bundle: Bundle | None = None


class Selection(Model):
    expected_revision: int = Field(ge=0)
    decision_ids: list[UUID] = Field(default_factory=list, max_length=5000)
    group_ids: list[UUID] = Field(default_factory=list, max_length=500)


class Staged(Model):
    decisions: list[SavedContent] = Field(min_length=1, max_length=500)
    project_id: str | None = None
    ledger_uuid: UUID | None = None
    new_project: bool = False
    expected_revision: int | None = Field(default=None, ge=0)
    publication_id: UUID = Field(default_factory=uuid4)
    phase: Literal['create', 'close', 'protect'] = 'create'
    targets: dict[str, int] = Field(default_factory=dict)
    approval: Approval | None = None
    reason: str = Field(default='Publish operator-selected saved decisions.', min_length=1, max_length=8192)

    @model_validator(mode='after')
    def bounded(self):
        require(len(store.encode(self.model_dump(mode='json')).encode()) <= 10 * 1024 * 1024, 'LIMIT_EXCEEDED', 'Staged content exceeds 10MiB.', 413)
        return self


def batches(staged):
    """Each complete decision travels together; aliases are local to one Change."""
    result, batch = [], []
    for ordinal, content in enumerate(staged.decisions):
        fields = content.model_dump(mode='json', exclude={'options', 'references'})
        alias = f'saved-{ordinal}'
        ops = [{'op': 'decision.create', 'client_ref': alias, 'data': fields}]
        ops += [{'op': 'option.add', 'key': '@' + alias, 'data': x.model_dump(mode='json')} for x in content.options]
        ops += [{'op': 'reference.add', 'key': '@' + alias, 'data': x.model_dump(mode='json')} for x in content.references]
        if len(batch) + len(ops) > 25:
            result.append(batch)
            batch = []
        batch.extend(ops)
    if batch:
        result.append(batch)
    return result


def prepare_publication(service, principal, data):
    """Prepare existing transitions; never write a project or invent approval."""
    for capability in ('read', 'write', 'decide'):
        principal.need(capability)
    require(data.approval is not None, 'APPROVAL_SOURCE_REQUIRED', 'Supply approval for the staged answers and destination.')
    if data.approval.mode == 'authenticated_now':
        require(principal.auth_method == 'human_password_session', 'FORBIDDEN', 'Only a signed-in person can approve now.', 403)
    for content in data.decisions:
        require(bool((content.answer or '').strip() and (content.rationale or '').strip()), 'VALIDATION_ERROR',
                f'Add an answer and rationale to "{content.title}" before publishing.')
    result = {'format': 'decision-tracker.saved-publication/v2', 'publication_id': str(data.publication_id),
              'baseline': 'publication-' + str(data.publication_id), 'phase': data.phase,
              'approval': data.approval.model_dump(mode='json', exclude_none=True, exclude_unset=True), 'batches': batches(data), 'requests': []}
    if data.new_project:
        require(data.phase == 'create' and not data.project_id and not data.targets, 'VALIDATION_ERROR', 'Choose one publication destination.')
        principal.need('registry')
        return {'ok': True, 'data': result}
    require(data.project_id and data.ledger_uuid, 'VALIDATION_ERROR', 'Choose a project and its ledger UUID.')
    with service.catalog.project(data.project_id, str(data.ledger_uuid), principal, True) as (db, project):
        meta = store.metadata(db, data.ledger_uuid)
        require(meta['schema_version'] >= 2, 'UPGRADE_REQUIRED', 'This project needs an authorized data-format upgrade.', 409)
        if data.expected_revision is not None:
            require(meta['ledger_revision'] == data.expected_revision, 'STALE_REVISION', 'The project changed; review before preparing publication.', 409)
        revision = meta['ledger_revision']
        if data.phase == 'create':
            require(not data.targets, 'VALIDATION_ERROR', 'Creation does not accept existing decision targets.')
            count = db.execute('SELECT count(*) FROM decisions').fetchone()[0]
            require(count + len(data.decisions) <= 500, 'LIMIT_EXCEEDED', 'The selected set exceeds project capacity.', 413)
            operations = result['batches']
        else:
            require(len(data.targets) == len(data.decisions), 'VALIDATION_ERROR', 'Retain one target for each staged decision.')
            operations = []
            ops = []
            for (key, expected), content in zip(data.targets.items(), data.decisions):
                obj = store.get(db, 'decisions', key)
                require(obj['revision'] == expected, 'STALE_REVISION', 'An injected decision changed; review its current state.', 409, key=key)
                if data.phase == 'close':
                    require(obj['status'] == 'open' and not obj['locked'], 'INVALID_TRANSITION', 'Close only the retained open decision.')
                    ops.append({'op': 'decision.close', 'key': key, 'data': {'answer': content.answer, 'rationale': content.rationale, 'approval': result['approval']}})
                else:
                    require(obj['status'] == 'closed' and not obj['locked'], 'INVALID_TRANSITION', 'Protect only the retained closed decision.')
                    ops.append({'op': 'decision.lock', 'key': key, 'data': {'baseline': result['baseline']}})
                if len(ops) == 25:
                    operations.append(ops); ops = []
            if ops: operations.append(ops)
        for index, ops in enumerate(operations):
            expected = {op['key']: data.targets[op['key']] for op in ops if op.get('key') and not op['key'].startswith('@')}
            refs = []
            if data.phase == 'protect':
                for key in expected:
                    obj = store.get(db, 'decisions', key)
                    refs.extend(obj['authority_refs'])
                # Closure records have a server-owned approval reference per decision.
                refs = [ref for ref in dict.fromkeys(refs) if ref.startswith('dt-approval:')]
                require(bool(refs), 'APPROVAL_SOURCE_REQUIRED', 'Read the committed approval before protecting.')
            request = Change(expected_ledger_uuid=data.ledger_uuid, expected_revision=revision + index,
                             expected_decision_revisions=expected, request_id=uuid5(data.publication_id, data.phase + ':' + str(index)),
                             reason=data.reason, authority_refs=refs, operations=ops)
            result['requests'].append(request.model_dump(mode='json'))
    result['project_id'] = data.project_id
    result['ledger_uuid'] = str(data.ledger_uuid)
    return {'ok': True, 'data': result}


class SavedDecisions:
    def __init__(self, root):
        self.path = Path(root) / 'saved-decisions.sqlite'
        self.lock = threading.RLock()
        self.failure = None
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            if self.path.exists():
                # Existing state must be recognized; never initialize over damaged data.
                with store.connect(self.path) as db:
                    tables={r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
                    require({'saved_meta','saved_decisions','saved_groups','saved_history'} <= tables, 'INTEGRITY_FAILED', 'Saved storage schema is incomplete.', 503)
                    require(self.revision(db) >= 0, 'INTEGRITY_FAILED', 'Saved revision is invalid.', 503)
                    store.integrity(db)
            else:
                with self.path.open('xb'):
                    pass
                with closing(sqlite3.connect(self.path)) as db:
                    db.executescript('''
                CREATE TABLE IF NOT EXISTS saved_meta(id INTEGER PRIMARY KEY CHECK(id=1),revision INTEGER NOT NULL);
                INSERT OR IGNORE INTO saved_meta VALUES(1,0);
                CREATE TABLE IF NOT EXISTS saved_decisions(id TEXT PRIMARY KEY,value TEXT NOT NULL CHECK(json_valid(value)));
                CREATE TABLE IF NOT EXISTS saved_groups(id TEXT PRIMARY KEY,value TEXT NOT NULL CHECK(json_valid(value)));
                CREATE TABLE IF NOT EXISTS saved_history(revision INTEGER PRIMARY KEY,actor TEXT NOT NULL,recorded_at TEXT NOT NULL,request_id TEXT NOT NULL,request_hash TEXT NOT NULL,request_json TEXT NOT NULL,result_json TEXT NOT NULL,UNIQUE(actor,request_id));
                CREATE TRIGGER IF NOT EXISTS saved_history_no_update BEFORE UPDATE ON saved_history BEGIN SELECT RAISE(ABORT,'Immutable history'); END;
                CREATE TRIGGER IF NOT EXISTS saved_history_no_delete BEFORE DELETE ON saved_history BEGIN SELECT RAISE(ABORT,'Immutable history'); END;
                    ''')
        except (sqlite3.Error, Fault, OSError, TypeError, IndexError):
            self.failure = Fault('DATABASE_UNAVAILABLE', 'Saved decisions are unavailable. Project work remains available.', 503,
                recovery='Preserve saved-decisions.sqlite. Stop the service, restore a checked saved-decision backup, then restart and verify the saved list. Do not replace project ledgers.')

    def available(self):
        if self.failure:
            raise self.failure

    def bundle(self, db):
        return Bundle(decisions=[json.loads(r[0]) for r in db.execute('SELECT value FROM saved_decisions ORDER BY id')],
                      groups=[json.loads(r[0]) for r in db.execute('SELECT value FROM saved_groups ORDER BY id')])

    def revision(self, db):
        return db.execute('SELECT revision FROM saved_meta WHERE id=1').fetchone()[0]

    def listing(self, principal, offset=0, limit=50, expected_revision=None):
        principal.need('read')
        self.available()
        with store.connect(self.path) as db:
            revision = self.revision(db)
            require(expected_revision is None or revision == expected_revision, 'REVISION_CONFLICT', 'Saved decisions changed; reload the list.', 409)
            records = db.execute('SELECT value FROM saved_decisions ORDER BY id LIMIT ? OFFSET ?', (limit, offset)).fetchall()
            groups = [json.loads(r[0]) for r in db.execute('SELECT value FROM saved_groups ORDER BY id LIMIT ? OFFSET ?', (limit, offset))]
            total = max(db.execute('SELECT count(*) FROM saved_decisions').fetchone()[0], db.execute('SELECT count(*) FROM saved_groups').fetchone()[0])
            # Summaries stay small even when saved content is large.
            rows = [json.loads(r[0]) for r in records]
            summaries = [{'id': x['id'], 'title': x['content']['title'], 'group_ids': x['group_ids']} for x in rows]
            size = limit
            while True:
                result = {'ok': True, 'revision': revision, 'data': summaries[:size], 'groups': groups[:size],
                          'next_offset': offset + size if offset + size < total else None}
                if len(store.encode(result).encode()) <= 60000:
                    return result
                require(size > 1, 'LIMIT_EXCEEDED', 'Saved summary exceeds response capacity.', 413)
                size -= 1

    def get(self, principal, id):
        principal.need('read')
        self.available()
        with store.connect(self.path) as db:
            row = db.execute('SELECT value FROM saved_decisions WHERE id=?', (str(id),)).fetchone()
            require(row is not None, 'NOT_FOUND', 'Saved decision is unavailable.', 404)
            return {'ok': True, 'revision': self.revision(db), 'data': json.loads(row[0])}

    def change(self, principal, request):
        principal.need('write')
        self.available()
        value = request.model_dump(mode='json')
        fingerprint = store.digest({k: v for k, v in value.items() if k != 'request_id'})
        with self.lock, store.connect(self.path, True) as db:
            prior = db.execute('SELECT request_hash,result_json FROM saved_history WHERE actor=? AND request_id=?', (principal.id, str(request.request_id))).fetchone()
            if prior:
                require(prior[0] == fingerprint, 'REQUEST_ID_REUSED', 'Request ID has different content.', 409)
                return json.loads(prior[1])
            revision = self.revision(db)
            require(revision == request.expected_revision, 'REVISION_CONFLICT', 'Saved decisions changed; reload before saving.', 409)
            bundle = self.bundle(db)
            decisions = {str(x.id): x for x in bundle.decisions}
            groups = {str(x.id): x for x in bundle.groups}
            id = str(request.id or uuid4())
            if request.action == 'save':
                current = decisions.get(id)
                require(request.content is not None or current is not None, 'VALIDATION_ERROR', 'Supply saved content.')
                decisions[id] = SavedRecord(id=id, content=request.content or current.content,
                    group_ids=request.group_ids if request.group_ids is not None else current.group_ids if current else [])
            elif request.action == 'delete':
                require(id in decisions, 'NOT_FOUND', 'Saved decision is unavailable.', 404)
                del decisions[id]
            elif request.action == 'group-save':
                require(request.name is not None, 'VALIDATION_ERROR', 'Supply group name.')
                groups[id] = SavedGroup(id=id, name=request.name)
            elif request.action == 'group-delete':
                require(id in groups, 'NOT_FOUND', 'Group is unavailable.', 404)
                del groups[id]
                decisions = {k: SavedRecord(id=x.id, content=x.content, group_ids=[g for g in x.group_ids if str(g) != id]) for k, x in decisions.items()}
            else:
                require(request.bundle is not None, 'VALIDATION_ERROR', 'Supply a portable bundle.')
                for target, incoming in ((groups, request.bundle.groups), (decisions, request.bundle.decisions)):
                    for item in incoming:
                        key = str(item.id)
                        require(key not in target or target[key] == item, 'REVISION_CONFLICT', 'Imported ID has different content. Existing saved content was retained.', 409, id=key)
                        target[key] = item
            updated = Bundle(decisions=list(decisions.values()), groups=list(groups.values()))
            for table, rows in (('saved_decisions', updated.decisions), ('saved_groups', updated.groups)):
                db.execute('DELETE FROM ' + table)
                db.executemany('INSERT INTO ' + table + ' VALUES(?,?)', [(str(x.id), store.encode(x.model_dump(mode='json'))) for x in rows])
            result = {'ok': True, 'revision': revision + 1, 'data': {'id': id if request.action != 'import' else None, 'action': request.action}}
            db.execute('UPDATE saved_meta SET revision=? WHERE id=1', (revision + 1,))
            db.execute('INSERT INTO saved_history VALUES(?,?,?,?,?,?,?)', (revision + 1, principal.id, now(), str(request.request_id), fingerprint, store.encode(value), store.encode(result)))
            return result

    def select(self, principal, selection):
        principal.need('read')
        self.available()
        with store.connect(self.path) as db:
            require(self.revision(db) == selection.expected_revision, 'REVISION_CONFLICT', 'Saved decisions changed; reload before adding to staging.', 409)
            bundle = self.bundle(db)
            chosen, tags = set(selection.decision_ids), set(selection.group_ids)
            require(chosen <= {x.id for x in bundle.decisions} and tags <= {x.id for x in bundle.groups}, 'NOT_FOUND', 'A selected saved item is unavailable.', 404)
            return {'ok': True, 'revision': self.revision(db), 'data': [{'id': str(x.id), 'content': x.content.model_dump(mode='json')} for x in bundle.decisions if x.id in chosen or tags.intersection(x.group_ids)]}


def mount(app):
    from fastapi import Request, Query
    from fastapi.responses import Response, FileResponse
    from .config import contained
    saved = SavedDecisions(app.state.service.root)
    app.state.saved_decisions = saved
    principal, output = app.state.principal, app.state.output

    @app.get('/api/v1/saved-decisions')
    def listing(request: Request, offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=50), expected_revision: int | None = Query(None, ge=0)):
        return output(request, saved.listing(principal(request), offset, limit, expected_revision))

    @app.get('/api/v1/saved-decisions/{id}')
    def get(id: UUID, request: Request):
        return output(request, saved.get(principal(request), id))

    @app.post('/api/v1/saved-decisions/changes')
    def change(request: Request, data: SavedChange):
        return output(request, saved.change(principal(request), data))

    @app.post('/api/v1/saved-decisions/stage')
    def select(request: Request, data: Selection):
        # Large selections are a bounded download, rather than the ordinary 64KiB response.
        p = principal(request)
        value = saved.select(p, data)
        require(len(value['data']) <= 500, 'LIMIT_EXCEEDED', 'Stage at most 500 decisions at a time.')
        return Response(store.encode(value), media_type='application/json')

    @app.post('/api/v1/saved-decisions/prepare')
    def prepare(request: Request, data: Staged):
        return Response(store.encode(prepare_publication(app.state.service, principal(request), data)), media_type='application/json')

    @app.post('/api/v1/saved-decisions/export')
    def export(request: Request):
        principal(request).need('read')
        saved.available()
        with store.connect(saved.path) as db:
            value = saved.bundle(db).model_dump(mode='json')
        return Response(store.encode(value), media_type='application/json', headers={'Content-Disposition': 'attachment; filename="saved-decisions.json"'})

    @app.post('/api/v1/saved-decisions/import-check')
    def check(request: Request, data: Bundle):
        principal(request).need('read')
        return output(request, {'ok': True, 'data': {'decisions': len(data.decisions), 'groups': len(data.groups), 'validated_only': True}})

    class BackupCheck(Model):
        artifact_id: UUID

    def backup_path(id):
        return contained(saved.path.parent, f'saved-backups/{id}.sqlite')

    def verify_backup(path):
        with store.connect(path) as db:
            store.integrity(db)
            bundle = saved.bundle(db)
            revision = saved.revision(db)
            rows = db.execute('SELECT * FROM saved_history ORDER BY revision').fetchall()
            require([r['revision'] for r in rows] == list(range(1, revision + 1)), 'INTEGRITY_FAILED', 'Saved history is incomplete.', 409)
            for row in rows:
                req = json.loads(row['request_json'])
                require(store.digest({k:v for k,v in req.items() if k != 'request_id'}) == row['request_hash'] and req['request_id'] == row['request_id'], 'INTEGRITY_FAILED', 'Saved history request failed verification.', 409)
                require(json.loads(row['result_json'])['revision'] == row['revision'], 'INTEGRITY_FAILED', 'Saved history receipt failed verification.', 409)
            return {'revision': revision, 'decisions': len(bundle.decisions), 'groups': len(bundle.groups), 'history_entries': len(rows)}

    @app.post('/api/v1/saved-decisions/backup')
    def backup(request: Request):
        principal(request).need('maintain')
        saved.available()
        id = uuid4()
        path = backup_path(id)
        path.parent.mkdir(parents=True, exist_ok=True)
        with saved.lock, store.connect(saved.path) as source, closing(sqlite3.connect(path)) as target:
            source.backup(target)
        return output(request, {'ok': True, 'data': {'artifact_id': str(id), **verify_backup(path)}})

    @app.post('/api/v1/saved-decisions/backup-check')
    def backup_check(request: Request, data: BackupCheck):
        principal(request).need('maintain')
        return output(request, {'ok': True, 'data': {'artifact_id': str(data.artifact_id), **verify_backup(backup_path(data.artifact_id)), 'live_data_changed': False}})

    @app.get('/api/v1/saved-decisions/backups/{id}/content')
    def download_backup(id: UUID, request: Request):
        principal(request).need('maintain')
        path = backup_path(id)
        require(path.is_file(), 'NOT_FOUND', 'Saved backup is unavailable.', 404)
        return FileResponse(path, media_type='application/octet-stream', filename='saved-decisions-backup.sqlite')
