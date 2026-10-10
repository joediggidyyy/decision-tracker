# Decision Tracker

<p align="center"><img src="src/decision_tracker/static/logo.png" alt="Polymath Global" width="150" height="180"></p>

> A lasting decision record for human–agent collaboration on complex projects.

Decision Tracker helps you and your agents collaborate on complex projects with many critical, specific decisions. Keep each decision, its reasoning and supporting evidence retrievable throughout the project lifecycle. As plans evolve, immutable snapshots preserve earlier decisions so you can revisit what was agreed and why.

**Local-use alpha · Windows 11 x64 installer · Public source repository**

Capture open questions, compare alternatives, record approvals and connect related decisions. Use the browser to review and decide, and the CLI or API to give agents access to the same project context. Closed decisions require explicit reopening before edits; protected baselines require amendment. Earlier records remain available as the project changes. Decision approval, implementation and verification stay distinct, so agreeing on an approach does not imply that the work is complete.

## Site map

| I want to… | Start here |
|---|---|
| Install and launch the application | [Quick start](#quick-start) |
| Find a guide | [Documentation index](docs/README.md) |
| Know which choices to record | [Decision workflow](docs/decision-workflow.md) |
| Work through the CLI or API | [Interface guide](docs/interfaces.md) |
| Reuse decisions across projects | [Saved decisions and optional groups](docs/saved-decisions.md) |
| Give your agents access | [Agent-access skill](skills/decision-tracker/SKILL.md) |
| Manage credentials, launch or recovery | [Operations guide](docs/operations.md) |
| Understand the implementation | [Architecture](docs/architecture.md) |
| Contribute code or run tests | [Contributing](CONTRIBUTING.md) |
| Report a security concern | [Private reporting instructions](SECURITY.md) |
| Prepare an installable package | [Packaging guide](docs/packaging.md) |
| Review what has changed | [Changelog](CHANGELOG.md) |

## Quick start

For ordinary Windows 11 x64 use, choose `DecisionTracker-0.1.0a1-windows-x64-setup.exe` from the release assets. This alpha installer includes Python and runtime dependencies; no separate Python, pip or terminal setup is needed. See [Windows installation](docs/windows-installation.md) for hashes, unsigned-app prompts and repair. No public release is claimed. The retained compiled Setup predates the latest deprecation-approval update; it has not been requalified for that update. See [current qualification and recovery limits](docs/verification.md#current-status).

Run Setup under your own Windows account. It creates a Start menu entry and offers a desktop shortcut. Launch Decision Tracker. On first launch, click OK to copy a temporary setup code, paste it into the browser form and choose your password. Cancel leaves setup unfinished. The code expires after 15 minutes. A fresh deployment starts with no projects or saved decisions.

### Python installation alternative

The managed browser launcher currently targets **Windows** with **Python 3.14**. Download this repository or clone it, then open PowerShell in the repository folder. Install the application and its runtime dependencies into your own environment:

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\python.exe -m pip install .
.\.venv\Scripts\decision-tracker.exe --help
```

This installs the application, browser assets and `decision-tracker` CLI with their runtime dependencies. Installation requires access to the Python package index unless you provide compatible offline wheels. If you want to contribute code or run tests, follow the [development setup](CONTRIBUTING.md#development-environment).

Initialize the current-user deployment and register its optional `decision-tracker://open` link handler once:

```powershell
.\.venv\Scripts\decision-tracker.exe service install-launcher --json
```

For **first-time password setup**, run this in a private local terminal:

```powershell
.\.venv\Scripts\decision-tracker.exe auth setup-code
.\.venv\Scripts\decision-tracker.exe service open
```

The code expires after 15 minutes. Enter it in the browser and choose your private password, then sign in. Do not share the code or password with an agent or put it in a command argument. Existing users simply sign in; [password changes and CLI-only recovery](docs/operations.md) have separate procedures.

**Launch again:** run `.\.venv\Scripts\decision-tracker.exe service open` from this folder. It starts or reuses the backend and opens the browser. Keep the installed environment in place: the launcher records its location. You can activate `.venv` to use the shorter `decision-tracker` command; no global PATH change is required.

You can also launch through the registered `decision-tracker://open` application link. Your browser may ask permission to open the local application. If the link leaves a blank tab, use the CLI launch command above. Your agents can start the backend without opening a browser:

```powershell
.\.venv\Scripts\decision-tracker.exe service ensure-running --json
```

The managed service stops after 90 minutes without useful activity when no operation or protected draft is active. No Windows startup task is installed.

## Browser pages

Use **Decisions** for project records, **Projects** for project and data administration, and **Library** for reusable decisions. The project selector and connection indicator share the top-right heading area on Decisions and Projects; selection carries across page navigation. Narrow screens wrap controls to fit. Library chooses its destination in staging.

Library starts empty. Create saved decisions with optional group tags, browse groups with the dropdown, and use individual checks or Check all. Checks persist in the current tab across browsing and page changes. Add to staging, adjust the copied set, choose or create a destination, then Publish. Each completed project copy receives the next decision number and starts closed and protected. Publish records the current browser operator’s approval; answers and rationale are required. View contains Edit and Delete. Groups have no effect after staging, and later Library edits leave project copies unchanged. See the [Library guide](docs/saved-decisions.md) for retry, transfer and backup details.

## Three interfaces, one decision model

| Interface | What it provides |
|---|---|
| Browser | Review questions and alternatives, record decisions, search project records and inspect their history. Your drafts are retained when validation fails or another participant changes the record. |
| CLI | An interface for humans and agents, offering granular control and authorized administrative access through structured commands. Manage projects, decisions, alternatives, references, relationships, credentials, backups and service operations. |
| API | Integrate decision tracking with your tools through versioned `/api/v1` routes. Revision checks and durable request IDs protect concurrent changes and retries. Authenticated `GET /api/v1/schema` provides the API specification. |

The [portable agent skill](skills/decision-tracker/SKILL.md) explains explicit project binding, credential use and conflict recovery. Copy its folder into your agent's supported skill directory. An MCP server is not included in this alpha.

Record choices whose durable consequences need an explicit, retrievable rationale, including engineering choices owned by agents within delegated scope. Registration and approval escalation are separate: seek human judgment when a choice exceeds delegation or changes settled requirements. The [decision workflow](docs/decision-workflow.md) gives the threshold and examples.

Use **Decide** beside an open question to record the answer and approval. The resulting record has status `closed`; CLI `decision close` and API `decision.close` retain their existing names. The decision is recorded without marking its implementation or verification complete.

Use **Deprecate** to end use of a decision while retaining its answer and history. It uses the same current human or reported external Approval controls as Decide. Deprecation is terminal; its approval evidence stays separate from the original resolution. See [Decision workflow](docs/decision-workflow.md#deprecation) and the [interface contract](docs/interfaces.md#decision-approval-events-schema-2).

Once you incorporate a closed decision into authoritative planning, use **link** beside its status. Choose a planning document from the dropdown, or use **Add document…** to browse the project's planning folders or paste a path. Its sections load automatically; select the section and link. Success leaves a soft green `linked` tag and an immutable receipt in History. Reopening starts a fresh cycle while preserving earlier receipts. Linking records where the approved decision was incorporated; it does not edit the plan or mark implementation or verification complete. The [interface guide](docs/interfaces.md#planning-links) covers CLI access, optional-anchor records and compatibility with earlier names.

[Live updates](docs/live-updates.md) tell you when another participant has changed the data without moving your focus or replacing your draft.

## Integrity and data boundaries

Each project has its own SQLite decision ledger within a central project catalog. Decisions are open, closed or deprecated, with separate work, challenge and evidence states. Protected baselines require amendment, and a rejected option remains distinct from an unselected one. The application has no hard-delete or silent-overwrite operation for decisions.

Committed changes retain immutable snapshots of affected decisions. You can retrieve earlier answers, reasoning and approval records as the current decision evolves. Backups and native exports preserve ledger history; imports create candidates for review rather than replacing active data. Restore checks use isolated copies.

Your data stays in local, nonsynchronized storage. Password credentials are separate from project ledgers, and stored agent tokens use Windows account protection. The application listens on your computer's loopback interface; this version is not intended for network hosting. See the [security guide](SECURITY.md) and [operations guide](docs/operations.md) for access controls and recovery procedures.

## Repository map

```text
decision-tracker/
├── src/decision_tracker/     Shared service, CLI, domain rules and browser assets
├── docs/                    Architecture, interface and operating guides
├── skills/decision-tracker/ Portable agent-access instructions
├── tests/                   Assertions and observed-workflow checks
├── catalog/                 Native Calamum test definitions
├── tools/                   Bounded proof and browser-observation helpers
├── .calamum/project.json    Portable Calamum project descriptor
├── pyproject.toml           Package metadata and CLI entry point
└── requirements-dev.lock    Exact development dependency versions
```

Keep your environment, credentials, project databases and generated evidence out of source control. See the [tracking guide](docs/tracking-boundaries.md) and [repository contract](docs/repository-contract.json) for contribution and repository requirements.

## Status and rights

Version `0.1.0a1` is a local-use alpha in a public source repository. Windows installation and managed CLI launch have been tested; broader platform support is not yet qualified. See the [verification record](docs/verification.md) for tested behavior and current limitations.

Copyright 2026 Polymath Global. Licensed under the [Apache License 2.0](LICENSE); see [NOTICE](NOTICE) for attribution. Third-party components retain their own license terms. The selected release is an unsigned Windows 11 x64 prerelease; publication and second-machine acceptance remain separate.

---

<p align="center">Maintained by Polymath Global</p>

## Imported decision histories

Decision Tracker can retain a project’s earlier decision history alongside its native decisions. Source identities, literal values, ordered events, versions and references remain immutable and retrievable. Unknown source values remain unknown; source benefit and summary text retain their attribution. New decisions and resolutions use the ordinary validation and approval rules.

The existing CLI and API support complete source retrieval and maintenance of inactive import candidates. See [Legacy import and recovery](docs/legacy-import.md). Each source migration requires independently qualified mapping, complete request/export sizing and explicit execution authority. Source-specific progress and deployment records belong in the owning business workspace.
