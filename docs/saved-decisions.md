# Saved decisions and optional groups

[Documentation](README.md) · [Interfaces](interfaces.md) · [Operations](operations.md)

Open **Library** after signing in. It is a standalone page in the application shell, alongside **Decisions** and **Projects**. A new installation has no saved decisions or groups. Library works before you create a project. Its destination selector is in staging; the shared selector on Decisions and Projects does not govern Library. Application packages contain no saved seed set. Transfer user content separately through export/import or checked backups.

Library starts in **Groups**. The single unboxed **Groups | Decisions** button switches the list and greys out the inactive label. The main column heading shows a plain integer count of displayed groups or decisions after search; opening group members does not change the group count. Staging retains its X staged label for copied decisions. Each mode keeps its own search text in this tab. Group search matches names; Decisions search matches titles and complete questions as literal text. Open one group at a time to reveal its decisions in place. Open a decision to read its complete question, answer, rationale, proposals, group tags and sources beneath its row. Only one source detail is open. Tags stay inside details. **Ungrouped** appears when needed as a browsing convenience, without creating a saved tag.

Use the flat **+** beside a row to add its copy to staging and **−** to remove it. A group adds missing members without replacing existing copies. Removing a group removes its currently staged members. Overlap is deduplicated by saved identity; all counts update together. Partly staged groups show both actions. Group search does not change a group's staging scope. Staging preserves existing order and appends missing members in displayed title/identity order.

Staging is visible beside the list on wide layouts. At 960px of available Library width or less, it comes before the list. The separate Browse/Staging navigation buttons are removed. Each staged copy expands in place, independently of source details. **Undo** and **Redo** reverse local staging changes, including a whole group command, with the exact copied content and order. They never change saved or project records. A new staging change clears redo; search, view changes and Library edits do not. History is bounded to 100 commands and 32MiB; evicting old commands leaves active copies intact. Staging and history remain during app navigation and Back/Forward in the tab, and end when the tab closes.

1. Choose **New decision**. The shared form preserves drafts and uses the same title, question, owner and optional fields as ordinary creation. Optional groups, proposals and references are available separately.
2. Use **Settings → Manage groups** to create or manage optional tags. Edit a decision to change its tags through the standard multiple-selection field.
3. Use **+** beside groups or decisions. Staging copies source content at the captured Library revision. A failed or conflicting read leaves staging and history untouched; refresh and repeat the action explicitly.
4. Expand staged copies to review them. Later source edits or deletion leave those copies intact. To update a copy deliberately, expand its source and use **Replace staged copy**. Replacement is undoable.
5. Choose or create a destination and **Publish**. This records current browser operator approval and creates next-numbered **closed and protected** decisions. Answers and rationale are required. Successful publication clears staging and its local history.

Settings shows only Manage groups and Transfer & backup in a compact in-place menu. Each option opens its own focused action dialog. Selection, Escape or click-away dismisses the menu; it has no Close button. Editing and group management use flat action dialogs. Management and transfer controls never expand the page heading or shift the browsing workspace. Account & access uses the single primary key control; Settings and creation/edit forms have no duplicates. Reading has no extra pane or popup. Cancelling a changed form offers Save, Discard or Keep editing. An unresolved save or publication retains its exact retry and prevents departure. Unknown or partial publication freezes staging/history changes. After a definitive partial failure, **Keep remaining items for review** starts a new history boundary and never recreates committed project records. Old browser-local group category preferences are inactive and do not affect native tags or exports.

Publication creates the project's next available D numbers, then records approval and protection through existing operations. Each finished decision has a publication baseline assigned automatically. Protected content follows the existing amendment workflow. Proposals start unselected. References do not acquire verified evidence status. Approval receipts, planning links and implementation evidence are not copied.

You may publish the same content again. Contradictory answers are also allowed. The operator and agent interpret the decisions. Group tags and saved identities stop at staging: project records have no group behavior or connection back to the saved item. Later edits, tag changes or deletion of a saved item leave earlier project copies unchanged. Existing project editing, closing and deprecation remain available.

## Permissions and limits

Saved reads, selection and export require `read`; publication preparation requires `read`, `write` and `decide`. Saved content, tags and import require `write`. Saved backups and their checks/downloads require `maintain`. Creating a destination project uses the existing `registry` capability. Publication requires the existing project's `write` and `decide` permissions and explicit project ID/ledger UUID. This feature adds no owner role or extra approval step.

The existing creation limits remain 25 operations per request and 500 decisions per project. Each saved decision, including its proposals/references, must fit one creation request. A larger staged set uses several ordinary requests; completed batches stay committed if a later batch fails. The browser reports progress and retains the remaining content for review. It does not promise a transaction across several requests.

Saved storage holds at most 5,000 decisions, 500 group tags and a self-contained content bundle of 10MiB. Staging holds at most 500 items and must fit the 10MiB preparation envelope; oversized group actions are rejected atomically. A selection stages at most 500 items; individual saved records must fit the existing single-record response budget. These are storage/transport bounds, not judgments about decision meaning.

## CLI and API

All saved commands are under the existing `data` group. Use your configured agent credential (`--credential-principal NAME` or `--token-env NAME`), as for other commands. Names below are examples, not installation defaults.

```text
decision-tracker data saved-list --json
decision-tracker data saved-create --title "Launch behavior" --question "How should this application launch?" --answer "Start locally" --expected-revision 0 --request-id UUID --reason "Save reusable drafting content" --json
decision-tracker data saved-group-create --name Websites --expected-revision 1 --request-id UUID --reason "Create an optional tag" --json
decision-tracker data saved-edit --id SAVED_UUID --group-id GROUP_UUID --expected-revision 2 --request-id UUID --reason "Tag this saved decision" --json
decision-tracker data saved-stage --group-id GROUP_UUID --saved-id SAVED_UUID --expected-revision 3 --output stage.json --json
```

Replace UUID placeholders with fresh request IDs or IDs returned by the service. `saved-list` returns saved revision, item summaries, group summaries and `next_offset`. Each item includes complete bounded `question` (at most 8,192 characters), plus compatible `question_preview` (at most 240 literal source characters) and `question_truncated`. Pages shrink to retain the 60,000-byte response bound. Follow pages with the same `--expected-revision`. `saved-get --id UUID` reads full content. `saved-edit` changes supplied content fields and retains others. Tag-only edits preserve content. A structured `group_ids: []` clears tags. `saved-delete`, `saved-group-edit` and `saved-group-delete` require the target `--id`, saved revision, request ID and reason. Deleting a group removes its tags from saved items; it never touches project records.

The stage file contains `data` entries with `id` and `content`. For agent publication, add an ordinary `approval` object describing genuine reported operator approval to the preparation input: `mode: reported`, `approver`, `sources`, and `precision` (plus date fields when known). Do not invent approval or use authenticated_now with an agent credential. Agents can add/drop entries before preparing. Browser users use the staging controls without composing JSON. For CLI publication, explicitly discover/create the destination through the existing project commands, then prepare and retain its requests:

```text
decision-tracker data saved-prepare --input stage.json --output publication.json --project example --ledger-uuid LEDGER_UUID --expected-revision PROJECT_REVISION --request-id UUID --reason "Publish selected saved decisions" --json
decision-tracker data saved-publish --input publication.json --project example --ledger-uuid LEDGER_UUID --json
```

Preparation creates an exclusive new `decision-tracker.saved-publication/v2` file before any project write. `saved-publish` checkpoints exact requests, returned keys/revisions, approval, and receipts through create, close and protect phases. Missing answer/rationale, destination permissions and approval are checked before creation. Protect uses the actual committed approval references. Interrupted publication may leave open or closed/unprotected records; report that state and retain the preparation. Completion is reported only after protection finishes. Retry the same file after an unknown outcome; already committed requests replay. A deliberate second publication needs a new preparation/request ID and the current project revision. For a definitive stale revision, retain receipts and review current project records before continuing. Do not recreate already injected records. Older creation-only preparations retain exact historical replay and report `legacy-create-only`; they are not silently converted or reported as closed/protected publication. Never renumber or alter an uncertain request. Generic `change apply` also accepts each prepared request.

The shared API exposes:

| Endpoint | Purpose |
|---|---|
| `GET /api/v1/saved-decisions` | Revision-bound item/group summary pages (`offset`, `limit`, `expected_revision`), including saved group tag IDs; page size shrinks as needed to retain the response bound. |
| `GET /api/v1/saved-decisions/{id}` | One full saved item and optional tag IDs. |
| `POST /api/v1/saved-decisions/changes` | Revision/request/reason-bound `save`, `delete`, `group-save`, `group-delete`, `import`. |
| `POST /api/v1/saved-decisions/stage` | Expand explicit `decision_ids` and `group_ids` at `expected_revision`, returning copied content once per identity. |
| `POST /api/v1/saved-decisions/prepare` | Preflight staged content, destination and approval; prepare existing create/close/protect requests for the requested phase. |
| `POST /api/v1/saved-decisions/export` | Download the portable saved-content bundle. |
| `POST /api/v1/saved-decisions/import-check` | Validate a portable bundle without changing stored data. |
| `POST /api/v1/saved-decisions/backup` | Create a checked SQLite snapshot, retaining saved change history. |
| `POST /api/v1/saved-decisions/backup-check` | Check the retained snapshot by `artifact_id`; leave live data unchanged. |
| `GET /api/v1/saved-decisions/backups/{id}/content` | Download a retained backup. |

API schema advertises `saved_decisions_v1`. Saved changes have independent revisions and immutable actor/time/request/reason history in `saved-decisions.sqlite`. Project schemas and change contracts are unchanged. HTTP mutation remains authenticated and, for browser sessions, protected by same-origin CSRF.

## Transfer and recovery

The portable `decision-tracker.saved-decisions/v1` JSON bundle contains saved identities, content, groups and their optional tag relationships. It contains no deployment paths, credentials, approvals or project data. Import adds new IDs, accepts identical existing items and rejects conflicting content for an existing ID without overwriting anything. A current revision and explicit import request are still required.

```text
decision-tracker data saved-export --output saved-decisions.json --json
decision-tracker data saved-import-check --input saved-decisions.json --json
decision-tracker data saved-import --input saved-decisions.json --expected-revision 0 --request-id UUID --reason "Import my saved decisions" --json
decision-tracker data saved-backup --json
decision-tracker data saved-backup-check --artifact-id BACKUP_UUID --json
decision-tracker data saved-backup-download --artifact-id BACKUP_UUID --output saved-backup.sqlite --json
```

Export transfers current saved content. The SQLite backup also preserves saved change history and retry receipts. Project exports/backups remain independent; catalog backups cover the catalog. Back up saved content separately as part of a deployment backup.

For manual recovery, stop the service, preserve the damaged `saved-decisions.sqlite`, and restore the previously checked saved backup to that file under the configured data root. Leave project ledgers and credentials alone. Restart, read `saved-list`, and check content with `saved-get`; make any subsequent publication explicit. Do not replace a live database while the service is running. Portable import into an empty administration store is an alternative for current content; it does not recreate the source's local history.

| Fault | Safe next step and verification |
|---|---|
| Saved revision changed | Keep the draft. Review current saved content, choose its current revision explicitly, then save with a new request ID. |
| Unknown save outcome | Keep the original request. Start/reuse the service with its launcher or `service ensure-running`, then retry exactly that request. Check the resulting saved revision or project records. |
| Publication partially committed | Retain completed-batch receipts. Review and publish only remaining items after a definitive failure; replay the original preparation after an unknown outcome. |
| Session expired | Use Account & access to sign in. Drafts and staging remain in tab memory. |
| Import ID conflicts or invalid format | Original content is retained. Review the conflicting IDs/content or obtain a compatible export, then revalidate. |
| Damaged saved storage | Saved operations stop and preserve the file. Existing project work stays available. Restore a checked saved backup and verify after restart. |
| Capacity exceeded | Reduce the staged set or use another project within existing limits; verify completed records before repeating publication. |

Browser drafts and staging remain in tab memory, with navigation warnings and an explicit retry workflow. They are not persisted across tab closure or browser crashes. This feature does not claim general automatic corruption repair or application-wide resilience compliance.
