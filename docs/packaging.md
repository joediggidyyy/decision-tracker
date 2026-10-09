# Packaging and support handoff

[Documentation](README.md) · [Install](../README.md#quick-start) · [Verification](verification.md)

## Current candidate

The application remains a local-use alpha, version `0.1.0.dev0`, requiring Python 3.14 or newer. Managed launch is qualified on Windows. Prepare a Python wheel and a source distribution. The wheel is not a standalone executable or a Windows installer. It installs the `decision-tracker` console command and runtime dependencies into the chosen Python environment.

No public release, package-index upload or repository push is implied by a local build. Keep the current version until a release version is selected. Source migration execution and broader platform qualification remain separate.

## Contents

The wheel contains application modules, browser assets, the legacy schema and Apache license metadata. The source archive also contains public guides, changelog, the portable agent skill, tests and native verification tools/catalog. `MANIFEST.in` defines source support inputs and excludes local state. Docs and the skill are companion material, not installed runtime modules; extract them from the source archive when delivering a wheel-only installation.

A new deployment starts with no projects, saved decisions or groups. Organization seed content is user data and is not bundled. Credentials, deployment descriptors, project and Library databases, backups, exports, preparation journals, developer environments and proof evidence are excluded from distribution. Inspect actual archive contents; Git ignore rules alone do not prove this boundary.

## Build and qualify locally

Use the repository development environment and native Calamum. Obtain its recorded local prerequisites as described in [Contributing](../CONTRIBUTING.md). From the repository root:

```powershell
.\.venv\Scripts\python.exe tools/prove.py --definition dt-package --budget-seconds 240
.\.venv\Scripts\python.exe tools/prove.py --definition dt-integration --budget-seconds 480
```

The package proof builds both archives in an isolated proof copy. It checks required files, excluded state, archive hashes, runtime dependency consistency, byte-identical installed assets and a fresh environment without Calamum or test dependencies. On Windows it starts, reuses and safely stops an isolated managed service. Browser dispatch is stubbed for the CLI open check; real browser workflows are separately exercised by integration.

Keep the proof directory, source manifest, stdout/stderr, package receipt and archive SHA256 values. Final candidates must match the qualified source. Retrieve the retained wheel/source archives from that proof, rather than rebuilding an unverified replacement. Label them alpha candidates. Do not clean retained failures or change live deployments as part of building.

## Install and first boot

In a new environment, install the retained wheel with pip. Online pip resolves its pinned runtime dependencies; offline installation also needs compatible wheels for all runtime dependencies. A source archive alone is not an offline dependency bundle. Run `pip check`, then the installed CLI help. Follow [Quick start](../README.md#quick-start) to initialize the current-user launcher, privately generate a setup code and choose a password. Protocol registration is optional and explicit. Keep the installed environment in place because the launcher records its interpreter.

Decisions and Projects select a project in their heading area. Library works without a project, stores reusable content and chooses a destination in staging. Finished publication copies are closed and protected. Group tags end at staging. Browser staging and drafts do not survive closing the tab. See [Library](saved-decisions.md) for partial-publication recovery and exact retry.

## Upgrade and recovery

Preserve the currently installed package/environment and checked backups before replacing runtime files. Back up registered project ledgers, the catalog and Library independently; project backups do not include Library. Credentials remain private and bound to the local account. Stop the managed service through its supported command before upgrading. Install the qualified candidate in the chosen environment, run `pip check` and CLI help, and update the launcher explicitly if the interpreter location changes.

Reuse the existing deployment rather than creating duplicate credentials or projects. Start with `service ensure-running`, verify service identity and inspect existing project/Library content before resuming writes. Schema upgrades remain explicit and require their existing checked-backup process. Installing a newer binary does not authorize migration or downgrade. Do not use an older binary on newer history unless compatibility has been qualified. Restore checks prepare isolated candidates; they do not overwrite active data. See [Operations](operations.md) and [Legacy recovery](legacy-import.md).

## Support record

Provide the version, archive hashes, install/launch steps, platform limits and this documentation bundle. For a fault, retain the error code, request ID, exact pending request and nonsecret proof/service status. Report whether an operation is uncommitted, committed or uncertain; retry uncertain requests exactly. Never include passwords, tokens, setup codes or private records in public reports. Security reports follow [Security](../SECURITY.md).

Read [Verification](verification.md) for actual test evidence. Passing isolated checks is separate from owner acceptance, a published release and production qualification.
