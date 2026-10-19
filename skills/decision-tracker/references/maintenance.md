# Separately authorized maintenance

Read only for the authorized installer, credential, policy, data-format, candidate
or recovery-media task. Presence of a command is not permission to run it. Policy writes
and account recovery retain their owner-local CLI-only boundaries; there is no HTTP policy
write fallback. Use recovery.md for uncertain outcomes and actual finite limits.

## Windows installer access

A Setup installation includes the owner CLI at `%LOCALAPPDATA%/Programs/DecisionTracker/decision-tracker.cmd`. Use that installed command rather than requiring a developer environment. Its deployment defaults remain the same; pass `--deployment FILE` for an explicitly configured alternate deployment. Start menu launch handles first-time human setup. Agents must not read the clipboard or request setup codes.

Installer repair/uninstall use the recorded current-user ownership and preserve user data. `INSTALLATION_MAINTENANCE` blocks launch during incomplete Setup or after uninstall; use matching Setup to repair. Do not delete maintenance markers, rewrite installation/deployment receipts, adopt a foreign binding or force-stop an application. This skill does not authorize installer publication, upgrades, credential administration or data migration.

Account recovery and token administration require an explicit human request for that operation. Human passwords and one-time codes are entered in the owner's private terminal/browser, never read into agent context. Recovery issuance and completion are CLI-only; agents do not use the browser to reset credentials.

Use the source distribution or companion support material’s `docs/interfaces.md`, `docs/operations.md` and `docs/packaging.md` for detailed maintenance contracts, or CLI help when only the package is available. Backup/verify/export are distinct from restore activation. Restore checks and imports retain isolated candidates; they never replace active data. Registration and production onboarding require their own authorized scope. Do not delete failed evidence.

Read GET /api/v1/schema before relying on approval_events_v1. New ledgers use schema 2; schema-1 reads still work but writes require an explicit upgrade. `data upgrade-check` is read-only; `data upgrade` requires maintain, the bound project, expected revision and a UUID request ID. The service creates and restore-checks a backup before the atomic upgrade. An implementation instruction or successful test is not permission to upgrade an unrelated live ledger. Preserve the exact request for replay and retain the backup receipt. Never downgrade after new writes.

### Prepared candidate discovery

`data candidates` lists prepared candidates; `data prepare-candidate --candidate-id UUID` explicitly prepares an older retained import. Both require maintain and registry. `import-new` creates a preparation receipt, while `import-validate` does not. Registered identities, including disabled registrations, do not appear. Use enable for a disabled project rather than registering it again.

Register using the selected `candidate_id` and `logical_digest` as `--candidate-id` and `--expected-candidate-digest`, alongside the existing project/name/catalog-revision/request-ID fields. Preparation never approves imported decisions and registration never replaces or upgrades active data. Discovery does not authorize import or registration. No arbitrary filesystem browsing is exposed.

Exact-request retries apply to catalog and decision mutations. Export and backup creation have no such replay guarantee: after a lost response inspect the file list and report uncertainty; do not automatically create a duplicate.

Artifact manager reads: `data artifact-list --kind backup --order newest --limit 25` (or kind export) returns one kind with Previous/Next cursors, counts and inventory identity. Use returned cursors with the same kind/order/limit/project binding. Changed inventory returns CURSOR_STALE; restart the read without combining old and new pages. Omitting filters preserves legacy mixed forward listing.

