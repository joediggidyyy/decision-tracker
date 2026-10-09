"""Build an offline Windows installer from pinned local inputs. No deployment writes."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tomllib
import zipfile


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build(root, output, runtime_file):
    root, output = Path(root).resolve(), Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    inputs = json.loads((root / 'packaging/windows-inputs.json').read_text(encoding='utf-8'))
    runtime = json.loads(Path(runtime_file).read_text(encoding='utf-8'))
    archive, compiler, wheelhouse = [Path(runtime[k]).resolve() for k in ('python_archive', 'compiler', 'wheelhouse')]
    assert sha(archive) == inputs['python']['sha256'], 'Runtime input hash changed'
    assert compiler.name.lower() == 'iscc.exe' and compiler.is_file()
    assert sha(compiler) == runtime['compiler_sha256'], 'Compiler input hash changed'
    version = tomllib.loads((root / 'pyproject.toml').read_text(encoding='utf-8'))['project']['version']
    assert version == '0.1.0a1'
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', PYTHONIOENCODING='utf-8')
    env.pop('PYTHONPATH', None)
    def run(command):
        result = subprocess.run(command, cwd=root, env=env, capture_output=True, text=True, encoding='utf-8', timeout=150)
        (output / ('build-' + str(len(list(output.glob('build-*.log')))) + '.log')).write_text(result.stdout + result.stderr, encoding='utf-8')
        assert result.returncode == 0, result.stdout + result.stderr
    run([sys.executable, '-m', 'pip', 'wheel', '--no-deps', '--no-build-isolation', '--wheel-dir', str(output), str(root)])
    wheel = next(output.glob('decision_tracker-*.whl'))
    run([sys.executable, '-c', 'from setuptools.build_meta import build_sdist; import sys; build_sdist(sys.argv[1])', str(output)])
    bundle = output / 'bundle'
    python = bundle / 'runtime'
    python.mkdir(parents=True)
    with zipfile.ZipFile(archive) as z:
        for name in z.namelist():
            assert not Path(name).is_absolute() and '..' not in Path(name).parts
        z.extractall(python)
    site = python / 'site-packages'
    constraints = output / 'runtime-constraints.txt'
    constraints.write_text(''.join(k + '==' + v + '\n' for k, v in inputs['runtime_dependencies'].items()), encoding='utf-8')
    run([sys.executable, '-m', 'pip', 'install', '--no-index', '--find-links', str(wheelhouse), '--no-compile',
         '--constraint', str(constraints), '--target', str(site), str(wheel)])
    # Do not ship pip-generated wrappers bound to the build interpreter.
    wrappers = site / 'Scripts'
    if wrappers.exists():
        for file in wrappers.iterdir():
            assert file.is_file() and file.resolve().is_relative_to(site.resolve())
            file.unlink()
        wrappers.rmdir()
    (python / 'python314._pth').write_text('python314.zip\n.\nsite-packages\nimport site\n', encoding='utf-8')
    (site / 'sitecustomize.py').write_text('import sys\nsys.dont_write_bytecode = True\n', encoding='utf-8')
    support = bundle / 'support'
    support.mkdir()
    for name in ['README.md', 'CHANGELOG.md', 'LICENSE', 'NOTICE', 'SECURITY.md', 'CONTRIBUTING.md', 'AGENTS.md']:
        shutil.copyfile(root / name, support / name)
    for folder in ['docs', 'skills']:
        shutil.copytree(root / folder, support / folder)
    files = {p.relative_to(bundle).as_posix(): sha(p) for p in bundle.rglob('*') if p.is_file()}
    assert not any(p.startswith(('runtime/site-packages/calamum', 'runtime/site-packages/pytest',
                                  'runtime/site-packages/_pytest')) or p.endswith(('.sqlite', '.db')) for p in files)
    manifest = {'format': 'decision-tracker.windows-bundle/v1', 'version': version,
                'python': inputs['python'], 'runtime_dependencies': inputs['runtime_dependencies'], 'files': files}
    (bundle / 'release-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    run([str(compiler), '/DBundleDir=' + str(bundle), '/DProductVersion=' + version,
         '/DOutputPath=' + str(output), str(root / 'packaging/windows.iss')])
    assets = [*output.glob('*.exe'), *output.glob('*.whl'), *output.glob('*.tar.gz')]
    assert len(assets) == 3
    (output / 'SHA256SUMS.txt').write_text(''.join(sha(p) + '  ' + p.name + '\n' for p in assets), encoding='utf-8')
    receipt = {'version': version, 'assets': {p.name: sha(p) for p in assets},
               'runtime_sha256': sha(archive), 'compiler_sha256': sha(compiler), 'unsigned': True}
    (output / 'build-receipt.json').write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8')
    return receipt


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--runtime-file', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build(Path(__file__).resolve().parents[1], args.output, args.runtime_file), indent=2))
