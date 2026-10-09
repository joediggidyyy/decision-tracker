import json
from pathlib import Path
import pytest
from decision_tracker import installed
from decision_tracker.credentials import Credentials
from decision_tracker.errors import Fault


@pytest.mark.parametrize('choice,expected', [(2, []), (1, ['issue', 'copy', 'open'])])
def test_first_setup_requires_explicit_copy(tmp_path, monkeypatch, choice, expected):
    calls = []
    monkeypatch.setattr(installed, 'deployment_for', lambda root: tmp_path / 'deployment.json')
    monkeypatch.setattr(installed, 'load', lambda path: ({}, type('Cfg', (), {'auth_store': tmp_path / 'auth.sqlite'})()))
    monkeypatch.setattr(Credentials, 'state', lambda self: {'state': 'uninitialized'})
    monkeypatch.setattr(Credentials, '__init__', lambda *a, **kw: None)
    monkeypatch.setattr(installed, 'message', lambda *a: choice)
    def issue(*a):
        calls.append('issue')
        return {'code': 'synthetic-test-code'}
    monkeypatch.setattr(installed, 'local_admin', issue)
    monkeypatch.setattr(installed, 'copy_code', lambda code: calls.append('copy') if code == 'synthetic-test-code' else None)
    monkeypatch.setattr(installed, 'open_app', lambda path: calls.append('open') or {'opened': True})
    result = installed.first_launch(tmp_path)
    assert calls == expected
    assert 'synthetic-test-code' not in json.dumps(result)


def test_bundle_rejects_escape_and_changed_files(tmp_path):
    manifest = {'format': 'decision-tracker.windows-bundle/v1', 'version': installed.__version__,
                'files': {f'../file{i}': 'bad' for i in range(21)}}
    (tmp_path / 'release-manifest.json').write_text(json.dumps(manifest))
    with pytest.raises(Fault, match='invalid path'):
        installed.validate_bundle(tmp_path)
    manifest['files'] = {f'file{i}': 'bad' for i in range(21)}
    (tmp_path / 'release-manifest.json').write_text(json.dumps(manifest))
    with pytest.raises(Fault, match='missing or changed'):
        installed.validate_bundle(tmp_path)


def test_busy_stop_never_becomes_forced_stop(tmp_path, monkeypatch):
    from decision_tracker import windows_local
    def busy(*a, **kw):
        raise Fault('SERVICE_BUSY', 'Unsaved drafts remain.')
    monkeypatch.setattr(windows_local, 'admin_request', busy)
    with pytest.raises(Fault, match='Unsaved drafts'):
        installed.stopped({'deployment_id': 'synthetic'}, type('Cfg', (), {'root': tmp_path})(), seconds=0)


@pytest.mark.parametrize('interrupted', [False, True])
def test_failed_upgrade_keeps_identity_and_can_repair(tmp_path, monkeypatch, interrupted):
    root = tmp_path / 'app'
    old = root / 'versions/0.1.0a0/runtime'
    old.mkdir(parents=True)
    path = tmp_path / 'deployment/deployment.json'
    from decision_tracker.deployment import initialize, atomic_json
    initialize(path, python=old / 'python.exe', source_root=old / 'site-packages')
    prior = json.loads(path.read_text())
    original_receipt = {'format': installed.APP_ID, 'owner_sid': installed.owner_sid(),
                        'root': str(root), 'version': '0.1.0a0', 'deployment': str(path)}
    atomic_json(root / 'installation.json', original_receipt)
    monkeypatch.setattr(installed, 'validate_bundle', lambda bundle: {})
    monkeypatch.setattr(installed, 'stopped', lambda *args: None)
    original_write = installed.atomic_json
    class Interrupted(BaseException):
        pass
    def failing_write(target, value):
        if target == root / 'installation.json':
            raise Interrupted() if interrupted else OSError('Synthetic write failure')
        original_write(target, value)
    monkeypatch.setattr(installed, 'atomic_json', failing_write)
    with pytest.raises(Interrupted if interrupted else OSError):
        installed.activate(root, path)
    if not interrupted:
        assert json.loads(path.read_text()) == prior
    monkeypatch.setattr(installed, 'atomic_json', original_write)
    installed.activate(root, path)
    current = json.loads(path.read_text())
    assert current['deployment_id'] == prior['deployment_id']
    assert current['config'] == prior['config'] and current['bundle'] == prior['bundle']
    assert current['python'].endswith('0.1.0a1\\runtime\\python.exe')
    assert not (root / 'activation-pending.json').exists()


def test_foreign_binding_is_preserved(tmp_path, monkeypatch):
    root = tmp_path / 'app'
    root.mkdir()
    path = tmp_path / 'deployment/deployment.json'
    from decision_tracker.deployment import initialize
    initialize(path)
    original = path.read_bytes()
    monkeypatch.setattr(installed, 'validate_bundle', lambda bundle: {})
    with pytest.raises(Fault, match='manual installation'):
        installed.activate(root, path)
    assert path.read_bytes() == original


def test_invalid_interruption_receipt_does_not_change_files(tmp_path):
    root = tmp_path / 'app'
    root.mkdir()
    path = tmp_path / 'deployment.json'
    path.write_text('{"unchanged":true}')
    journal = {'format':installed.APP_ID, 'owner_sid':installed.owner_sid(),
               'root':str(root), 'deployment':str(path), 'before':{}, 'after':{},
               'receipt_after':{'root':'unrelated'}}
    (root / 'activation-pending.json').write_text(json.dumps(journal))
    original = path.read_bytes()
    with pytest.raises(Fault, match='receipt is invalid'):
        installed.recover_activation(root, path)
    assert path.read_bytes() == original and (root / 'activation-pending.json').exists()
