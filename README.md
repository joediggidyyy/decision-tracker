# Decision Tracker

Decision Tracker is a private Polymath application being built for portable,
project-aware decision records. The approved design combines SQLite storage,
a mutable browser workspace, a comprehensive CLI and a shared agent/program API.

**Current state:** repository and development-environment bootstrap. The application
service, browser and decision commands are not implemented yet.

## Development

Use Python 3.14 and a project-local `.venv`. Environment setup and native Calamum
commands are in [CONTRIBUTING.md](CONTRIBUTING.md).
The package currently exposes version metadata only; there is no application
console command to run.

The tracked Calamum descriptor is `.calamum/project.json`; the test catalog is
`catalog/test_definitions.json`. Generated evidence stays under
`.calamum/generated/` and is not committed.

## Design and boundaries

[Repository contract](docs/repository-contract.json) records the initialization
scope. [Architecture](docs/architecture.md) summarizes the approved application.
[Calamum workflow](docs/calamum.md) documents discovery, project resolution,
test lanes, retained runs and reporting.

The app will open from the Polymath home page in a new tab and preserve the
workspace's dark header and right-panel design. It remains independently hosted
on local loopback, with authenticated access and separate project databases.
The home-page integration is not installed by this bootstrap.

## Rights and release

This repository is private. No distribution license or public release has been
selected. No LICENSE is fabricated; this notice does not change ownership or
third-party license terms. Publication requires owner direction.
