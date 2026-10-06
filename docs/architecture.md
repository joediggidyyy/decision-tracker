# Architecture

[Documentation](README.md) · [Home](../README.md)

Decision Tracker is an independently served, loopback-only application with a Polymath-congruent browser shell. It is usable by any project; organization-specific lifecycle policy is not embedded in its domain logic.

The central SQLite catalog maps explicit project IDs to contained ledgers and expected UUIDs. Each project ledger stores decisions, alternatives, references, directed relations, immutable transactions/snapshots, artifact metadata and import receipts. Browser/API/CLI operations converge on one shared service and state transition engine.

A conservative in-process coordinator serializes registry and ledger operations through transaction commit. This meets the bounded single-user service model and prevents disable/write races. SQLite BEGIN IMMEDIATE, full synchronization, foreign keys and revisions provide durable write boundaries. No cross-project transaction exists.

The UI uses external static assets, semantic controls, a full-width decision detail, Focus view, and a right panel with context above results. Both panel boundaries support dragging and keyboard resizing, with nonsecret local layout preferences. At 980 CSS pixels or narrower, the context/results panel stacks and stays visible, with one page scroll surface and no collapse toggle. Selecting a result leaves the panel visible. Desktop scrollbars appear only while interacting with overflowing regions. It never imports the business workspace folder index. Credentials, source records and application hosting stay independent of the home page.

Transactions retain canonical intent and its hash alongside committed outcomes. Revisions retain complete affected aggregates. Protected amendment records an incident relationship in parent history while preserving baseline content. Selected alternatives can change only through explicit resolution operations.

Native export/import retains history exactly. Backup and restore checks operate on bounded contained candidates; no maintenance endpoint overwrites an active ledger. Request scope, expected identity and versions remain mandatory.

Schema 3 adds immutable planning-link receipts and policy events. The current linked indicator is derived from the current closure's identity and its anchored receipt; an owner-authorized omitted anchor displays `recorded`. Neither is an editable decision field. Linking advances the ledger/record revision while preserving decision content and approval. Reopen starts another closure cycle; historical receipts remain intact. Schema 1/2 history stays readable, and explicit backup/restore-checked upgrades introduce each extension.

The owner CLI registers project planning roots and optional-anchor policy through the protected local administration channel. Policy evidence is ledger data, but filesystem permission is a separate names-only binding under the deployment data root. Imported/restored policy cannot authorize file reads by itself. The resolver reads bounded local canonical JSON and optional generated Markdown; it rejects unregistered locations, symbolic links and junctions. Link rechecks observed bytes before commit, without claiming a transaction across SQLite and external editors. No generator or network request runs inside Link.

The detailed approved business execution contract remains in Polymath planning custody. This implementation record describes actual technical boundaries. The portable agent-access skill is included; MCP remains a follow-up. Both agent and browser use the shared API.

Read-only planning document discovery reuses the same deployment-local root binding as anchor resolution. The pool derives from immediate registered-folder sources and retained planning-link paths; no second registry is stored. Add document navigates contained directories. Every inventory request rejects redirections and bounds enumeration/source bytes; cursors bind the complete observed inventory and policy. File selection does not grant new permissions or move data.

Managed Windows deployments use an open-only URI handler, nonce/HMAC readiness, owner-local administration, DPAPI and a separate auth.sqlite. Human password sessions and agent bearer credentials have independent lifecycles. Idle admission and draft leases share a mutex; polling and notifications cannot keep a managed service alive. Foreground operation remains available with idle shutdown disabled.

Public planning-link names are aliases over the existing schema-3 evidence model. Stored table names, native bundle keys and `decision-tracker.application/v1` receipt markers stay stable. Validation accepts both `decision.apply` and `decision.link`; exact retries preserve their original operation name and committed result. API compatibility views retain old status keys alongside the new anchor-aware fields. New operation histories require a compatible current binary; this is not permission to downgrade or rewrite history.

---

<p align="center">Maintained by Polymath Global</p>
