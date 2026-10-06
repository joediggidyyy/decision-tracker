---
name: decision-tracker
description: Read, propose, and apply project decisions through the Decision Tracker CLI or API, including revision conflicts, history, and recovery. Use for an existing Decision Tracker service; not for generic task tracking or direct SQLite editing.
---

# Decision Tracker access

## Planning application

Apply records that an authorized closed resolution has been incorporated into one designated authoritative planning section. It does not mark implementation, verification or acceptance complete. Confirm the cited planning content against the approved answer before recording this attestation; anchor/hash checks alone do not establish meaning. Do not mark every closed decision applied merely because the feature is available.

Read `planning_application` and `application_policy_revision` from `decision get`. `decision list` exposes `applied`. Open and deprecated records cannot be applied; protected closed baselines may append application evidence without changing their answer or approval. Reopen starts a fresh cycle, preserving old receipts. Reclosing the same answer requires fresh application. Read `decision applications --key KEY` and follow cursors for full historical receipts.

Use existing `decision apply` with project/binding/credential, key, expected ledger/record revisions, request ID and reason, plus `--expected-policy-revision`, `--planning-document PATH` and `--planning-section STABLE_ID`. The structured operation is `decision.apply` through `change apply`; save it separately from other mutations of that decision. Pin observations with `--expected-resolution-id`, `--expected-document-sha256` and, for Markdown input, `--expected-projection-sha256`. Preserve exact values for uncertain-outcome replay.

Anchors require a local native `codesentinel.canonical-document/v1` source or its generated Markdown companion inside explicitly registered project planning roots. GET `/api/v1/projects/{project}/planning-document?locator=PATH` returns readable headings and stable section/block IDs; follow returned cursors with the same locator. Source/projection changes invalidate pagination. The service rechecks bytes before commit. Missing/unavailable anchors reject only application recording, leave the decision unapplied and preserve form work; other project work can continue.

`project policy show` reads the policy. Only owner-local CLI `project policy set` can register roots or change `--anchor-required true/false`, with expected policy revision, request ID and reason. No browser/HTTP policy write exists. Existing agent credentials do not grant this owner administration permission. Do not loosen the requirement to bypass a failure without the user's explicit intent. Optional policy permits omission, recorded honestly as `omitted`; supplied invalid anchors still fail. Imports preserve policy history without granting local file access.

Schema 3 is required for application writes. `data upgrade-check/upgrade` extend the existing backup/restore-checked flow; schema 1 first advances to 2, then 2 to 3 under a new request ID. Existing ledgers do not upgrade silently, and unrelated live-ledger upgrades require their own authorized scope. Receipts retain actor/time, closure/approval, transaction/request, document version/hash, section content digest and policy. `generator_verification: not_checked` means no canonical generator verification ran; a matching Markdown source marker is narrower evidence.

Humans use the Planning document/Section/Apply form or plain CLI flags; never ask them to compose JSON. Generator workflows may prefill a decision link with URL-encoded `planning-document`, `planning-section` and optional observed-file `planning-sha256` fragment fields. The selected project/decision must match, the service reloads sections, and Apply remains explicit. Do not invent MCP tools, a new top-level CLI group, automatic generator execution or automatic planning incorporation.

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

## Approval events and data-format upgrades

Read GET /api/v1/schema before relying on approval_events_v1. New ledgers use schema 2; schema-1 reads still work but writes require an explicit upgrade. `data upgrade-check` is read-only; `data upgrade` requires maintain, the bound project, expected revision and a UUID request ID. The service creates and restore-checks a backup before the atomic upgrade. An implementation instruction or successful test is not permission to upgrade an unrelated live ledger. Preserve the exact request for replay and retain the backup receipt. Never downgrade after new writes.

`decision.close` accepts an approval object in their existing JSON input. Agent credentials cannot use authenticated_now. With actual authorized decision intent and decide capability, report external evidence using mode reported, approver, 1–32 sources and precision exact/date/unknown. Exact requires an offset-aware occurred_at and matching numeric utc_offset_minutes; date requires occurred_date plus offset; unknown omits occurrence/offset/timezone. Never invent dates or impersonate human approval. The server keeps recording identity/time separate from reported approval. Existing reference-only requests remain valid on schema 2.

A selected proposal requires expected_option_revision and matching answer text. Read the latest proposal before applying it. Resolution cannot share a batch with another mutation of that same decision. Follow latest_resolution_approval, paginated /approvals and /approvals/{event_id} for approval evidence; follow returned text chunks. PROPOSAL_CHANGED and UPGRADE_REQUIRED require reconciliation, not blind retry. These additions do not change credential scope or capabilities.

### Prepared candidate discovery

`data candidates` lists prepared candidates; `data prepare-candidate --candidate-id UUID` explicitly prepares an older retained import. Both require maintain and registry. `import-new` creates a preparation receipt, while `import-validate` does not. Registered identities, including disabled registrations, do not appear. Use enable for a disabled project rather than registering it again.

Register using the selected `candidate_id` and `logical_digest` as `--candidate-id` and `--expected-candidate-digest`, alongside the existing project/name/catalog-revision/request-ID fields. Preparation never approves imported decisions and registration never replaces or upgrades active data. Discovery does not authorize import or registration. No arbitrary filesystem browsing is exposed.

Exact-request retries apply to catalog and decision mutations. Export and backup creation have no such replay guarantee: after a lost response inspect the file list and report uncertainty; do not automatically create a duplicate.

Artifact manager reads: `data artifact-list --kind backup --order newest --limit 25` (or kind export) returns one kind with Previous/Next cursors, counts and inventory identity. Use returned cursors with the same kind/order/limit/project binding. Changed inventory returns CURSOR_STALE; restart the read without combining old and new pages. Omitting filters preserves legacy mixed forward listing.

## Closed-record mutation policy

Closed records reject ordinary content and work-state changes in the browser, CLI and API, including dry runs. Reopen must commit in a separate request before editing; then Close with current approval. Both endpoints of ordinary relationship changes must be open and unlocked. Protected baselines require Amend. Reopen, Protect, Amend and Deprecate retain their existing state, authority and evidence requirements. Inspection and historical snapshots remain available.

`decision edit-resolution` remains recognized for compatibility but is withdrawn for new writes (`INVALID_TRANSITION`, HTTP 422). Reopen, use `decision edit` on the open record, then Close. Exact historical committed requests still replay their original receipt after permission and payload checks; no history is rewritten. Reusing a request ID with different content still fails.

A batch cannot reopen and mutate or reclose the same closed-at-start decision. Retain a stale browser draft after remote closure; review current state and obtain authorized reopening instead of automatically advancing revisions. Disabled pane controls keep the fixed grid. Outside the pane, unavailable child mutation controls are hidden; Protect/Amend is beside Approval and Decide/Reopen stays beside Question. The browser label Decide invokes the existing `decision.close` operation; CLI `decision close` and status `closed` are unchanged.

## Challenges during investigation

Use a challenge to record investigation feedback that questions a premise, proposal or answer. When a decision is contested, read `decision history --key KEY` with the same project, binding and credential flags before continuing the investigation, proposing a resolution or applying one. Follow history cursors until complete. The ordinary record exposes the contested flag; the challenge message is recorded as the transaction reason in history. Review subsequent messages and source evidence rather than treating the flag alone as sufficient context. Address the challenge in the next investigation response. Live notifications indicate changed data; they do not automatically start an agent or convey the complete conversation. Do not resolve a challenge merely because it has been read.

## Browser resolution choices

Explicitly switching the resolution radio choice replaces the Decision, Why this choice and Change note fields. Selecting a proposal fills these fields from that proposal; selecting Write a different answer clears the answer and rationale and resets the generated change note. Drafts are not cached per choice and there is no additional preservation prompt. Editing a proposal answer converts it to a written answer while retaining the text being edited. Approval details remain independent of the solution choice.
