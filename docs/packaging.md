# Packaging and support handoff

[Documentation](README.md) · [Install](../README.md#quick-start) · [Verification](verification.md)

## Current candidate

The selected limited-test prerelease is `0.1.0a1`, tagged `v0.1.0a1` when published. Its conventional Windows Setup EXE targets Windows 11 x64 and installs for the current user. It includes pinned Python 3.14.8 and vendored runtime dependencies. The build is unsigned; signing and broader distribution remain separate. Wheel and source assets remain available for Python users and contributors. The wheel itself is not a standalone installer.

Build and qualify locally before preparing a draft GitHub prerelease. Publication, second-machine operator acceptance and source migration remain separate actions. Do not rename older `dev0` artifacts or claim a published release from a local build.

The current source includes deprecation approval. Native focused/integration evidence qualifies its source, wheel and source archive. Compiled-Setup qualification below belongs to an earlier source snapshot and has not been repeated for this update. No current Setup release is claimed. Select archives by retained source manifest/hash and runtime capabilities, rather than the shared `0.1.0a1` label. The health endpoint still reports the older `0.1.0.dev0` string; use authenticated schema discovery and source/asset correspondence for capability checks.

## Contents

The wheel contains application modules, browser assets, the legacy schema and Apache license metadata. The source archive also contains public guides, changelog, the portable agent skill, tests and native verification tools/catalog. `MANIFEST.in` defines source support inputs and excludes local state. Docs and the skill are companion material, not installed runtime modules; extract them from the source archive when delivering a wheel-only installation.

A new deployment starts with no projects, saved decisions or groups. Organization seed content is user data and is not bundled. Credentials, deployment descriptors, project and Library databases, backups, exports, preparation journals, developer environments and proof evidence are excluded from distribution. Inspect actual archive contents; Git ignore rules alone do not prove this boundary.

## Build and qualify locally

Pinned portable inputs live in `packaging/windows-inputs.json`. Obtain the specified official Python archive and Inno Setup compiler, verify the archive hashes and compiler publisher signature, and retain the receipt. Store local input paths in ignored `.local/installer-runtime.json` with `python_archive`, `compiler`, `compiler_sha256` and `wheelhouse`. The wheelhouse must contain the exact runtime dependency versions with Windows x64/Python 3.14 compatibility. Never put local paths, credentials or downloaded compiler binaries into source.

`tools/build_windows.py --output NEW_FOLDER --runtime-file FILE` builds offline from those inputs. For release qualification, use the compiled-Setup native lane below; it invokes this same builder in a source-corresponding copy. Keep the resulting EXE, wheel, source archive, `SHA256SUMS.txt`, bundle manifest, build receipt and proof. Use these exact tested assets for release; do not rebuild a replacement after qualification.

Use the repository development environment and native Calamum. Obtain its recorded local prerequisites as described in [Contributing](../CONTRIBUTING.md). From the repository root:

```powershell
.\.venv\Scripts\python.exe tools/prove.py --definition dt-windows-installer --budget-seconds 360
.\.venv\Scripts\python.exe tools/prove.py --definition dt-package --budget-seconds 240
.\.venv\Scripts\python.exe tools/prove.py --definition dt-integration --budget-seconds 480
```

The package proof builds both archives in an isolated proof copy. It checks required files, excluded state, archive hashes, runtime dependency consistency, byte-identical installed assets and a fresh environment without Calamum or test dependencies. On Windows it starts, reuses and safely stops an isolated managed service. Browser dispatch is stubbed for the CLI open check; real browser workflows are separately exercised by integration.

Keep the proof directory, source manifest, stdout/stderr, package receipt and archive SHA256 values. Final candidates must match the qualified source. Retrieve the retained wheel/source archives from that proof, rather than rebuilding an unverified replacement. Label them alpha candidates. Do not clean retained failures or change live deployments as part of building.

## Install and first boot

Use [Windows Setup and repair](windows-installation.md) for the EXE workflow. The following is the Python alternative.

In a new environment, install the retained wheel with pip. Online pip resolves its pinned runtime dependencies; offline installation also needs compatible wheels for all runtime dependencies. A source archive alone is not an offline dependency bundle. Run `pip check`, then the installed CLI help. Follow [Quick start](../README.md#quick-start) to initialize the current-user launcher, privately generate a setup code and choose a password. Protocol registration is optional and explicit. Keep the installed environment in place because the launcher records its interpreter.

Decisions and Projects select a project in their heading area. Library works without a project, stores reusable content and chooses a destination in staging. Finished publication copies are closed and protected. Group tags end at staging. Browser staging and drafts do not survive closing the tab. See [Library](saved-decisions.md) for partial-publication recovery and exact retry.

## Upgrade and recovery

Preserve the currently installed package/environment and checked backups before replacing runtime files. Back up registered project ledgers, the catalog and Library independently; project backups do not include Library. Credentials remain private and bound to the local account. Stop the managed service through its supported command before upgrading. Install the qualified candidate in the chosen environment, run `pip check` and CLI help, and update the launcher explicitly if the interpreter location changes.

Reuse the existing deployment rather than creating duplicate credentials or projects. Start with `service ensure-running`, verify service identity and inspect existing project/Library content before resuming writes. Schema upgrades remain explicit and require their existing checked-backup process. Installing a newer binary does not authorize migration or downgrade. Do not use an older binary on newer history unless compatibility has been qualified. Restore checks prepare isolated candidates; they do not overwrite active data. See [Operations](operations.md) and [Legacy recovery](legacy-import.md).

New deprecation approval events require a runtime advertising `deprecation_approval_v1`, even when the ledger remains SQL schema 2, 3 or 4. Preserve a capable qualified runtime and checked project/catalog/Library backups before replacement. Verify the runtime capability and retained source/asset hashes; the package version or SQL schema number alone is insufficient. An older backup discards later writes and is not a substitute for forward recovery. See [the event compatibility contract](interfaces.md#decision-approval-events-schema-2).

## Support record

Provide the version, archive hashes, install/launch steps, platform limits and this documentation bundle. For a fault, retain the error code, request ID, exact pending request and nonsecret proof/service status. Report whether an operation is uncommitted, committed or uncertain; retry uncertain requests exactly. Never include passwords, tokens, setup codes or private records in public reports. Security reports follow [Security](../SECURITY.md).

Read [Verification](verification.md) for actual test evidence. Passing isolated checks is separate from owner acceptance, a published release and production qualification.

## GitHub prerelease preparation

Select a verified source commit and map each retained asset hash to its proof/source manifest. Check all distribution contents and third-party notices. Prepare release notes with Windows 11 x64 limits, unsigned-app guidance, retained-data uninstall behavior and pending second-machine acceptance. Prepare a draft prerelease with tag `v0.1.0a1` and the tested EXE, wheel, source archive and checksums. Do not upload local build logs, credentials, deployment state or business planning. Keep publication authority distinct from local preparation.
