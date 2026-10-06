# Contributing

[Home](README.md) · [Documentation](docs/README.md) · [Security](SECURITY.md)

This guide is for authorized collaborators maintaining Decision Tracker. Propose changes within the approved project scope, retain evidence of their behavior, and obtain owner authorization before pushing or publishing.

Contributions are provided under the repository's [Apache License 2.0](LICENSE), unless explicitly stated otherwise. Retain applicable copyright and attribution notices.

Keep decision semantics in a shared service. Browser, CLI and agent interfaces
must not bypass authorization, revision checks or history.

## Development environment

Use Python 3.14 in `.venv`, without global site packages. The initial environment
is captured by `requirements-dev.lock`. The locally built Calamum wheel and
its source/hash receipt are retained under ignored `.local/`; obtaining that
wheel is an explicit prerequisite for recreating this exact development setup.

Run these commands from this repository root, after the Calamum wheel has been supplied:
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --find-links .local/wheels -r requirements-dev.lock
python -m pip install --no-build-isolation --no-deps -e .
python -m pip check
```

## Validate with native Calamum

```powershell
$env:CALAMUM_CONFIG_ROOT = Join-Path (Get-Location) '.local/calamum-config'
calamum project validate . --json
calamum test list --json
calamum test show dt-bootstrap --json
calamum test run dt-bootstrap --dry-run --json
python tools/prove.py --definition dt-bootstrap
calamum test runs list --json
calamum test reports generate --scope project --project decision-tracker --json
```

Run these examples with this repository’s environment activated. In each new terminal, run `.\.venv\Scripts\Activate.ps1` from the repository root first.

Do not invoke PyTest directly. Calamum owns test execution and retained evidence;
the proof wrapper adds bounded supervision and source correspondence.

Bootstrap, focused, integration and observed-browser definitions are registered.
For application regression:

```powershell
python tools/prove.py --definition dt-integration --budget-seconds 300
```

The browser lane requires actual observations; see tools/browser_host.py. Do not register placeholder passing definitions for planned
capabilities. Preserve failed evidence and investigate failures before rerunning.

Use explicit staging and review diffs. Never commit credentials, real project
data, environment folders or generated evidence. Do not push or publish without
owner authorization. Dependency changes must retain exact versions and evidence.

## Tracking and closeout

See [tracking boundaries](docs/tracking-boundaries.md) before staging. Keep historical home proof inputs under ignored `.local/home-integration`; they are a local test prerequisite, not public source. Before a push, inspect the staged diff, all newly transmitted history, remote identity and final native evidence. Obtain the operator's explicit push authorization when requested. Do not force-push or prune retained evidence during routine cleanup.

---

<p align="center">Maintained by Polymath Global</p>
