# Legacy decision imports and recovery

Decision Tracker preserves earlier decision records as immutable source history alongside native decisions. Original identities, literal types and values, ordering, versions, events, relations, absences and references remain retrievable. Source benefit and summary text keep their attribution. Imported history never becomes a fabricated native approval or backdated transaction.

## Contract and data boundaries

The packaged [legacy-import/v1 schema](../src/decision_tracker/schemas/legacy-import-v1.json) is the normative interchange authority. It defines closed rows, requests, response envelopes, native v4 columns and the supported semantic adapters. Authenticated `GET /api/v1/schema` returns discovery metadata and the contract URL/SHA256; `GET /api/v1/schema?contract=legacy-import-v1` returns the contract itself. Its hash pins the reviewed bytes. Keep the source manifest and reviewed target UUID with the request.

E1 retains JSON numeric token spelling, Unicode without normalization, array order, and missing/null/empty distinctions. It rejects duplicate object members, nonfinite numbers and lone surrogates. Payload and projection JSON are retained as E1 strings. Native fields are projections and do not replace original payloads. Version IDs bind namespace, exact slash-normalized locator and file hash; member IDs bind version and selector. The schema supplies the full identity and ordering contracts.

New legacy candidates initialize schema 4. Seeds begin at native decision revision 1 and ledger revision 0; native transactions and approvals start only when new native actions occur. Native v4 export/import preserves all origin tables and seed snapshots. Existing native v1–v3 formats remain supported. Existing live ledgers do not automatically upgrade, and there is no schema-3-to-4 upgrade command.

Import/new and native export each have a 10 MiB encoded-body limit. Normal reads and discovery stay within 64 KiB. Lists accept 1–200 rows and reduce page size to fit. Payload chunks accept 1–16,384 bytes. Follow `next_cursor` until `complete`; follow `next_offset` to null for payloads. Recombine bytes, verify encoded length and SHA256, then decode UTF-8. Source-only payload sizes do not prove a complete migration request or native export fits.

## Reading original history

All project reads require the normal credential, project authorization and expected ledger UUID. Decision payload reads additionally require source association to that decision. Project reads include unassociated dispositions and provenance. Associations provide navigation and do not imply approval.

| Existing CLI operation | Source read |
|---|---|
| `decision get --source-namespace N --source-id ID` | Qualified source identity or alias; omit `--key`. |
| `decision history --key KEY --origin legacy` | Paginated original members. |
| `query context --origin legacy` | Complete project members; add `--key` for a decision. |
| `query context --origin legacy --relations` | Source relations, including nondecision endpoints. |
| `query context --origin legacy --legacy-kind FAMILY` | Complete descriptor collection; optionally filter by `--key`. |
| `decision as-of --key KEY --origin legacy --source-version VERSION` | Original version presence and member/absence pointers. |
| `decision field --key KEY --origin legacy --payload SHA256` | Associated source payload chunks. |
| `data export --origin legacy --payload SHA256` | Project source payload chunks. |

Use the normal project/binding/credential flags. Descriptor families are `identities`, `versions`, `appearances`, `payloads`, `members`, `associations`, `relations`, `projections`, `source_anchors` and `absences`. Payload descriptors exclude bytes; use the chunk route for complete values. Keep filters and limit unchanged across a cursor chain. Revision changes invalidate cursors; restart the read.

The API uses existing project route families:

- `GET /api/v1/projects/{project}/decisions?source_namespace=N&source_id=ID`
- `GET /api/v1/projects/{project}/legacy/members` and `/legacy/relations`
- `GET /api/v1/projects/{project}/legacy/records/{family}`
- `GET /api/v1/projects/{project}/legacy/payloads/{sha256}`
- `GET /api/v1/projects/{project}/decisions/{key}/legacy` and `/legacy/relations`
- `GET /api/v1/projects/{project}/decisions/{key}/legacy/as-of?version_id=VERSION`
- `GET /api/v1/projects/{project}/decisions/{key}/legacy/payload/{sha256}`

The browser’s Source section shows origin identity, unknown/nonprojected fields and source attribution. Source history and Source references are read-only and separate from native History. Reference-only imported anchors do not create planning-link receipts.

## Native actions after import

Only unchanged sparse fields explicitly bound to immutable origin projections receive historical exceptions. Ordinary edits validate changed fields. New Close and amendment children use strict native rules. Permissions, revisions, graph/capacity checks, protected baselines and separate Reopen commits still apply. Source history remains unchanged when native work continues.

## Import intent and inactive recovery

Use existing `data import-validate` or `data import-new` with the reviewed request file. Humans are not asked to compose this interchange JSON; engineering adapters produce and independently qualify it. Validate-only retains isolated scratch evidence without publishing a candidate or reserving an import intent.

Publication durably reserves the principal/request ID, exact body hash, namespace, target UUID and candidate ID before creating the candidate. Retry an uncertain outcome with identical content, request ID and authorized principal. Recovery reconciles interrupted preparation and reuses that candidate. Changed-body and namespace/target identity collisions reject. Registration remains a separate catalog operation with the returned candidate ID and expected digest.

After registration and subsequent native work, exact import replay returns the original historical receipt without resetting the ledger. It is not verification of the ledger's current digest. Use ordinary project verification for current registered data; inactive maintenance rejects registered candidates.

Existing `data export`, `backup`, `verify` and `restore-check` accept `--candidate-id UUID --expected-candidate-digest SHA256` for inactive maintenance. Restore-check also requires the backup `--artifact-id`. It prepares a distinct inactive candidate and verifies the whole logical content without registration or activation. Download via existing `data artifact-download` with the same candidate/digest and artifact ID. Preserve backup bytes, receipts and failed preparation evidence.

The corresponding API uses `POST /api/v1/candidates/{id}/exports`, `/backups`, `/verify` and `/restore-check`, with `expected_candidate_digest` and optional restore `artifact_id`. Download uses `GET /api/v1/candidates/{id}/artifacts/{artifact_id}/content?expected_candidate_digest=SHA256`. Maintain permission and candidate scope apply. These operations do not authorize migration execution or active-ledger replacement.
