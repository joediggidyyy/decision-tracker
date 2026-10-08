---
name: decision-tracker
description: Read, propose, record and link project decisions through the Decision Tracker CLI or API, including revision conflicts, history, and recovery. Use for an existing Decision Tracker service; not for generic task tracking or direct SQLite editing.
---

# Decision Tracker access

## When to record a decision

Record a choice or unresolved question when its durable consequence needs an explicit, retrievable rationale: data meaning/fidelity; identity, schema, interface or compatibility contracts; authority, permissions, custody or retention; failure, retry, recovery or integrity guarantees; or a substantial tradeoff, dependency or commitment that later work must respect. This includes agent-owned engineering decisions within delegated scope. Admit a consequential unresolved choice before dependent implementation; retain alternatives, evidence, owner, affected scope and what must be settled.

Registration and approval escalation are separate. Resolve agent-owned choices only within actual delegated authority and the existing service capability/approval contract; assigning owner_role=agent grants no authority. Escalate choices that exceed delegation, change settled requirements or need the human's judgment. Never invent human approval. Record an authorized resolution and its rationale even when no new human approval is required.

Routine mechanics can remain in execution documentation when they implement an already defined contract without introducing a consequential choice. Formatting and private variable names usually qualify; public names or formats that create a compatibility commitment can require a decision. Search existing decisions first. Cite settled requirements and record only the new choice; do not reopen an approved requirement merely to choose its engineering representation. Use the existing decision/options/references/link operations, not a second editable register or a new CLI root. The repository's docs/decision-workflow.md gives human-facing examples; these instructions remain self-contained when installed alone.

## Recommended proposals

Whenever presenting multiple proposals for a decision, explicitly identify exactly one as **Recommended**. Explain why it is preferred for the current requirements, including its benefits and costs. Do not rely on proposal order or leave the operator to infer the recommendation.

Record that recommendation in the Tracker as well as in any review presentation. The current proposal model has no dedicated recommendation field: append `(Recommended)` to the recommended proposal's title and include a concise recommendation rationale in its description. Keep the proposal's benefit and cost fields informative. Use the existing option operations; preserve proposal IDs and unrelated content. When changing the recommendation, remove the old recommended label so each decision has one current recommendation. Read current decision and proposal state before editing, and respect revision and closed-record controls.

Recommended is advisory. It does not mean selected, approved, closed, implemented or accepted. Do not change proposal disposition, resolve the decision or report operator approval merely to identify a recommendation.

## Planning links

Link records that an authorized closed resolution has been incorporated into one designated authoritative planning section. It does not mark implementation, verification or acceptance complete. Confirm the cited planning content against the approved answer before recording this attestation; anchor/hash checks alone do not establish meaning. Do not mark every closed decision linked merely because the feature is available.

Read `planning_link` (`recorded`, `linked`, `receipt`) and `planning_link_policy_revision` from `decision get`. `decision list` exposes `linked` and `planning_link_recorded`; writes return `planning_link_receipts`. Open and deprecated records cannot be linked; protected closed baselines may append planning-link evidence without changing their answer or approval. Reopen starts a fresh cycle, preserving old receipts. Reclosing the same answer requires a fresh link. Read `decision planning-links --key KEY` and follow cursors for full historical receipts.

Use existing `decision link` with project/binding/credential, key, expected ledger/record revisions, request ID and reason, plus `--expected-policy-revision`, `--planning-document PATH` and `--planning-section STABLE_ID`. The structured operation is `decision.link` through `change apply`; save it separately from other mutations of that decision. Pin observations with `--expected-resolution-id`, `--expected-document-sha256` and, for Markdown input, `--expected-projection-sha256`. Preserve exact values for uncertain-outcome replay.

Anchors require a local native `codesentinel.canonical-document/v1` source or its generated Markdown companion inside explicitly registered project planning roots. GET `/api/v1/projects/{project}/planning-document?locator=PATH` returns readable headings and stable section/block IDs; follow returned cursors with the same locator. Source/projection changes invalidate pagination. The service rechecks bytes before commit. Missing/unavailable anchors reject only link recording, leave the decision unlinked and preserve form work; other project work can continue.

The browser uses a Planning document dropdown, with Add document for bounded folder browsing or pasted paths. Section loads from the selected source and Link waits for a section when anchors are required. GET `/api/v1/projects/{project}/planning-documents` discovers the document pool; `directory=PATH` browses immediate authorized subfolders/documents. Follow cursors with unchanged directory/policy/inventory. The pool is derived from registered roots and earlier planning-link paths, not a separate mutable registry. Selection neither uploads/moves files nor expands permission. Canonical JSON is listed; a generated Markdown companion can be selected by pasting its path. No additional CLI root is needed.

`project policy show` reads the policy. Only owner-local CLI `project policy set` can register roots or change `--anchor-required true/false`, with expected policy revision, request ID and reason. No browser/HTTP policy write exists. Existing agent credentials do not grant this owner administration permission. Do not loosen the requirement to bypass a failure without the user's explicit intent. Optional policy permits omission, recorded honestly as `omitted`; supplied invalid anchors still fail. Imports preserve policy history without granting local file access.

Schema 3 is required for planning-link writes. `data upgrade-check/upgrade` extend the existing backup/restore-checked flow; schema 1 first advances to 2, then 2 to 3 under a new request ID. Existing ledgers do not upgrade silently, and unrelated live-ledger upgrades require their own authorized scope. Receipts retain actor/time, closure/approval, transaction/request, document version/hash, section content digest and policy. `generator_verification: not_checked` means no canonical generator verification ran; a matching Markdown source marker is narrower evidence.

Humans use the Planning document/Section/Link form or plain CLI flags; never ask them to compose JSON. Generator workflows may prefill a decision link with URL-encoded `planning-document`, `planning-section` and optional observed-file `planning-sha256` fragment fields. The selected project/decision must match, the service reloads sections, and Link remains explicit. Do not invent MCP tools, a new top-level CLI group, automatic generator execution or automatic planning incorporation.

New work uses `decision link`, `decision planning-links`, structured `decision.link` and GET `.../{key}/planning-links`; discovery capability is `planning_links_v1`. Earlier `decision apply`, `decision applications`, `decision.apply` and `/applications` remain compatibility aliases. Retry uncertain outcomes with their original operation name and identical body; never rename an in-flight request. Generic `change apply` remains unchanged. Old detail/list/result keys remain compatibility views. Native schema-3 table/export keys and `decision-tracker.application/v1` receipts stay unchanged; do not rewrite historical records or hashes. After new `decision.link` writes, use a compatible current binary; older binaries may reject that operation even at schema 3.

With owner-authorized optional anchors, blank input records incorporation as `omitted` and displays `recorded`; `planning_link.recorded` is true and `linked` is false. A supplied invalid anchor still fails. Do not describe an omitted-anchor record as a planning link. Reopen clears current-cycle status and retains its receipt. Linking records incorporation already completed; it does not edit planning or run the generator.

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
