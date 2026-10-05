# Approved architecture

Decision Tracker uses one local Python service, a project catalog and one SQLite
ledger per project. FastAPI/Uvicorn host the shared API and packaged HTML/CSS/JS.
The CLI calls the same API. Browser record mutation is required.

The Polymath home page will place Tools above Workspace and keep Sites in place.
The tracker card opens the app in a new tab. The app adopts the existing dark
palette, branded header and app-specific right context panel; list/detail and
Focus views operate inside that shell.

Authentication, expected project UUID, revisions, idempotent changes, immutable
history, decision-tag semantics and verified backups are required. Native import
creates an unregistered candidate; it does not merge or overwrite live data.

Implementation follows the approved business-custody execution contract.
The machine-local planning index identifies that authority without copying
business evidence into the package. Source-project migrations are separate work.
The session target is flexible; security, best practices and proof are not.

Future agent access uses API and CLI JSON first. A dedicated GPT skill will teach
safe discovery, explicit project routing, validation and retry behavior after the
interfaces exist. MCP remains an optional thin adapter, not a first-build dependency.
