# API and CLI contract

[Documentation](README.md) · [Home](../README.md)

Run command examples from the repository root after activating its environment:

```powershell
.\.venv\Scripts\Activate.ps1
```

The application service is the sole ledger writer. Default origin is http://127.0.0.1:8765. API clients authenticate with a separate agent bearer credential supplied externally or selected from the protected deployment bundle. Browser sessions use HttpOnly, SameSite=Strict cookies and same-origin CSRF tokens. Authorization derives from the configured principal; client attribution never grants rights.

## Discover and bind

```powershell
decision-tracker project list --json
decision-tracker project show --project example --bind .local/example-binding.json --json
decision-tracker decision list --project example --binding .local/example-binding.json --json
```

A binding contains project ID and ledger UUID only. Commands never infer project identity from cwd. `project show` is explicit discovery; project reads/writes otherwise require the expected UUID. Rebinding is an explicit operator action, never an automatic retry.

## Changes

CLI convenience commands require `--expected-revision`, `--request-id` (UUID), `--reason` and every affected existing decision revision. Use `--record-revision` for the selected decision and `--expected-decision-revisions FILE` for multiple endpoints. Lifecycle authority uses repeated `--authority-ref` arguments. Complex option/reference/evidence fields use an input JSON object.

For batches use `change apply --input FILE --project example --binding .local/example-binding.json --json`. The input is a complete envelope:

```json
{
  "expected_ledger_uuid": "REPLACE_WITH_DISCOVERED_UUID",
  "expected_revision": 0,
  "expected_decision_revisions": {},
  "request_id": "REPLACE_WITH_NEW_REQUEST_UUID",
  "reason": "Record the storage question",
  "authority_refs": [],
  "operations": [
    {
      "op": "decision.create",
      "client_ref": "storage",
      "data": {"title": "Storage", "question": "Which storage engine?"}
    }
  ]
}
```

These uppercase placeholders deliberately fail validation until replaced. Later operations in the same batch can address `@storage`. Limit25 operations/touched decisions. `--dry-run` validates a change and rolls back; it is not a reservation. Do not use dry-run to imply a project or maintenance operation was simulated.

Retry an uncertain write with the identical body and request ID. A committed matching request returns its original outcome before checking stale revisions. Changed content under an old request ID is rejected. On409 reload, reconcile explicitly, and use a new request ID. Do not auto-overwrite a conflict.

## Command families

| Family | Actions |
|---|---|
| service | serve, status, catalog-backup, ensure-running, open, install-launcher, uninstall-launcher, configure-credentials, stop |
| auth | setup-code, recover, reset-password, migrate; token create, rotate, revoke, list |
| project | list, show, create, register, disable, enable; policy show, set |
| decision | list, get, create, edit, edit-resolution, close, reopen, lock, amend, deprecate, defer, resume, challenge, resolve-challenge, set-work, history, as-of, field, apply, applications |
| option | list, add, edit, retire |
| reference | list, add, edit, retire |
| link | list, add, unlink |
| query | search, context, impact, deprecated |
| change | apply |
| data | export, import-validate, import-new, candidates, prepare-candidate, backup, verify, restore-check, artifact-list, artifact-download, upgrade-check, upgrade |

Selecting an option belongs to `decision close`, using `selected_option` in input or `--selected-option`. Selection changes require decide authority. Reopen clears selection. Rejected options need reason and authority. Protected and deprecated aggregates reject ordinary editing.

Project create/register use expected catalog revision and request ID. Register accepts a contained relative ledger path; duplicate enabled UUID/path is rejected. Disable/enable preserve history and identity. There is no remove/repoint operation.

## API mapping

| Method / route | Purpose |
|---|---|
| GET /api/v1/status | Non-sensitive readiness |
| POST, GET, DELETE /api/v1/session | Browser sign in, inspect, sign out |
| GET /api/v1/schema | Authenticated OpenAPI |
| GET, POST /api/v1/projects | List / create or register |
| GET /api/v1/projects/{project} | Explicit identity discovery |
| POST /api/v1/projects/{project}/state | Enable / disable |
| POST /api/v1/projects/{project}/changes | Atomic typed batch, or validate_only |
| GET /api/v1/projects/{project}/decisions | Search/filter/page |
| GET /api/v1/projects/{project}/decisions/{key} | Detail with collection/text descriptors |
| GET .../{key}/history, /as-of, /fields/{field} | History and bounded historical retrieval |
| GET .../{key}/options, /references, /links | Paginated child collections |
| GET .../{key}/context, /impact | Direct neighborhood / bounded dependents |
| POST /api/v1/projects/{project}/exports, /backups, /verify, /restore-check | Maintenance |
| GET /api/v1/projects/{project}/artifacts | Artifact metadata |
| GET .../artifacts/{id}/content | Verified artifact download |
| POST /api/v1/imports/validate, /new | Validate native candidate / retain registerable candidate |
| POST /api/v1/catalog/backups | Separate catalog backup |
| GET /api/v1/projects/{project}/policy | Inspect application policy; no HTTP write route |
| GET /api/v1/projects/{project}/planning-document?locator=PATH | Bounded canonical section choices; follow returned cursors |
| GET .../{key}/applications | Paginated immutable planning application receipts |

Project-bound routes require `X-Ledger-UUID`; changes also require matching `expected_ledger_uuid`. API JSON is UTF-8. Unknown model fields are rejected. Optional authority is evidence text, not proof of external approval.

## Planning application

An open record displays only `open`. A closed record displays `closed` and **Apply**. The small form contains **Planning document**, **Section** and **Apply**; it constructs the API input from these fields. Success replaces the button with a noninteractive `applied` tag. Reopen clears current application state; reclosure requires a new application even when the answer is unchanged. Earlier receipts remain in History and `decision applications`. Deprecated records have no Apply action. Protected closed baselines can append application evidence without changing their approved content.

Use a local native `codesentinel.canonical-document/v1` JSON document or its generated Markdown companion within this project's registered planning roots. Readable headings select stable section/block IDs. No arbitrary URL fetch or filesystem browsing is provided. Missing sections report **Section not found in this document.** Unavailable files report **Cannot access this document.** These failures preserve the form and leave the decision unapplied; other work can continue. If the observed document bytes change, review the refreshed section choices and retry. A stale Markdown source marker requires regenerating that companion.

```powershell
decision-tracker project policy show --project PROJECT --binding BINDING --credential-principal agents --json
decision-tracker decision apply --project PROJECT --binding BINDING --credential-principal agents --key KEY --expected-revision REVISION --record-revision RECORD_REVISION --expected-policy-revision POLICY_REVISION --planning-document C:/Project/planning/plan.json --planning-section SECTION_ID --request-id UUID --reason "Incorporated approved resolution into planning" --json
decision-tracker decision applications --project PROJECT --binding BINDING --credential-principal agents --key KEY --json
```

Replace uppercase placeholders with read values. `decision apply` needs write access and schema 3. `change apply` accepts the same `decision.apply` operation. Required operation data: `expected_policy_revision`; anchor fields: `planning_document` and `planning_section`. Optional `expected_resolution_id`, `expected_document_sha256` and `expected_projection_sha256` pin prior observations. Ledger and record preconditions remain mandatory. Save Apply separately from any other mutation of that decision. The browser pins resolution and observed hashes automatically; CLI flags can do the same. Retry uncertain outcomes with exactly the original values and request ID.

Anchor requirement defaults to true. Only owner-local `project policy set` can change it or register planning roots; see [operations](operations.md#planning-application-policy). If disabled, a blank anchor records `omitted`; a supplied invalid anchor still fails. Policy conflicts require review rather than silently accepting a different requirement.

Receipts identify the closure/approval, transaction/request, actor and recording time, policy, planning document/version/file hash and selected section content digest. `planning_application` on detail and `applied` on list expose current status. Application attests incorporation into one designated planning section. Anchor/hash checks do not prove semantic incorporation, implementation or acceptance. `generator_verification: not_checked` is explicit: Apply does not run the canonical generator or claim a Doctor/render-check result. A Markdown source-marker match is recorded with its projection bytes; it is not full generator verification.

A generator workflow can prefill the form through the decision URL's fragment: `#project=PROJECT&decision=KEY&planning-document=ENCODED_PATH&planning-section=SECTION_ID&planning-sha256=FILE_SHA256`. Values must be URL encoded. The project/decision must match, choices are reloaded through the service, and the user still presses Apply. A stale supplied hash is surfaced for review. No application is recorded by opening the link.

## Bounds and output

500 decisions per ledger; aggregate128KiB;50 alternatives;100 references;100 active outbound links. List default50/max200. JSON response budget64KiB; large detail fields carry chunk URLs pinned to revision. Follow collection cursors until complete. Cursors reject when the ledger revision changes. Field offsets are UTF-8 byte boundaries. Impact traversal is depth3/node200 and explicitly flags truncation; consult paginated links for complete direct relations.

Mutation body1MiB; native import/export10MiB; artifact download20MiB. Stored history grows with activity, so exports can reach the interchange bound before the decision capacity; archive/scale work requires a later tested contract.

`--json` prints one JSON result envelope to stdout. Usage errors go to stderr. Exit codes:0 success,2 invalid input,3 revision/identity conflict,4 authentication/permission,5 availability/retry,1 unexpected failure. Human mode gives status/reason/recovery guidance. Do not log credential values.

## Revision notifications

GET `/api/v1/projects/{id}/events?decision_key=D000001` streams SSE latest-state messages with existing authentication and mandatory `X-Ledger-UUID`. Omit decision_key for project-only awareness. This route uses `text/event-stream` rather than the JSON envelope after connection; pre-stream failures retain JSON errors. Consumers must reconcile the initial snapshot after every reconnect; event IDs do not promise durable replay. See [live-updates.md](live-updates.md) for bounds and browser behavior.

## Password and local administration interfaces

Human routes: GET/POST `/api/v1/session/setup`, POST `/api/v1/session`, GET `/api/v1/account`, POST `/api/v1/account/password`, POST `/api/v1/account/sessions/revoke-others`. Setup/login require preauthentication cookie and CSRF; account mutations require a human session, same-origin CSRF and current password. Setup/change return 204. No HTTP recovery route exists. Agent tokens cannot create human sessions.

Draft routes: POST `/api/v1/service/draft-leases`, PUT/DELETE `/api/v1/service/draft-leases/{uuid}`; browser session and project identity required. GET `/api/v1/service/lifecycle` and POST `/api/v1/service/stop` require deployment-wide maintain scope. Safe stop returns 202 or busy409. Managed readiness is an unauthenticated nonce/HMAC challenge with no data access.

Local credential operations are an OS-owner administrative exception, not ledger access. See Operations for private terminal prompts. Select `--deployment FILE` when using a nondefault deployment. `--credential-principal NAME` and `--token-env NAME` are mutually exclusive. Start explicitly with `service ensure-running`; data commands do not silently launch or replay writes.

## Decision approval events (schema 2)

The **Decide** form shows proposed solutions, then Decision and Why this choice. Selecting a proposal fills those fields and the optional change note. Switching to another proposal replaces all three fields; choosing Write a different answer clears the answer and explanation and resets the change note. There is no draft cache per choice or extra confirmation prompt. Editing the answer switches to a written answer while retaining the text being edited; editing the explanation keeps the proposal selected. Approval details are independent of these choices. Save closes the question; it does not perform implementation work.

`decision.close` accepts `data.approval`. Current approval is `{"mode":"authenticated_now"}` and requires a password-authenticated human session plus decide permission. Recorder identity and UTC recording time come from the server. Agent bearer credentials and legacy token sessions cannot use this mode.

For an earlier or external approval, use:

```json
{"mode":"reported","approver":"Project owner","sources":["Meeting note dated 2020-01-02"],"precision":"date","occurred_date":"2020-01-02","utc_offset_minutes":-300}
```

Reported approval requires decide permission, who approved, and 1–32 nonblank sources. Exact precision requires an offset-aware `occurred_at` plus matching `utc_offset_minutes`; date precision requires `occurred_date` plus offset; unknown precision forbids date/time/offset/timezone. Future occurrence is rejected. The reported approver is not authenticated. A generated event reference is stored in addition to submitted sources, so snapshots allow 33 references while caller `authority_refs` remains bounded at 32.

Selecting a proposal on the structured path requires its `selected_option` ID and `expected_option_revision`. The answer must match the proposal description (or title when description is empty). A resolution edit can preserve an unchanged legacy mismatch. Other changes to the same decision cannot share a resolution batch. Structured approval cannot be combined with top-level `occurred_at`. Legacy explicit-reference requests remain supported without invented approval dates.

Approval events count with the decision toward the 128 KiB aggregate limit. Events are immutable and linked across resolution edits and reopen/close cycles. Detail/as-of returns `latest_resolution_approval`; GET `.../decisions/{key}/approvals` returns paginated summaries, and GET `.../approvals/{event_id}` returns the full event with revision-pinned chunks for long text. Existing project identity and read permission requirements apply. GET `/api/v1/schema` advertises `approval_events_v1` and ledger schemas 1 and 2.

CLI `decision close` and `change apply` forward this object through existing JSON inputs. Bearer agents must report genuine external approval evidence and possess decide permission; this feature grants no new access.

The browser retains the exact request after an uncertain response, retries it once, then offers Retry original save. Each changes request is bounded at 15 seconds. Definitive rejection permits correction with a new request ID. A failed refresh after a successful save is reported as a saved decision.

---

<p align="center">Maintained by Polymath Global</p>

## Prepared projects and administration

Projects & data has one project table and compact New project / Add existing dialogs. Name generates an editable ID. Project selection keeps this page open; Results and the horizontal Decisions menu return to decision work. Disabled selections show their state without exposing stale actions. Project controls occupy the side pane on this page. Both control panes use translucent buttons over the faint Polymath watermark.

Backups and Exports open separate bounded managers. Select one file, then use the shared Download/Check buttons (Check is backup-only). Created dates and times occupy separate unbroken lines. Rows offers 10/25/50/100, default 25, saved as a browser layout preference. Previous/Next replaces the page; page/size/refresh clears selection. Verify replaces one readable project summary. Check validates an isolated copy and does not restore active data. A lost export/backup response is an unknown outcome, not permission for an automatic duplicate operation.

`GET /api/v1/candidates` and CLI `data candidates` list prepared, unregistered imported ledgers. Both maintain and registry permissions are required. Cursor pagination defaults to 50 and permits up to 200 entries. Changed inventory/catalog state invalidates the cursor.

`POST /api/v1/candidates/{candidate_id}/prepare` with `{}` and CLI `data prepare-candidate --candidate-id UUID` explicitly validate a retained candidate and atomically publish its preparation receipt. The same permissions apply. Repeated preparation of unchanged content returns the same receipt. Changed content requires preparation again. `import-new` writes a receipt after validation; `import-validate` does not. Imported copies of already registered identities remain retained but are excluded from selection, even when that registration is disabled.

Registration accepts `candidate_id` and `expected_candidate_digest` together instead of `relative_path`. The service resolves the contained candidate and revalidates its receipt, history, identity and digest before catalog mutation. The legacy contained-path CLI/API contract remains supported. CLI `project register` accepts `--candidate-id` and `--expected-candidate-digest`. Existing request-ID replay and catalog revision preconditions still apply. No ledger schema migration is introduced; schema-1 projects require their separate upgrade before writing decisions.

## Artifact manager pagination

GET `/api/v1/projects/{project_id}/artifacts?kind=backup&order=newest&limit=25` lists one kind, ordered by creation date then ID descending. CLI `data artifact-list --kind backup --order newest --limit 25` uses the same API. Manager envelopes add `previous_cursor`, `total_count`, `page_index`, `page_count`, and `inventory_sha256`. Cursors bind project identity, ledger revision, kind, order, limit and public inventory; changed files return `CURSOR_STALE`. Response-byte limits may yield fewer rows than the selected maximum. Legacy calls without these fields retain mixed forward pagination. No database migration is required.

## Closed-record mutation policy

Closed records reject ordinary content and work-state changes in the browser, CLI and API, including dry runs. Reopen must commit in a separate request before editing; then Close with current approval. Both endpoints of ordinary relationship changes must be open and unlocked. Protected baselines require Amend. Reopen, Protect, Amend and Deprecate retain their existing state, authority and evidence requirements. Inspection and historical snapshots remain available.

`decision edit-resolution` remains recognized for compatibility but is withdrawn for new writes (`INVALID_TRANSITION`, HTTP 422). Reopen, use `decision edit` on the open record, then Close. Exact historical committed requests still replay their original receipt after permission and payload checks; no history is rewritten. Reusing a request ID with different content still fails.

A batch cannot reopen and mutate or reclose the same closed-at-start decision. Retain a stale browser draft after remote closure; review current state and obtain authorized reopening instead of automatically advancing revisions. Disabled pane controls keep the fixed grid. Outside the pane, unavailable child mutation controls are hidden; Protect/Amend is beside Approval and Decide/Reopen stays beside Question. The browser action is labeled Decide; the CLI command remains `decision close`, the API operation remains `decision.close`, and the resolved status remains `closed`.
