"""Actual Setup qualification against disposable current-user installation/data."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import urllib.request
import winreg
import pytest

pytestmark = pytest.mark.skipif(os.environ.get('DECISION_TRACKER_PROOF_SCOPE') != 'dt-windows-installer',
                                reason='Compiled Setup runs only in its dedicated native lane.')


def test_compiled_setup_install_repair_uninstall_reinstall(tmp_path):
    root = Path(__file__).resolve().parents[1]
    # Never modify an existing production Setup registration.
    key = r'Software\Microsoft\Windows\CurrentVersion\Uninstall\{48F6D0E0-478C-435E-9E76-8AF59BB81944}_is1'
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key):
            raise AssertionError('Existing installer registration: use a separate test Windows account.')
    except FileNotFoundError:
        pass
    spec = importlib.util.spec_from_file_location('build_windows', root / 'tools/build_windows.py')
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)
    output = root / '.local/windows-package'
    build = builder.build(root, output, os.environ['DECISION_TRACKER_INSTALLER_RUNTIME'])
    setup = next(output.glob('*setup.exe'))
    app = tmp_path / 'Application é test'
    descriptor = tmp_path / 'deployment/deployment.json'
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', PYTHONIOENCODING='utf-8')
    env.pop('PYTHONPATH', None)
    for name in list(env):
        if name.startswith(('DT_', 'CALAMUM_')):
            env.pop(name)
    def run(args):
        result = subprocess.run([str(a) for a in args], cwd=tmp_path, env=env,
                                capture_output=True, text=True, encoding='utf-8', timeout=120)
        assert result.returncode == 0, result.stdout + result.stderr
        return result.stdout
    def install(label):
        run([setup, '/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART', '/SP-', '/NOICONS',
             '/DIR=' + str(app), '/DEPLOYMENT=' + str(descriptor), '/PORT=' + str(port),
             '/LOG=' + str(output / (label + '.log'))])
    install('install')
    python = app / 'versions/0.1.0a1/runtime/python.exe'
    def cli(*args):
        return json.loads(run([python, '-m', 'decision_tracker.cli', *args, '--deployment', descriptor, '--json']))
    assert 'data' in run([python, '-m', 'decision_tracker.cli', '--help'])
    runtime = json.loads(run([python, '-c', "import sys,json,importlib.util,sqlite3,ssl,decision_tracker; print(json.dumps({'version':sys.version,'app':decision_tracker.__version__,'path':decision_tracker.__file__,'pip':importlib.util.find_spec('pip') is not None,'pytest':importlib.util.find_spec('pytest') is not None,'calamum':importlib.util.find_spec('calamum') is not None}))"]))
    assert runtime['version'].startswith('3.14.8') and runtime['app'] == '0.1.0a1'
    assert Path(runtime['path']).is_relative_to(app)
    assert not runtime['pip'] and not runtime['pytest'] and not runtime['calamum']
    original = json.loads(descriptor.read_text())
    # Synthetic test credentials only. Setup codes never leave this process or enter logs.
    from decision_tracker.credentials import Credentials
    from decision_tracker.config import load_config
    cfg = load_config(original['config'])
    credentials = Credentials(Path(cfg.auth_store))
    code = credentials.issue('bootstrap')
    credentials.redeem('bootstrap', code, 'Synthetic installer password 987!', 'Synthetic installer password 987!')
    from decision_tracker.service import Service
    from decision_tracker.auth import Principal
    from decision_tracker.models import ProjectChange
    from uuid import uuid4
    service = Service(cfg.root)
    principal = Principal('operator', frozenset({'*'}), frozenset({'read','write','decide','maintain','registry','propose'}))
    project = service.catalog.mutate(principal, ProjectChange(project_id='setup-test', name='Setup test', expected_catalog_revision=0, request_id=uuid4()))
    project_uuid = project['data']['ledger_uuid']
    from decision_tracker.saved_decisions import SavedDecisions, SavedChange
    saved = SavedDecisions(cfg.root)
    assert saved.listing(principal)['data'] == [] and saved.listing(principal)['groups'] == []
    saved_id = saved.change(principal, SavedChange(expected_revision=0, request_id=uuid4(),
        reason='Synthetic installer fixture', action='save', content={'title':'Retained saved decision',
        'question':'Is Library retained?', 'answer':'Yes', 'rationale':'Keep user data.'}))['data']['id']
    def hashes():
        return {str(p.relative_to(tmp_path)): hashlib.sha256(p.read_bytes()).hexdigest()
                for base in [cfg.root, descriptor.parent] for p in base.rglob('*') if p.is_file()
                and p.suffix in ('.sqlite', '.db')}
    before = hashes()
    started = cli('service', 'ensure-running')['data']
    assert started['started']
    again = cli('service', 'ensure-running')['data']
    assert again['instance_id'] == started['instance_id'] and not again['started']
    with urllib.request.urlopen(started['base_url'], timeout=5) as response:
        assert b'id="login-form"' in response.read()
    # A real protected browser draft prevents owner-local installer shutdown.
    import httpx
    with httpx.Client(base_url=started['base_url']) as browser:
        csrf = browser.get('/api/v1/session/setup').json()['data']['csrf_token']
        browser.headers.update({'Origin':started['base_url'].rstrip('/'), 'X-CSRF-Token':csrf})
        login = browser.post('/api/v1/session', json={'password':'Synthetic installer password 987!'})
        assert login.status_code == 200
        browser.headers['X-CSRF-Token'] = login.json()['data']['csrf_token']
        lease = browser.post('/api/v1/service/draft-leases', json={'project_id':'setup-test',
            'expected_ledger_uuid':project_uuid, 'tab_nonce':str(uuid4())})
        assert lease.status_code == 201
        busy = subprocess.run([str(python), '-m', 'decision_tracker.installed', 'prepare',
            '--install-root', str(app)], cwd=tmp_path, env=env, capture_output=True,
            text=True, encoding='utf-8', timeout=15)
        assert busy.returncode == 1 and 'SERVICE_BUSY' in busy.stderr
        assert not (descriptor.parent / 'installation-maintenance.json').exists()
        assert cli('service', 'ensure-running')['data']['instance_id'] == started['instance_id']
        assert browser.delete('/api/v1/service/draft-leases/' + lease.json()['data']['lease_id']).status_code == 204
    # Setup itself performs owner-local stop, then repairs the same deployment.
    install('repair')
    assert json.loads(descriptor.read_text()) == original
    assert credentials.state()['state'] == 'active'
    assert service.catalog.listing(principal)['data'][0]['ledger_uuid'] == project_uuid
    assert saved.listing(principal)['data'][0]['id'] == saved_id
    # Repair replaces a damaged bundled support file without deleting user data.
    (app / 'versions/0.1.0a1/support/NOTICE').write_text('damaged synthetic file')
    install('repair-damaged-file')
    assert (app / 'versions/0.1.0a1/support/NOTICE').read_bytes() == (root / 'NOTICE').read_bytes()
    python.unlink()
    install('repair-missing-runtime')
    assert python.is_file() and credentials.state()['state'] == 'active'
    assert service.catalog.listing(principal)['data'][0]['ledger_uuid'] == project_uuid
    stable = hashes()
    uninstall = app / 'unins000.exe'
    run([uninstall, '/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART', '/LOG=' + str(output / 'uninstall.log')])
    assert not python.exists()
    assert hashes() == stable
    assert descriptor.exists() and (descriptor.parent / 'installation-maintenance.json').exists()
    install('reinstall')
    assert json.loads(descriptor.read_text()) == original
    assert credentials.state()['state'] == 'active'
    assert service.catalog.listing(principal)['data'][0]['ledger_uuid'] == project_uuid
    assert saved.listing(principal)['data'][0]['id'] == saved_id
    assert not (descriptor.parent / 'installation-maintenance.json').exists()
    run([uninstall, '/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART'])
    (output / 'qualification.json').write_text(json.dumps({'build':build,'runtime':runtime,
        'install':True,'repair':True,'missing_runtime_repaired':True,
        'uninstall_preserves_data':True,'reinstall':True,
        'managed_start_reuse_stop':True,'busy_draft_stop_refused':True,
        'project_uuid_preserved':True,'library_id_preserved':True,'spaces_and_unicode_path':True,
        'graphical_wizard':'silent execution; interactive owner acceptance pending'}, indent=2))
