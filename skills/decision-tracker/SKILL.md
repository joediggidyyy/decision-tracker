---
name: decision-tracker
description: Read, propose, record and link project decisions using authenticated API reads and supported authorized operations, including revision conflicts, history and recovery. Use for an existing Decision Tracker service; not generic task tracking or direct SQLite editing.
metadata:
  version: "0.2.0"
  status: "released-for-authorized-use"
---

# Decision Tracker access

Use the application service as sole ledger writer. This skill grants no mutation,
administration, migration, credential or publication authority. Continue within the actual
assignment; prepare a concrete proposal when mutation authority is missing.

Recover the explicitly selected deployment/origin and existing principal. Never infer
identity from cwd, silently rebind, switch to operator credentials, read credential values,
or substitute a default port for a failed selected binding. Ordinary retrieval uses the
authenticated API. CLI-only owner operations and authorized fallbacks remain conditional.

Bind project routes to the intended project and ledger UUID. Follow material collection
cursors and revision-pinned text to completion; restart stale pagination. Capability/schema
discovery proves advertised support, not permission or installed source correspondence.

Preserve exact requests, principal, revisions, failures and unknown outcomes. On uncertainty
read recovery guidance before retrying; do not issue a fresh create or advance preconditions.
Never fabricate approval, dates or planning-link receipts. A recommendation, execution,
hash match or logged proposal is not approval, acceptance or behavioral qualification.

Read only task-matching references and their stated dependencies. Examples preserve the
owner's supported operations; they do not override the assignment's interface restrictions.

| Task | Reference | Read condition |
|---|---|---|
| Read or search current decisions | [api-access.md](references/api-access.md) | Every API retrieval; bind origin, project and ledger UUID, then follow applicable cursors/chunks. |
| Record a consequential question or recommend options | [decisions.md](references/decisions.md) | Before a consequential proposal or decision; includes contested investigation history. |
| Prepare or apply an authorized change | [changes.md](references/changes.md) | Before any mutation; also load recovery.md and approval-planning.md when approval/closure/linking is involved. |
| Read/report approval or incorporate a closure into planning | [approval-planning.md](references/approval-planning.md) | For approval evidence, lifecycle resolution or planning-link work; capability and real authority control. |
| Start/reuse the selected service or handle a lost response/conflict | [recovery.md](references/recovery.md) | For normal selected-deployment startup/reuse or first failure under standing task authority; no fresh per-start approval. Preserve exact identity and bounded recovery, then stop/report essential failure. |
| Use reusable Library content | [library.md](references/library.md) | Only for saved content, staging, transfer or publication; publication also requires changes.md, recovery.md and approval-planning.md. |
| Inspect legacy source history or source bytes | [legacy-history.md](references/legacy-history.md) | Only when imported identities, versions, original bytes or inactive candidates matter; API reads start with api-access.md. |
| Use an authorized CLI equivalent | [cli-fallback.md](references/cli-fallback.md) | Only when the assignment permits CLI access or an actual supported fallback is required; no automatic retry through another route. |
| Administer deployment, upgrades, recovery media or candidates | [maintenance.md](references/maintenance.md) | Only for that explicitly authorized operation; inspect current owner capabilities, and load recovery.md. |
| Operate browser resolution/evidence controls | [browser.md](references/browser.md) | Only for actual browser work; documentation is not installed-runtime or GUI qualification. |
