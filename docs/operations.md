# Local operations and recovery

## Storage and credentials

Use local nonsynchronized storage, separate from source and OneDrive. The managed deployment lives under `%LOCALAPPDATA%/DecisionTracker/`. Configuration contains principal scopes and file paths; auth.sqlite holds password/token verifiers. secrets.bin uses current-user DPAPI for the launcher key and explicitly stored agent tokens. These files are not project exports or transferable ledger backups. OS account ownership remains the local trust boundary.

The browser's small footer key opens Account & access. Changing the password requires the current password, rotates this session and revokes other human sessions. Agent tokens remain active. Passwords require 15–128 characters; spaces and password managers are supported. Browser sessions expire after 30 minutes idle or 8 hours absolute. No password is needed to start the service.

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

This first delivery targets the actual Windows/Python3.14 host. POSIX portability is designed, not qualified. Owner acceptance, source-project migrations, production-data onboarding and MCP remain separate work. The portable agent-access skill is included under skills/decision-tracker.


## Managed and foreground lifecycle

`service ensure-running --json` starts or reuses the configured deployment without a browser. `service open` also opens the browser. `service stop` asks for a safe stop and refuses while operations or protected drafts are active. Readiness verifies a fresh nonce, deployment/configuration identity and HMAC before stored agent credentials are transmitted. An unrelated port occupant is never killed.

The managed idle default is 90 minutes; configuration permits 30–240. Status checks, SSE and draft heartbeats do not count as useful work. Unsaved drafts use 180-second leases renewed every 60 seconds, bounded to eight per session and 32 total. Loss or expiry of a lease starts a fresh idle period. Suspended browsers cannot hold a lease indefinitely. Session expiry remains independent.

For explicit foreground operation use `service serve --config PATH_TO_DEPLOYMENT_CONFIG`. Idle shutdown is disabled; Ctrl+C stops it. The same password store is used. A second writer is refused. `service uninstall-launcher` removes only an unchanged owned protocol registration and preserves data. No Windows startup task is created.

Legacy credential migration is explicit: `auth migrate --config OLD_CONFIG --deployment NEW_DESCRIPTOR` in a private owner terminal. Stop the old server first. Agent credentials must be present privately in their configured environment variables. Validation precedes publication; a protected config backup and receipt are retained. Legacy operator tokens are not imported. Partial setup files are preserved for inspection, never silently overwritten. Do not roll back to code that re-enables old operator tokens. Source-project ledger migrations remain separate.

Before real data adoption, create and verify a project-bound backup, download it to a new owner-controlled file and perform a restore check. Keep catalog and authentication recovery material separately. Synthetic proof does not establish a production backup schedule.
