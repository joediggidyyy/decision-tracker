# API reads and explicit identity

Read this for ordinary retrieval. The actual selected runtime supplies authentication;
never inspect or persist its credential values. Use the selected origin, not a guessed
default. Inspect authenticated schema before relying on optional capabilities.

| Read | Supported route | Binding / completeness |
|---|---|---|
| Capability discovery | GET /api/v1/schema | Authenticated OpenAPI document; it is not the ordinary ok/data envelope. |
| Accessible project catalogue | GET /api/v1/projects | Discover only within actual principal visibility. |
| Explicit project identity | GET /api/v1/projects/{project} | Confirm the intended ledger UUID; do not silently rebind. |
| Search/list decisions | GET /api/v1/projects/{project}/decisions?q=TERM | X-Ledger-UUID; preserve filters and follow returned cursors. |
| Decision detail | GET /api/v1/projects/{project}/decisions/{key} | X-Ledger-UUID; retrieve material child/text descriptors before relying on completeness. |
| History, children, text | Returned history/options/references/links/fields URLs | Keep identity and revision pinned; restart stale pagination. |

Search is case-insensitive substring over key/title/question/answer/rationale, not reference
file contents, Boolean/vector search or an established global endpoint. Bound a cross-project
question to the accessible catalogue and relevant owners. Preserve query/perimeter and
inaccessible sources; an empty first page does not prove absence.

Read current question, answer, rationale, approval, options, references, relations, history,
evidence and planning links as material to the question. A URL/count is a pointer until
retrieved. Current implementation, qualification and access are separate claims.

Use [normal selected-deployment startup/reuse and bounded recovery](recovery.md) under
standing task authority when readiness must be established or a connection fails. An
already verified running deployment can be reused. No fresh per-start approval is needed.
After permitted recovery fails, stop dependent work; never substitute an unbound default.
For separately authorized mutations, read [changes](changes.md).
Read [decisions](decisions.md) before investigating a contested decision. Read
[legacy history](legacy-history.md) for source-origin collections or bytes.

## Authenticated read boundary

For ordinary retrieval, use bearer authentication supplied by the runtime and `X-Ledger-UUID` on project routes. Discover the authenticated schema at `/api/v1/schema`. Do not bypass the service with SQL or database-file edits.

Live notifications are freshness hints, not durable replay or approval to overwrite. Reconcile after reconnect. The browser's explicit refresh/review controls preserve drafts. No MCP server is supplied by this version; use the CLI/API rather than inventing MCP tools.

