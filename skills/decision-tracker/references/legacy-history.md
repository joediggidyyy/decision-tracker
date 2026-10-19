# Immutable source history

For read-only history, use api-access.md and the authenticated schema's advertised legacy
contract and returned routes. CLI examples below identify equivalent owner operations only
where CLI use is authorized. Import, restore-check or registration requires its own scope;
load maintenance.md and recovery.md before that work. No runtime import is authorized here.

## Immutable legacy decision history

Discovery advertises `legacy_history_v1` and `inactive_candidate_recovery_v1` when implemented. Use the packaged contract returned by authenticated `/api/v1/schema?contract=legacy-import-v1`, with its advertised SHA256. Legacy origins do not fabricate historical approval: unknowns, source benefit/summary attribution, versions, events, relations and reference-only anchors remain distinct from native decisions, approvals and planning-link receipts. Native history and source history must both be read when relevant.

Use existing `decision get --source-namespace NAMESPACE --source-id SOURCE_ID` without `--key` for qualified identity/alias lookup. `decision history --key KEY --origin legacy` and `query context --origin legacy` return complete paginated source members; context without a key includes unassociated project context. Use `--relations` for source relations, or `--legacy-kind` with identities, versions, appearances, payloads, members, associations, relations, projections, source_anchors or absences for exact descriptor collections. Supply the explicit project and expected ledger UUID/binding; keep query/limit fixed while following cursors. Restart pagination if the revision changes.

Use `decision as-of --origin legacy --source-version VERSION_ID --key KEY` for source-version presence and member/absence pointers. `decision field --origin legacy --payload SHA256 --key KEY` and `data export --origin legacy --payload SHA256` return base64 byte chunks with offset/limit, total encoded length and hash. Follow next_offset to null, recombine bytes, verify length/SHA256 and decode UTF-8 before interpreting E1. Payload metadata is available through `--legacy-kind payloads`; complete bytes use the chunk route. Read-only browser Source history/references show original content separately from native History.

Import-new/validate remain existing data operations; never improvise a legacy JSON shape. Bind the reviewed target UUID, contract hash and source manifest; preserve the exact request file and ID for retry. Validation-only is not publication. Inactive `data export/backup/verify/restore-check` require `--candidate-id` and `--expected-candidate-digest`; restore-check also needs the backup artifact ID. Download through `data artifact-download` with the same binding. No registration, overwrite, source conversion or execution release is implied. Source-specific migration approval and independent mapping/size qualification still control.

Imported sparse exceptions are immutable and field-specific. Untouched source unknowns can survive permitted operations; edits, new Close and amendment children use current native validation. Reopen still commits separately; protected records require Amend. Origin association is navigation, not approval. Reference-only source anchors are not planning-link attestations. Schema 4 is initialized for new legacy candidates; no automatic schema-3-to-4 upgrade exists. Existing formats, command roots and historical request aliases remain supported.
