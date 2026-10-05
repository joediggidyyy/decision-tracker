# API and CLI contract

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
| project | list, show, create, register, disable, enable |
| decision | list, get, create, edit, edit-resolution, close, reopen, lock, amend, deprecate, defer, resume, challenge, resolve-challenge, set-work, history, as-of, field |
| option | list, add, edit, retire |
| reference | list, add, edit, retire |
| link | list, add, unlink |
| query | search, context, impact, deprecated |
| change | apply |
| data | export, import-validate, import-new, backup, verify, restore-check, artifact-list, artifact-download |

Selecting an option belongs to `decision close` or `decision edit-resolution`, using `selected_option` in input or `--selected-option`. Selection changes require decide authority. Reopen clears selection. Rejected options need reason and authority. Protected and deprecated aggregates reject ordinary editing.

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

Project-bound routes require `X-Ledger-UUID`; changes also require matching `expected_ledger_uuid`. API JSON is UTF-8. Unknown model fields are rejected. Optional authority is evidence text, not proof of external approval.

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
