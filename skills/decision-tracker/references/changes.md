## Prepare and apply a change

Read the current ledger and every affected decision revision before preparing a write. Retain the exact intended payload and a fresh UUID request ID in ignored local custody until the outcome is known. For linked changes, include both endpoints. Never derive a decision's revision from the ledger revision.

For atomic batches, use `change apply --input FILE --project example --binding .local/example-binding.json --token-env DT_AGENT_TOKEN --json`. The input is a complete envelope with:

- `expected_ledger_uuid`: the bound UUID.
- `expected_revision`: the read ledger revision.
- `expected_decision_revisions`: a map from each affected existing decision key to its read revision; empty for creating an independent decision.
- `request_id`: a new UUID; `reason`: the actual reason; `authority_refs`: genuine supporting references, not invented approval.
- `operations`: up to 25 operations, for example `{"op":"decision.create","data":{"title":"Storage","question":"Which storage engine?"}}`.

`--dry-run` validates and rolls back a decision change. It is not a reservation or a dry run for project/maintenance operations. `validate_only` is excluded from the stored intent hash, and a fresh validation rolls back without recording a committed receipt. The same intent/request ID may subsequently commit; validation does not reserve revisions. If that ID already committed, matching requests return its receipt before validation and stale-revision checks. A deliberately revised intent requires a new ID; uncertain committed outcomes require exact replay. Convenience mutations also require `--expected-revision`, `--record-revision` for the selected record, `--request-id`, and `--reason`; their `--input` contains operation data, not the complete envelope. Multi-record commands use `--expected-decision-revisions FILE`.

After success, inspect the returned committed outcome and explicitly read back relevant state. Testing or implementation completion does not authorize closing a decision. Closure, locking, amendment, deprecation, rejected options and resolution changes require the appropriate user intent and service capability. Protected approved content requires amendment; permitted supporting context uses the narrow closed-record allowlist below. There is no hard-delete or silent overwrite.

## Closed-record mutation policy

Closed and protected closed decisions accept supporting context through `reference.add`, `link.add`, `link.unlink` and `decision.set-evidence`, with existing write permission (or authorized propose-only dry run). Deprecated decisions reject these operations. Approved content, approval events, baseline, selected options and planning receipts remain unchanged. Reopen/Amend remains necessary for substantive edits, options and work/challenge state.

Both ordinary relationship endpoints may be active open or closed, including protected closed. Supply both current record revisions. Either endpoint may unlink a `relates_to` edge; only the source may unlink `depends_on`. Lifecycle links remain transition-owned. Closed references are append-only: correction means appending a source and explaining the earlier reference in the change reason. Closed reference edit/retire stays unavailable.

`decision set-evidence --input FILE` accepts operation data such as `{"evidence_state":{"verification":{"status":"Focused checks passed","evidence_refs":["retained proof receipt"],"responsible_role":"maintainer"}}}`. The structured operation is `decision.set-evidence`. Only implementation, verification and acceptance slots are allowed. Omitted slots stay unchanged; explicit null clears a slot with previous values retained in history. Supply a nonempty patch and nonblank status/sources/role when present, plus the usual UUID, revisions, request ID and reason. Reported evidence never grants approval or proves acceptance.

`decision edit-resolution` remains withdrawn for new writes. Reopen, edit the open decision, then Close with current approval. Exact historical committed requests still replay their original receipts after permission and payload checks; no history is rewritten. Reopening must commit separately.

A batch cannot reopen and mutate or reclose the same closed-at-start decision.

Reopen, Protect, Amend and Deprecate retain their existing state, authority and evidence requirements. Inspection and historical snapshots remain available.


## Direct API changes

For direct API changes, use matching `expected_ledger_uuid` in changes. Submit batches to
`POST /api/v1/projects/{project}/changes`; set `validate_only` for validation. Authentication
and project-route identity follow api-access.md. Validation, mutation authority, current
revision guards and exact replay follow the change/recovery rules in this reference and
recovery.md; validate_only is not permission, a reservation or a read-only GET.
