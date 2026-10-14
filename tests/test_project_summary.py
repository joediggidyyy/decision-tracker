from uuid import uuid4
from datetime import datetime, timezone
import pytest
from conftest import change
from test_api import setup_project
from decision_tracker.auth import Principal
from decision_tracker.errors import Fault
from decision_tracker.models import ProjectState


def test_summary_snapshot_counts_beyond_pagination_and_latest_activity(ledger, monkeypatch):
    s, p, u = ledger
    empty = s.project_summary('alpha', u, p)
    assert empty['data'].pop('last_write_at').endswith('Z')
    assert empty['data'] == {'counts': {'open': 0, 'closed': 0, 'deprecated': 0}, 'latest_activity_at': None, 'latest_activity_key': None}
    monkeypatch.setattr('decision_tracker.service.now', lambda: '2026-10-13T20:00:00Z')
    for batch in range(3):
        change(s, p, u, [{'op': 'decision.create', 'data': {'title': str(i), 'question': 'Which approach?'}} for i in range(batch * 25, (batch + 1) * 25)], batch)
    change(s, p, u, [{'op': 'decision.close', 'key': 'D000002', 'data': {'answer': 'Chosen', 'rationale': 'Reviewed'}}], 3, {'D000002': 1}, authority_refs=['operator'])
    change(s, p, u, [{'op': 'decision.deprecate', 'key': 'D000001', 'data': {'kind': 'superseded', 'replacement_key': 'D000002'}}], 4, {'D000001': 1, 'D000002': 2}, authority_refs=['operator'])
    result = s.project_summary('alpha', u, p)
    assert result['data']['counts'] == {'open': 73, 'closed': 1, 'deprecated': 1}
    assert result['data']['latest_activity_key'] == 'D000001'
    assert result['data']['latest_activity_at'] == '2026-10-13T20:00:00Z'
    with s.catalog.project('alpha', u, p) as (_, project):
        modified = (s.root / project['db_path']).stat().st_mtime
    assert result['data']['last_write_at'] == datetime.fromtimestamp(modified, timezone.utc).isoformat().replace('+00:00', 'Z')
    assert result['data']['last_write_at'] != result['data']['latest_activity_at']
    assert result['revision'] == 5 and result['ledger_uuid'] == u and result['project_id'] == 'alpha'
    assert len(s.list_decisions('alpha', u, p)['data']) == 50
    assert s.project_summary('alpha', u, p) == result


def test_summary_shared_scope_identity_and_disabled_guards(ledger):
    s, p, u = ledger
    for restricted in [Principal('hidden', frozenset({'other'}), frozenset({'read'})), Principal('writer', frozenset({'alpha'}), frozenset({'write'}))]:
        with pytest.raises(Fault):
            s.project_summary('alpha', u, restricted)
    with pytest.raises(Fault):
        s.project_summary('alpha', str(uuid4()), p)
    s.catalog.mutate(p, ProjectState(enabled=False, expected_catalog_revision=1, request_id=uuid4()), 'alpha')
    with pytest.raises(Fault):
        s.project_summary('alpha', u, p)


def test_summary_api_readonly_identity_and_no_revision_change(client):
    u = setup_project(client)
    client.headers['Authorization'] = 'Bearer ' + client.readonly
    first = client.get('/api/v1/projects/alpha/summary')
    assert first.status_code == 200
    assert first.json()['data']['counts'] == {'open': 0, 'closed': 0, 'deprecated': 0}
    assert first.json()['revision'] == client.get('/api/v1/projects/alpha/decisions').json()['revision'] == 0
    assert client.get('/api/v1/projects/other/summary').status_code == 404
    client.headers['X-Ledger-UUID'] = str(uuid4())
    assert client.get('/api/v1/projects/alpha/summary').status_code == 409
    del client.headers['X-Ledger-UUID']
    assert client.get('/api/v1/projects/alpha/summary').status_code == 422
