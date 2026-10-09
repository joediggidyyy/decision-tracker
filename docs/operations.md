# Local operations and recovery

[Documentation](README.md) · [Home](../README.md)

Run command examples from the repository root after activating its environment:

```powershell
.\.venv\Scripts\Activate.ps1
```

For a new user installation, follow the [Quick start](../README.md#quick-start). Installing the package creates the `decision-tracker` console script. `decision-tracker service open` is the user launch point; it starts or reuses the managed backend and opens the default browser. Without activation, invoke `.\.venv\Scripts\decision-tracker.exe service open` directly. Polymath home is optional and its link may require browser permission to open an external application. The managed launcher is currently qualified on Windows only.

## Pages and reusable content

Select projects in the heading on Decisions or Projects. The adjacent connection dot opens workspace updates and service controls. Library works without a project and chooses the destination in staging. A fresh installation has no saved decisions or groups; no organization seed set is bundled.

Library content is separate from project ledgers. Include its checked saved-content backup in a deployment backup, or use its portable export for content transfer. Project/catalog backups do not include Library. In-progress drafts, checkbox selections and staging live only in the current browser tab; finish or retain pending publication requests before closing it. A completed Publish creates closed/protected copies. If publication stops partway, retain the receipts and review the actual phase before continuing. See [Saved decisions](saved-decisions.md) for recovery and [Packaging](packaging.md) for installation/upgrade handoff.

## Storage and credentials

Use local nonsynchronized storage, separate from source and OneDrive. The managed deployment lives under `%LOCALAPPDATA%/DecisionTracker/`. Configuration contains principal scopes and file paths; auth.sqlite holds password/token verifiers. secrets.bin uses current-user DPAPI for the launcher key and explicitly stored agent tokens. These files are not project exports or transferable ledger backups. OS account ownership remains the local trust boundary.

The browser's small footer key opens Account & access. Changing the password requires the current password, rotates this session and revokes other human sessions. Agent tokens remain active. Passwords require 15–128 characters; spaces and password managers are supported. Browser sessions expire after 90 minutes idle or 8 hours absolute. No password is needed to start the service.

Recovery is entirely CLI-only, in a private interactive owner terminal:

```text
decision-tracker auth recover
decision-tracker auth reset-password
```

The first command confirms human-session revocation and prints a 15-minute recovery code once. The second privately prompts for that code, new password and confirmation. Recovery leaves agents active. No browser recovery endpoint exists. Neither codes nor passwords are accepted as command arguments or JSON output.

Configure a separate agent principal with explicit project IDs and needed capabilities in the deployment config. `read`, `propose`, `write`, `decide`, `maintain` and `registry` do not imply one another. Restart to apply scope/configuration changes. Then, in the private owner terminal:

```text
decision-tracker auth token create --principal agent --store-local
decision-tracker auth token list --json
decision-tracker auth token rotate --token-id TOKEN_ID --store-local
decision-tracker auth token revoke --token-id TOKEN_ID
```

Creation/rotation prints the generated token once; `--store-local` additionally saves it through DPAPI for `--credential-principal agent`. List returns metadata only. No agent principal is created or granted access automatically. Revocation is checked on each request. The OS-owner named pipe is used for live administration; stopped-service administration holds coordinator and instance locks. Data commands still use HTTP only.

## Backup and restore

`data backup` captures SQLite using its backup API, validates integrity/history, hashes the immutable artifact and writes a receipt. `data export` creates deterministic native JSON retaining transaction and snapshot history. Artifact operations do not change decision revisions.

Use `data artifact-list`, then `data artifact-download --artifact-id UUID --output NEW_FILE` with a project binding. Output files are exclusive-create; existing files are not overwritten.

`data verify` checks SQLite integrity/foreign keys, transaction sequence/request hashes, snapshot hashes/revision chains and current-state correspondence. Hashes detect drift, not signer identity or external source authenticity.

`data restore-check --artifact-id UUID` copies a verified backup to isolated scratch storage, validates identity/revision and history, and reports activated=false. It never replaces active data.

`data import-validate --input EXPORT.json` retains an isolated validation candidate. `data import-new` also returns its contained relative path. Registration is a separate registry operation. To deliberately recover a ledger, stop and preserve the existing evidence, validate the candidate, disable the old registration, then register the candidate under a new project ID. There is no in-place swap. Imported receipts do not alter original transaction history. No legacy-format adapter or automatic migration is included.

Registry mutations make separate pre-change catalog backups; `service catalog-backup` creates an explicit one. Catalog recovery is an offline owner-managed activity, not an application repoint endpoint.

## Interruptions

A transaction either commits state/history/outcome together or rolls back. After a lost response, retry the exact request. A stale response requires explicit reconciliation. Busy databases return bounded503 after five seconds.

Artifacts start pending and become downloadable only after verification and publication. Failed operations retain evidence. Startup marks interrupted pending artifacts failed; recreate the artifact explicitly. Incomplete candidate creation is preserved for inspection. Do not delete evidence to suppress a failure.

A second process on the same data root is refused by an instance lock. Do not remove or bypass the lock while a service is running. Unknown schema versions refuse operations.

## Home integration and rollback

Polymath's home page remains a separate file. Tools appears above Workspace; Sites stays below it. The Decision Tracker card invokes decision-tracker://open, which starts or reuses the service and opens its URL through the default browser. The Ledger placeholder is preserved.

The scoped home receipt records the prior Sites and tools section, inserted Tools section, replacement section and before/after hashes. Roll back only when the current file matches the recorded post-change hash: remove the inserted section and restore the prior section. This preserves unrelated links without retaining a copy of the private folder index or credential-bearing launch URLs.

## Proof and limitations

Run software verification through native Calamum using tools/prove.py. Proof copies use synthetic data, bounded process supervision and source hashes. Actual browser observations are separate empirical evidence; a verifier cannot invent them. Retain failed attempts.

This first delivery targets the actual Windows/Python3.14 host. POSIX portability is designed, not qualified. The operator accepted the exercised browser and home-card workflows on 2026-10-05. Source-project migrations, real-data onboarding and MCP remain separate work. The portable agent-access skill is included under skills/decision-tracker.


## Managed and foreground lifecycle

`service status` reports public health only; use an authenticated project request to verify agent access or revocation.

`service ensure-running --json` starts or reuses the configured deployment without a browser. `service open` also opens the browser. `service stop` asks for a safe stop and refuses while operations or protected drafts are active. Readiness verifies a fresh nonce, deployment/configuration identity and HMAC before stored agent credentials are transmitted. An unrelated port occupant is never killed.

The managed idle default is 90 minutes; configuration permits 30–240. Status checks, SSE and draft heartbeats do not count as useful work. Unsaved drafts use 180-second leases renewed every 60 seconds, bounded to eight per session and 32 total. Loss or expiry of a lease starts a fresh idle period. Suspended browsers cannot hold a lease indefinitely. Session expiry remains independent.

For explicit foreground operation use `service serve --config PATH_TO_DEPLOYMENT_CONFIG`. Idle shutdown is disabled; Ctrl+C stops it. The same password store is used. A second writer is refused. `service uninstall-launcher` removes only an unchanged owned protocol registration and preserves data. No Windows startup task is created.

Legacy credential migration is explicit: `auth migrate --config OLD_CONFIG --deployment NEW_DESCRIPTOR` in a private owner terminal. Stop the old server first. Agent credentials must be present privately in their configured environment variables. Validation precedes publication; a protected config backup and receipt are retained. Legacy operator tokens are not imported. Partial setup files are preserved for inspection, never silently overwritten. Do not roll back to code that re-enables old operator tokens. Source-project ledger migrations remain separate.

Before real data adoption, create and verify a project-bound backup, download it to a new owner-controlled file and perform a restore check. Keep catalog and authentication recovery material separately. Synthetic proof does not establish a production backup schedule.

## Explicit data-format upgrades

New project ledgers initialize at schema 2 for compatibility. Schema 1 remains readable, verifiable, exportable and recoverable; writes require upgrading to schema 2. Planning links require schema 3. Each explicit upgrade advances one supported step: 1 to 2, then 2 to 3, with separate request IDs and backups. No startup or import silently upgrades a ledger. Older binaries refuse newer unsupported schemas. Native interchange retains its format: v2 includes approval events and upgrade evidence; v3 also preserves planning-link receipts and policy history.

Use the project's existing binding and maintain credential:

```text
decision-tracker data upgrade-check --project PROJECT --binding BINDING --credential-principal agents --json
decision-tracker data upgrade --project PROJECT --binding BINDING --credential-principal agents --expected-revision REVISION --request-id UUID --json
```

The check verifies history and reports version, compatibility, revision and backup-size estimates. It does not reserve the revision. The upgrade holds coordinated write exclusion, creates a native backup, independently restore-checks it, and changes schema in one transaction. UUID, ledger/decision revisions, historical snapshots and original request hashes are preserved. No historical approval is invented. The separate receipt identifies the backup. Retry the identical request ID and revision to recover a committed upgrade result.

An active deployment upgrade requires an exact project/UUID/revision and backup plan authorized for that operational mutation. Source implementation or a test pass is not deployment acceptance. Do not roll back to an incompatible binary after schema 2 or 3 has been activated. Replaying an earlier upgrade request returns its earlier receipt, even if the ledger has since advanced another schema step.

Recovery is explicit and offline. Before any subsequent writes, stop the service through its safe-stop path, obtain instance exclusion, verify the pre-upgrade backup and exact live identity/revision, retain the current file, then restore only under recovery authorization. After subsequent writes, use forward repair or a compatible current-schema backup with reconciliation of later transactions. Never automatically replace an active ledger or discard later writes.

<a id="planning-application-policy"></a>

This terminology update does not migrate schema-3 storage or rewrite history. Earlier commands remain compatibility aliases. After a new `decision.link` write, retain a binary that understands it; older binaries can reject its history even at schema 3. See [planning-link compatibility](interfaces.md#compatibility-with-earlier-planning-names).

## Planning-link policy

Planning anchors are required by default. Register project planning directories through the owner-local CLI after the explicit schema-3 upgrade:

```powershell
decision-tracker project policy set --project PROJECT --binding BINDING --expected-policy-revision 0 --planning-root C:/Project/planning --request-id UUID --reason "Register authoritative planning custody" --json
decision-tracker project policy show --project PROJECT --binding BINDING --credential-principal agents --json
```

`set` uses the existing Windows owner administration channel and needs no bearer credential. It has no HTTP or browser equivalent. `show` is an ordinary authorized read. Use the returned policy revision for later changes. Repeated `--planning-root` values replace the registered set; omitting the flag preserves it. Roots must be existing absolute directories, with no symbolic-link/junction traversal or drive-root registration. Supply only the selected project's planning directories.

An omitted-anchor receipt displays `recorded`; it does not claim a planning section is linked. To permit an omitted anchor, use the same `project policy set` command with `--anchor-required false`, current `--expected-policy-revision`, a new request ID and an honest reason. Use `true` to restore the requirement. A supplied invalid anchor fails under either policy. Each change records the local-owner actor, reason, time and policy revision independently of decision revisions.

Filesystem authorization is a separate local binding under the deployment data root. Backups/native imports preserve policy provenance but do not transfer this permission. After an import or recovery, register the reviewed planning roots locally before resolving documents. A failed local-binding publication denies file access; retry the identical current policy request to complete it. Replaying an older superseded policy does not activate its roots.

The browser's document pool discovers canonical JSON in the registered folders and includes previously linked documents that remain authorized. Add document browses subfolders or accepts a pasted source/companion path. It does not copy files, upload content, broaden roots or create a separate document registry. If inventory exceeds its bounds, use Add document to browse a narrower folder or paste the known path. Section and Link wait for a valid selection; missing files cannot produce a linked receipt.

## Inactive legacy recovery

Legacy import validation and publication use the existing `data import-validate` and `data import-new` commands. Validate-only retains an isolated scratch database but creates no published candidate or import intent. Publication first reserves a durable principal/request/body-hash/target-UUID/candidate binding. Retry uncertain outcomes with the same credential, exact file and request ID; changed content and identity collisions reject. Retain journal, incomplete preparation and source evidence for recovery.

Before registration, use existing `data export`, `backup`, `verify` or `restore-check` with `--candidate-id` and `--expected-candidate-digest`. Restore-check additionally requires the backup `--artifact-id`; it prepares a distinct inactive candidate and changes no project registration. Download the resulting artifact through `data artifact-download` with the same candidate/digest binding. These operations require maintain permission; their receipt is not a cutover or migration release. Never substitute a guessed UUID or path for the reviewed candidate.
