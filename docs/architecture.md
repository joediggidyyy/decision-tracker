# Architecture

[Documentation](README.md) · [Home](../README.md)

Decision Tracker is an independently served, loopback-only application with a Polymath-congruent browser shell. It is usable by any project; organization-specific lifecycle policy is not embedded in its domain logic.

The central SQLite catalog maps explicit project IDs to contained ledgers and expected UUIDs. Each project ledger stores decisions, alternatives, references, directed relations, immutable transactions/snapshots, artifact metadata and import receipts. Browser/API/CLI operations converge on one shared service and state transition engine.

A conservative in-process coordinator serializes registry and ledger operations through transaction commit. This meets the bounded single-user service model and prevents disable/write races. SQLite BEGIN IMMEDIATE, full synchronization, foreign keys and revisions provide durable write boundaries. No cross-project transaction exists.

The UI uses external static assets, semantic controls, a full-width decision detail, Focus view, and a right panel with context above results. Both panel boundaries support dragging and keyboard resizing, with nonsecret local layout preferences. At 980 CSS pixels or narrower, the context/results panel stacks and stays visible, with one page scroll surface and no collapse toggle. Selecting a result leaves the panel visible. Desktop scrollbars appear only while interacting with overflowing regions. It never imports the business workspace folder index. Credentials, source records and application hosting stay independent of the home page.

Transactions retain canonical intent and its hash alongside committed outcomes. Revisions retain complete affected aggregates. Protected amendment records an incident relationship in parent history while preserving baseline content. Selected alternatives can change only through explicit resolution operations.

Native export/import retains history exactly. Backup and restore checks operate on bounded contained candidates; no maintenance endpoint overwrites an active ledger. Request scope, expected identity and versions remain mandatory.

The detailed approved business execution contract remains in Polymath planning custody. This implementation record describes actual technical boundaries. The portable agent-access skill is included; MCP remains a follow-up. Both agent and browser use the shared API.

Managed Windows deployments use an open-only URI handler, nonce/HMAC readiness, owner-local administration, DPAPI and a separate auth.sqlite. Human password sessions and agent bearer credentials have independent lifecycles. Idle admission and draft leases share a mutex; polling and notifications cannot keep a managed service alive. Foreground operation remains available with idle shutdown disabled.

---

<p align="center">Maintained by Polymath Global</p>
