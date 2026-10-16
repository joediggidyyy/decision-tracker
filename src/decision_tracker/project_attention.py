"""Read-only lifecycle evidence for browser-local project acknowledgement."""
import json
from .errors import require
from .legacy import initial


def attention(db, revision):
    latest = None
    opened = list(db.execute("SELECT key,revision FROM decisions WHERE status='open' ORDER BY key"))
    # Only current open records contribute. An old closed unseen interval must
    # disappear even when other, acknowledged records remain open.
    for decision in opened:
        key = decision['key']
        seed = initial(db, key)
        previous = seed['status'] if seed else None
        prior = seed['revision'] if seed else 0
        start = 0 if previous == 'open' else None
        for row in db.execute('SELECT ledger_revision,prior_decision_revision,snapshot_json FROM revisions WHERE decision_key=? ORDER BY ledger_revision', (key,)):
            snap = json.loads(row['snapshot_json'])
            require(row['ledger_revision'] <= revision and row['prior_decision_revision'] == prior
                    and snap.get('key') == key and snap.get('revision') == prior + 1
                    and snap.get('status') in ('open', 'closed', 'deprecated'),
                    'INTEGRITY_FAILED', 'Decision attention history is incomplete.', 409)
            status = snap['status']
            if status == 'open' and previous != 'open':
                start = row['ledger_revision']
            if status != 'open':
                start = None
            previous, prior = status, snap['revision']
        require(previous == 'open' and prior == decision['revision'] and start is not None,
                'INTEGRITY_FAILED', 'Decision attention history is incomplete.', 409)
        latest = start if latest is None else max(latest, start)
    return {'version': 1, 'open_count': len(opened), 'latest_open_revision': latest}
