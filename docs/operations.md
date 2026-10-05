# Local operations and recovery

## Storage and credentials

Use a local nonsynchronized data root, separate from source and OneDrive. Configuration names environment variables, never values. The service rejects known network/OneDrive/linked paths and requires explicit local-custody confirmation. Local filesystem ownership remains the security boundary; this is not OS multi-tenancy.

Configure a separate agent principal with explicit project IDs and only needed capabilities. `read` permits retrieval/export; `write` permits ordinary changes; `decide` permits lifecycle authority; `maintain` permits backup/verify/import/restore checks; `registry` permits project catalog changes. `propose` supports noncommitting ordinary validation. Capabilities do not imply one another. Restart the service to load changed configuration or credentials; in-memory browser sessions expire on restart.

Browser idle expiry30min, absolute expiry8h. Sign out revokes its session. Failed sign-ins are rate limited. Credentials are not retained in browser storage.

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

Polymath's home page remains a separate file. Tools appears above Workspace; Sites stays below it. The Decision Tracker card opens http://127.0.0.1:8765/ in a new tab. The Ledger placeholder is preserved.

The scoped home receipt records the prior Sites and tools section, inserted Tools section, replacement section and before/after hashes. Roll back only when the current file matches the recorded post-change hash: remove the inserted section and restore the prior section. This preserves unrelated links without retaining a copy of the private folder index or credential-bearing launch URLs.

## Proof and limitations

Run software verification through native Calamum using tools/prove.py. Proof copies use synthetic data, bounded process supervision and source hashes. Actual browser observations are separate empirical evidence; a verifier cannot invent them. Retain failed attempts.

This first delivery targets the actual Windows/Python3.14 host. POSIX portability is designed, not qualified. Owner acceptance, source-project migrations, production-data onboarding, MCP and a dedicated GPT agent-access skill remain separate work.
