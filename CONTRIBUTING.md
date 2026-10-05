# Contributing

Keep decision semantics in a shared service. Browser, CLI and agent interfaces
must not bypass authorization, revision checks or history.

## Environment

Use Python 3.14 in `.venv`, without global site packages. The initial environment
is captured by `requirements-dev.lock`. The locally built Calamum wheel and
its source/hash receipt are retained under ignored `.local/`; obtaining that
wheel is an explicit prerequisite for recreating this exact development setup.

After the Calamum wheel has been supplied:
```powershell
python -m venv .venv
.venv/Scripts/python.exe -m pip install --find-links .local/wheels -r requirements-dev.lock
.venv/Scripts/python.exe -m pip install --no-build-isolation --no-deps -e .
.venv/Scripts/python.exe -m pip check
```

## Validate with native Calamum

```powershell
$env:CALAMUM_CONFIG_ROOT = Join-Path (Get-Location) '.local/calamum-config'
.venv/Scripts/calamum.exe project validate . --json
.venv/Scripts/calamum.exe test list --json
.venv/Scripts/calamum.exe test show dt-bootstrap --json
.venv/Scripts/calamum.exe test run dt-bootstrap --dry-run --json
.venv/Scripts/python.exe tools/prove.py --definition dt-bootstrap
.venv/Scripts/calamum.exe test runs list --json
.venv/Scripts/calamum.exe test reports generate --scope project --project decision-tracker --json
```

Do not invoke PyTest directly. Calamum owns test execution and retained evidence;
the proof wrapper adds bounded supervision and source correspondence.

Bootstrap, focused, integration and observed-browser definitions are registered.
Run tools/prove.py --definition dt-integration --budget-seconds 300 for application regression.
The browser lane requires actual observations; see tools/browser_host.py. Do not register placeholder passing definitions for planned
capabilities. Preserve failed evidence and investigate failures before rerunning.

Use explicit staging and review diffs. Never commit credentials, real project
data, environment folders or generated evidence. Do not push or publish without
owner authorization. Dependency changes must retain exact versions and evidence.
