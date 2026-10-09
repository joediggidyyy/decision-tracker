# Calamum workflow

[Documentation](README.md) · [Home](../README.md)

Calamum is the testing substrate, not just a wrapper for one runner.
The CLI and Python facade calamum.api provide project context, catalog discovery,
execution, retained runs and job/project/domain aggregates.

## Project and catalog

Native `calamum project register` creates the root `.calamum/project.json`.
Portable shared paths remain in that descriptor. Interpreter and active-project
state belong in a machine-local overlay under `.local/calamum-config`.
Use CALAMUM_CONFIG_ROOT for this project-local state.

Resolution order is explicit --project, nearest descriptor, CALAMUM_PROJECT,
then active local state. Path precedence is explicit flags, local overlay,
descriptor, defaults. Inspect `project current`, `project show`, `project list`
and `project validate` rather than assuming the active target.

The catalog uses controlled category/profile/tag/policy vocabulary from the
Calamum README. One definition tests one concern and can combine pytest
(code assertions), sandbox_test (controlled workflow) and empirical_test
(actual observations). A lane name does not itself create OS isolation.
The catalog now binds bootstrap, core behavior, integrated recovery/CLI/security and actual browser observations.

## Evidence and reports

Use `test list`, `test show ID`, dry-run, then the bounded proof command in
CONTRIBUTING. Inspect `test runs list` and `test runs show RUN_ID`.
Each native run retains report.json, report.md, manifest.json, checksums.json,
stdout/stderr and an append-only run index under .calamum/generated/runs.

Use `test reports generate --scope project --project decision-tracker` for project aggregates,
or job/domain scopes when those contexts actually apply. Inspect reports list/show.
Aggregate output is under .calamum/generated/reports/generated. Unsigned local
evidence is not an authenticated signed release.

## Optional capabilities

For fresh user-installation qualification, run `tools/prove.py --definition dt-package --budget-seconds 180`. It builds a wheel, installs only runtime dependencies into a new environment, verifies the installed console script and packaged assets, and exercises isolated Windows managed startup, reuse and shutdown. It reads the served sign-in page; browser dispatch is stubbed for the CLI `service open` check. No owner data or protocol registry entries are changed by this proof. It also builds a source archive and inspects both archives for required runtime/support files, licenses and excluded local data. Build artifacts and SHA256 values are retained with the proof. See [Packaging](packaging.md).

Monitor capability discovery and optional signing were reviewed. Hardware/packet
capture, privileged repair and signed publication are not required for this app
bootstrap and are not activated. Future empirical browser checks must retain
real observations; placeholder output cannot replace them.

The setup receipt retains README/help inspection, installed versions, wheel hashes,
native registration/readback and verification evidence under .local/setup.

For project aggregates use the registered ID decision-tracker. In the inspected
Calamum0.3.1 build, --project . resolved context but filtered aggregates by the
literal selector, producing no matched runs. The failed attempt is retained;
the stable-ID command is the verified route. No upstream source was modified.

Credential and lifecycle verification uses `dt-auth-focus`; actual account interface observation uses `dt-account-browser`. `dt-integration` is the final combined checkpoint. Operator-reported system-browser acceptance is recorded separately from native run results.

---

<p align="center">Maintained by Polymath Global</p>

## Action-form browser proof

`tools/prove.py --definition dt-deprecation-focus --budget-seconds 240` qualifies shared deprecation approval, immutable history/replay/recovery, CLI reads and the actual browser source-removal and tooltip observations. `dt-integration --budget-seconds 480` includes these assertions through its existing tests scope. Retained failed attempts remain evidence; confirm proof-copy/source hashes before claiming qualification.

`tools/prove.py --definition dt-action-forms --budget-seconds 240` runs the focused browser and resolution checks through native Calamum. `dt-integration` includes these checks. The browser test uses disposable local data, a synthetic password and an ephemeral loopback port.

Provide Playwright through `NODE_PATH`, with browser executable overrides `PROOF_BROWSER_EXECUTABLE` and `PROOF_FULL_BROWSER`. Alternatively, keep these machine-local paths in ignored `.local/browser-runtime.json`, using keys `node_modules`, `headless_executable` and `browser_executable`. The proof supervisor validates and loads that file. No browser runtime path belongs in portable source. The full Chromium executable supports a disposable test extension that sets and reads actual browser zoom; CSS scaling is not used as a substitute.

Browser screenshots and `observations.json` are retained under each proof copy's `.local/action-browser`. Test profiles, credentials and extension files are isolated there and remain untracked.

## Projects and data proof

`tools/prove.py --definition dt-projects-data --budget-seconds 240` runs candidate service/API checks and isolated Chromium administration workflows through native Calamum. It retains screenshots at wide/320-pixel layouts and actual 200% browser zoom, plus named observations. The integrated catalog includes these tests. No production registry or decision mutations are used by this proof.

## Planning-link proof

`tools/prove.py --definition dt-planning-links --budget-seconds 240` exercises planning-link receipts, anchor and policy failures, schema-3 upgrade/rollback, backup/native round-trips, protected baselines, reopen cycles, owner-only policy routing and the compact CLI. An isolated Chromium test retains tag/form/history observations and wide/320-pixel screenshots under the proof copy's `.local/planning-link-browser`. `dt-integration` includes these tests. `dt-applications` remains a compatibility definition selector. Source-correspondence manifests distinguish tested code from later documentation-only changes; no production ledger is a fixture.

## Legacy capability proof

`python tools/prove.py --definition dt-legacy --budget-seconds 240` selects the bounded native legacy lane. It covers synthetic lexical fidelity, immutable origin/native history separation, source paging/chunks/as-of, sparse native lifecycle and approval/graph guards, durable interruption/replay, candidate-only backup/export/restore and Chromium source visibility. `dt-integration` includes these checks and fresh wheel installation. Business repositories are not mounted into runtime proofs. Independent original-file/Git comparisons and source-only byte accounting are separate metadata evidence, and do not prove a converted import/export fits or authorize migration execution.

## Frozen source-input construction qualification

`python tools/prove.py --definition dt-migration --budget-seconds 180 --input-manifest FILE --runtime-file FILE` uses an explicitly configured existing rootless Linux backend. Both files remain local. The input manifest contains `contract_sha256` and `files`, each with `project`, `path`, `sha256` and `bytes`. Inputs must be reviewed copies under `.local`; original business folders are never mounted. The runtime file contains names-only `distribution`, `user`, `construction_root`, digest-pinned `image`, `retention_helper` and `retention_helper_sha256`. No credentials, image acquisition or dependency installation are supported.

The adapter verifies rootless/systemd/cgroup-v2 identity and actual image, user, mounts, network, capability, privilege and resource controls before starting. Native Calamum checks the shared production E1 encoder, frozen root identities/types/order, QA snapshot events, Ledger original commit objects/parent boundaries and source appearances. Input mounts are read-only; scratch and evidence use bounded tmpfs. Attempts, failures, actual inspection, terminal state and copied-source correspondence remain under `.local/proofs`. This is construction evidence. It does not construct a business import/candidate, certify source request/export fit, register data or satisfy unrelated signed product-activation gates.

## Windows installer proof

`tools/prove.py --definition dt-windows-installer --budget-seconds 360` builds fresh Setup, wheel and source assets from the copied source. It uses pinned local input files named in ignored `.local/installer-runtime.json`; no input download occurs during testing. Actual silent Setup installs into disposable nonsynchronized folders and qualifies service reuse, safe repair, credential/project/Library retention, uninstall and reinstall. A preexisting Setup registration blocks this test to preserve user installations. The interactive wizard and second-machine owner acceptance remain separate. Ordinary integration skips this dedicated compiled-Setup test and includes the focused installer lifecycle assertions.
