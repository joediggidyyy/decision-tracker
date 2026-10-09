"""Owned Windows installation lifecycle; user data is never installer payload."""
import argparse
import ctypes
import hashlib
import json
import sys
import time
from pathlib import Path
from . import __version__
from .deployment import (atomic_json, coordinator, default_path, initialize, load,
                         local_admin, open_app, safe_path, install_protocol, uninstall_protocol)
from .errors import Fault, require
from .windows_local import owner_sid

APP_ID = 'decision-tracker.windows-installation/v1'


def read_json(path):
    require(path.is_file() and path.stat().st_size < 2_000_000,
            'INSTALLATION_DAMAGED', 'Installation information is missing. Run Setup again to repair it.')
    return json.loads(path.read_text(encoding='utf-8'))


def bundle_for(root, version=__version__):
    root = safe_path(root)
    require(version == __version__, 'INSTALLATION_DAMAGED', 'Use the matching installer version.')
    return root / 'versions' / version


def validate_bundle(bundle):
    manifest = read_json(bundle / 'release-manifest.json')
    require(manifest.get('version') == __version__ and manifest.get('format') == 'decision-tracker.windows-bundle/v1',
            'INSTALLATION_DAMAGED', 'The application bundle does not match this installer.')
    require(isinstance(manifest.get('files'), dict) and len(manifest['files']) > 20,
            'INSTALLATION_DAMAGED', 'The application inventory is incomplete.')
    for name, digest in manifest['files'].items():
        path = bundle / name
        require(not Path(name).is_absolute() and '..' not in Path(name).parts,
                'INSTALLATION_DAMAGED', 'The installation inventory has an invalid path.')
        safe_path(path)
        require(path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest() == digest,
                'INSTALLATION_DAMAGED', 'An application file is missing or changed. Run Setup again to repair it.')
    return manifest


def receipt(root):
    value = read_json(root / 'installation.json')
    require(value.get('format') == APP_ID and value.get('owner_sid') == owner_sid()
            and value.get('root') == str(root), 'INSTALLATION_CONFLICT',
            'This folder is not an installation owned by the current user.')
    require(isinstance(value.get('version'), str) and '/' not in value['version']
            and '\\' not in value['version'] and '..' not in value['version'],
            'INSTALLATION_DAMAGED', 'The installed version information is invalid.')
    return value


def deployment_for(root):
    return safe_path(receipt(root)['deployment'])


def owned_deployment(root, path):
    old = receipt(root)
    require(str(path) == old['deployment'], 'INSTALLATION_CONFLICT', 'The deployment binding changed. Preserve it for review.')
    value, cfg = load(path, check_runtime=False)
    old_bundle = root / 'versions' / old['version']
    require(value['python'] == str(old_bundle / 'runtime' / 'python.exe')
            and value['source_root'] == str(old_bundle / 'runtime' / 'site-packages'),
            'INSTALLATION_CONFLICT', 'The application binding changed. Preserve it for review.')
    return value, cfg


def recover_activation(root, path):
    """Finish only an exactly identified, interrupted installer binding update."""
    journal = root / 'activation-pending.json'
    if not journal.exists():
        return
    value = read_json(journal)
    require(value.get('format') == APP_ID and value.get('owner_sid') == owner_sid()
            and value.get('root') == str(root) and value.get('deployment') == str(path),
            'INSTALLATION_CONFLICT', 'Interrupted setup belongs to another installation. Preserve it for review.')
    old, new = value['before'], value['after']
    require(value['receipt_after'] == {'format': APP_ID, 'owner_sid': owner_sid(),
                'root': str(root), 'version': __version__, 'deployment': str(path)},
            'INSTALLATION_CONFLICT', 'Interrupted setup receipt is invalid. Preserve it for review.')
    previous = value['receipt_before']['version']
    require('/' not in previous and '\\' not in previous and '..' not in previous
            and old['python'] == str(root / 'versions' / previous / 'runtime/python.exe')
            and old['source_root'] == str(root / 'versions' / previous / 'runtime/site-packages'),
            'INSTALLATION_CONFLICT', 'Interrupted setup has an unrelated application binding.')
    require(set(old) == set(new) and all(old[k] == new[k] for k in old if k not in ('python', 'source_root')),
            'INSTALLATION_CONFLICT', 'Interrupted setup changed deployment identity. Preserve it for review.')
    require(new['python'] == str(bundle_for(root) / 'runtime/python.exe')
            and new['source_root'] == str(bundle_for(root) / 'runtime/site-packages'),
            'INSTALLATION_CONFLICT', 'Use the matching Setup to complete interrupted installation.')
    current = read_json(path)
    current_receipt = receipt(root)
    require(current in (old, new) and current_receipt in (value['receipt_before'], value['receipt_after']),
            'INSTALLATION_CONFLICT', 'Deployment changed after interrupted setup. Preserve it for review.')
    if current == new:
        atomic_json(root / 'installation.json', value['receipt_after'])
    else:
        require(current_receipt == value['receipt_before'], 'INSTALLATION_CONFLICT',
                'Interrupted setup bindings disagree. Preserve them for review.')
    journal.unlink()


def stopped(value, cfg, seconds=30):
    """Use the owner pipe and then prove exclusive service-lock acquisition."""
    from .windows_local import admin_request
    from .api import InstanceLock
    safe_path(cfg.root).mkdir(parents=True, exist_ok=True)
    try:
        admin_request(value['deployment_id'], 'stop')
    except OSError as exc:
        if exc.errno not in (2, 3):
            raise Fault('SERVICE_UNAVAILABLE', 'Cannot stop the application safely. Close drafts and retry Setup.') from None
    deadline = time.monotonic() + seconds
    while True:
        lock = InstanceLock(cfg.root / '.service.lock')
        try:
            lock.acquire()
            lock.release()
            return
        except Fault:
            require(time.monotonic() < deadline, 'SERVICE_BUSY', 'The application is still busy. Close drafts and retry Setup.')
            time.sleep(.1)


def prepare(root):
    root = safe_path(root)
    if not (root / 'installation.json').exists():
        return
    path = deployment_for(root)
    value, cfg = load(path, check_runtime=False)
    with coordinator(value):
        recover_activation(root, path)
        value, cfg = owned_deployment(root, path)
        existing = path.parent / 'installation-maintenance.json'
        if existing.exists():
            require(read_json(existing).get('root') == str(root), 'INSTALLATION_CONFLICT',
                    'An unrelated maintenance operation is active.')
        stopped(value, cfg)
        atomic_json(path.parent / 'installation-maintenance.json',
                    {'format': APP_ID, 'root': str(root), 'deployment_id': value['deployment_id']})


def activate(root, path=None, port=8765):
    root = safe_path(root)
    bundle = bundle_for(root)
    validate_bundle(bundle)
    path = safe_path(path or default_path())
    flag = path.parent / 'installation-maintenance.json'
    if flag.exists():
        require(read_json(flag).get('root') == str(root), 'INSTALLATION_CONFLICT',
                'An unrelated maintenance operation is active.')
    python = bundle / 'runtime' / 'python.exe'
    source = bundle / 'runtime' / 'site-packages'
    prior = (root / 'installation.json').exists()
    if prior:
        value, cfg = load(path, check_runtime=False)
        with coordinator(value):
            recover_activation(root, path)
            value, cfg = owned_deployment(root, path)
            stopped(value, cfg)
            # Verify the credential store without reading secret values or initializing it.
            from .credentials import Credentials
            Credentials(Path(cfg.auth_store)).state()
            original = {k: v for k, v in value.items() if k != 'path'}
            value = dict(original, python=str(python), source_root=str(source))
            next_receipt = {'format': APP_ID, 'owner_sid': owner_sid(), 'root': str(root),
                            'version': __version__, 'deployment': str(path)}
            journal = root / 'activation-pending.json'
            atomic_json(journal, {'format': APP_ID, 'owner_sid': owner_sid(), 'root': str(root),
                        'deployment': str(path), 'before': original, 'after': value,
                        'receipt_before': receipt(root), 'receipt_after': next_receipt})
            atomic_json(path, value)
            try:
                atomic_json(root / 'installation.json', next_receipt)
            except Exception:
                atomic_json(path, original)
                journal.unlink()
                raise
            journal.unlink()
    else:
        require(not path.exists(), 'INSTALLATION_CONFLICT',
                'An existing manual installation uses this deployment. Preserve it; install with a separate deployment or review migration.')
        initialize(path, python=python, source_root=source, port=port)
        atomic_json(root / 'installation.json', {'format': APP_ID, 'owner_sid': owner_sid(),
                    'root': str(root), 'version': __version__, 'deployment': str(path)})
    flag = path.parent / 'installation-maintenance.json'
    if flag.exists():
        marker = read_json(flag)
        require(marker.get('root') == str(root), 'INSTALLATION_CONFLICT', 'An unrelated maintenance operation is active.')
        flag.unlink()
    # Refresh only an already-owned optional URI handler. A foreign handler is preserved.
    warning = None
    if (path.parent / 'protocol-registration.json').exists():
        try:
            install_protocol(path)
        except Fault as exc:
            warning = exc.code
    return {'installed': True, 'version': __version__, 'protocol_warning': warning}


def copy_code(code):
    user = ctypes.WinDLL('user32', use_last_error=True)
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.GlobalAlloc.argtypes = [ctypes.c_uint, ctypes.c_size_t]
    kernel.GlobalAlloc.restype = ctypes.c_void_p
    kernel.GlobalLock.argtypes = [ctypes.c_void_p]
    kernel.GlobalLock.restype = ctypes.c_void_p
    kernel.GlobalUnlock.argtypes = [ctypes.c_void_p]
    kernel.GlobalFree.argtypes = [ctypes.c_void_p]
    user.SetClipboardData.argtypes = [ctypes.c_uint, ctypes.c_void_p]
    user.SetClipboardData.restype = ctypes.c_void_p
    data = (code + '\0').encode('utf-16-le')
    handle = kernel.GlobalAlloc(0x42, len(data))
    require(handle, 'CLIPBOARD_UNAVAILABLE', 'Cannot copy the setup code. Retry first-time setup.')
    pointer = kernel.GlobalLock(handle)
    if not pointer:
        kernel.GlobalFree(handle)
        raise Fault('CLIPBOARD_UNAVAILABLE', 'Cannot copy the setup code. Retry first-time setup.')
    ctypes.memmove(pointer, data, len(data))
    kernel.GlobalUnlock(handle)
    if not user.OpenClipboard(None):
        kernel.GlobalFree(handle)
        raise Fault('CLIPBOARD_UNAVAILABLE', 'The clipboard is busy. Retry first-time setup.')
    try:
        require(user.EmptyClipboard() and user.SetClipboardData(13, handle),
                'CLIPBOARD_UNAVAILABLE', 'Cannot copy the setup code. Retry first-time setup.')
        handle = None  # Windows owns it now.
    finally:
        user.CloseClipboard()
        if handle:
            kernel.GlobalFree(handle)


def message(text, title='Decision Tracker', flags=0):
    return ctypes.windll.user32.MessageBoxW(None, text, title, flags)


def first_launch(root):
    root = safe_path(root)
    path = deployment_for(root)
    value, cfg = load(path)
    from .credentials import Credentials
    state = Credentials(Path(cfg.auth_store)).state()['state']
    if state == 'uninitialized':
        # No code is generated until the user explicitly requests copying it.
        if message('Welcome to Decision Tracker.\n\nClick OK to copy a one-time setup code and open your browser. '
                   'Paste the code into the setup form and choose your private password. '
                   'The code expires after 15 minutes.\n\nCancel leaves setup unfinished.', 'First-time setup', 1) != 1:
            return {'opened': False}
        result = local_admin(path, 'setup-code')
        copy_code(result.pop('code'))
    return open_app(path)


def uninstall(root):
    root = safe_path(root)
    prepare(root)
    path = deployment_for(root)
    if (path.parent / 'protocol-registration.json').exists():
        try:
            uninstall_protocol(path)
        except Fault as exc:
            if exc.code != 'REGISTRATION_CONFLICT':
                raise
    flag = path.parent / 'installation-maintenance.json'
    # Retain the maintenance marker until reinstall: dangling launch paths must not restart.
    return {'data_preserved': True, 'maintenance_marker': flag.name}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['activate', 'prepare', 'open', 'uninstall'])
    parser.add_argument('--install-root', type=Path, required=True)
    parser.add_argument('--deployment', type=Path)
    parser.add_argument('--port', type=int, default=8765)
    args = parser.parse_args()
    try:
        if args.action == 'activate':
            activate(args.install_root, args.deployment, args.port)
        elif args.action == 'prepare':
            prepare(args.install_root)
        elif args.action == 'uninstall':
            uninstall(args.install_root)
        else:
            first_launch(args.install_root)
    except Exception as exc:
        text = (exc.code + ': ' + str(exc)) if isinstance(exc, Fault) else 'Setup could not finish safely. Preserve your data and run Setup again to repair the installation.'
        if args.action == 'open':
            message(text, flags=0x10)
        else:
            # Nonsecret diagnostics only; setup codes are never returned here.
            sys.stderr.write(text + '\n')
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
