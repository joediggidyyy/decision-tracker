---
name: decision-tracker
description: Read, propose, and apply project decisions through the Decision Tracker CLI or API, including revision conflicts, history, and recovery. Use for an existing Decision Tracker service; not for generic task tracking or direct SQLite editing.
---

# Decision Tracker access

Use the application service as the sole ledger writer. The installed `decision-tracker` CLI and HTTP API enforce the same rules. This skill does not grant authority to change decisions, project registrations, credentials, or data custody. Continue within the user's existing authorization; read and prepare a concrete proposal when mutation authority is missing.

## Start or reuse the local service

For an installed Windows deployment, run `decision-tracker service ensure-running --json` before data access. It starts or reuses the service without opening a browser. Pass `--deployment FILE` for a nondefault deployment. Do not install a startup task or keep it alive with polling; useful requests and bounded draft leases manage the 90-minute idle policy.

Use `--credential-principal NAME` only for an explicitly provisioned stored agent credential. It verifies the deployment before transmitting the token. Alternatively use `--token-env NAME` for the authorized external credential. Never fall back to operator/password access. A missing credential is an owner provisioning input, not permission to create or expand access.

On connection loss, allow at most one ensure-running attempt and one retry within a 60-second recovery budget, preserving exact payload, request ID and principal. If unavailable or uncertain, retain the request and report its state. Do not repeat a human password change automatically.

Account recovery and token administration require an explicit human request for that operation. Human passwords and one-time codes are entered in the owner's private terminal/browser, never read into agent context. Recovery issuance and completion are CLI-only; agents do not use the browser to reset credentials.

## Connect and identify

Use the configured CLI executable (or the application repository's local environment), service origin and credential-variable **name**. The default service origin is `http://127.0.0.1:8765`. Never read, echo, place in command arguments, or store a credential value. Prefer a separately configured project-scoped agent principal. The following examples assume its environment variable is `DT_AGENT_TOKEN`; do not silently substitute the operator credential if it is absent.

```text
decision-tracker service status --token-env DT_AGENT_TOKEN --json
decision-tracker project list --token-env DT_AGENT_TOKEN --json
decision-tracker project show --project example --bind .local/example-binding.json --token-env DT_AGENT_TOKEN --json
decision-tracker decision list --project example --binding .local/example-binding.json --token-env DT_AGENT_TOKEN --json
```

Replace `example` with the intended project ID. Create the ignored binding directory if needed. A binding is an exclusive-created file containing project ID and ledger UUID, not credentials. Reuse an existing matching binding. Never infer identity from the working directory, silently rebind, or register a project to bypass a mismatch. Pass `--base-url` explicitly when using a configured alternate origin.

Use `decision get`, `decision history`, `query context`, and `query impact` with `--key D000001` and the same project/binding/token flags. Follow collection cursors and revision-pinned text chunks when responses indicate incomplete content. A stale cursor requires restarting the read; do not combine pages from different revisions. Impact results can be truncated.

## Prepare and apply a change

Read the current ledger and every affected decision revision before preparing a write. Retain the exact intended payload and a fresh UUID request ID in ignored local custody until the outcome is known. For linked changes, include both endpoints. Never derive a decision's revision from the ledger revision.

For atomic batches, use `change apply --input FILE --project example --binding .local/example-binding.json --token-env DT_AGENT_TOKEN --json`. The input is a complete envelope with:

- `expected_ledger_uuid`: the bound UUID.
- `expected_revision`: the read ledger revision.
- `expected_decision_revisions`: a map from each affected existing decision key to its read revision; empty for creating an independent decision.
- `request_id`: a new UUID; `reason`: the actual reason; `authority_refs`: genuine supporting references, not invented approval.
- `operations`: up to 25 operations, for example `{"op":"decision.create","data":{"title":"Storage","question":"Which storage engine?"}}`.

`--dry-run` validates and rolls back a decision change. It is not a reservation or a dry run for project/maintenance operations. Dry run and commit are distinct request bodies; assign the commit its own request ID. Convenience mutations also require `--expected-revision`, `--record-revision` for the selected record, `--request-id`, and `--reason`; their `--input` contains operation data, not the complete envelope. Multi-record commands use `--expected-decision-revisions FILE`.

After success, inspect the returned committed outcome and explicitly read back relevant state. Testing or implementation completion does not authorize closing a decision. Closure, locking, amendment, deprecation, rejected options and resolution changes require the appropriate user intent and service capability. Protected baselines require amendment, not ordinary edits. There is no hard-delete or silent overwrite.

## Conflicts and uncertain outcomes

On a lost response, retry the **identical payload and request ID with the same principal**. Matching committed requests replay before stale-revision checks. Do not generate a new ID merely because the response was lost. Bound retries; if the service remains unavailable, retain the payload and report the unknown outcome.

On a confirmed revision conflict, fetch current state, compare it with the original and intended changes, and reconcile within authorization. Use a new request ID only for a deliberately revised request. Never silently advance preconditions and overwrite another actor's work. Identity mismatch, lost authorization, or disabled project requires resolving that condition; do not switch ledgers or credentials automatically.

JSON mode returns one envelope. Exit codes: 0 success, 2 invalid input, 3 revision/identity conflict, 4 authentication/permission, 5 availability/retry, 1 unexpected failure. Preserve meaningful failure evidence without credentials.

## API and maintenance

For direct API access, use bearer authentication supplied by the runtime, `X-Ledger-UUID` on project routes and matching `expected_ledger_uuid` in changes. Discover the authenticated schema at `/api/v1/schema`. Submit batches to `POST /api/v1/projects/{project}/changes`; set `validate_only` for validation. Do not bypass the service with SQL or database-file edits.

Use the installed application's `docs/interfaces.md` and `docs/operations.md` for detailed maintenance contracts, or CLI help when only the package is available. Backup/verify/export are distinct from restore activation. Restore checks and imports retain isolated candidates; they never replace active data. Registration and production onboarding require their own authorized scope. Do not delete failed evidence.

Live notifications are freshness hints, not durable replay or approval to overwrite. Reconcile after reconnect. The browser's explicit refresh/review controls preserve drafts. No MCP server is supplied by this version; use the CLI/API rather than inventing MCP tools.
