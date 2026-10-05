# Decision Tracker

<p align="center"><img src="src/decision_tracker/static/logo.png" alt="Polymath Global" width="150" height="180"></p>

> Project decisions, their reasoning, and their history in one local workspace.

Decision Tracker is a portable application for people and agents. Each project has its own SQLite decision ledger, selected through a central catalog. The browser, CLI and API share the same rules, revision checks and audit history.

**Internal alpha · Python 3.14 · Private repository**

The application supports creating and editing decisions, comparing alternatives, recording evidence and changing decision status. The operator accepted the earlier system-browser experience and launch from Polymath home. The decision-page layout and action forms are implemented and regression-tested, including isolated Chromium workflows and actual 200% browser zoom. The installed migration project is active on data format 2. Projects & data is implemented and verified; operator reassessment remains separate. See the [verification record](docs/verification.md) for automated evidence and remaining qualification limits.

## Site map

| I want to… | Start here |
|---|---|
| Open the application or test the CLI | [Quick start](#quick-start) |
| Find a guide | [Documentation index](docs/README.md) |
| Work through the CLI or API | [Interface guide](docs/interfaces.md) |
| Give an agent access | [Agent-access skill](skills/decision-tracker/SKILL.md) |
| Manage credentials, launch or recovery | [Operations guide](docs/operations.md) |
| Understand the implementation | [Architecture](docs/architecture.md) |
| Develop and verify changes | [Contributing](CONTRIBUTING.md) |
| Report a security concern | [Private reporting instructions](SECURITY.md) |
| Review what has changed | [Changelog](CHANGELOG.md) |

## Quick start

Run commands from this repository's root using **its own `.venv`**. A parent project's environment does not provide this installation. For a new checkout, complete the [development setup](CONTRIBUTING.md#development-environment) first.

Activate the environment in PowerShell, then check the CLI and open the application:

```powershell
.\.venv\Scripts\Activate.ps1
decision-tracker --help
decision-tracker service open
```

On Windows, install the current-user launcher once to enable the Polymath home card:

```powershell
decision-tracker service install-launcher --json
```

For **first-time password setup**, run this in a private local terminal:

```powershell
decision-tracker auth setup-code
```

The code expires after 15 minutes. Enter it in the browser and choose your private password, then sign in. Do not share the code or password with an agent or put it in a command argument. Existing users simply sign in; [password changes and CLI-only recovery](docs/operations.md) have separate procedures.

The home card starts or reuses the service and opens the app in a new browser tab. An agent can start it without opening a browser:

```powershell
decision-tracker service ensure-running --json
```

The managed service stops after 90 minutes without useful activity when no operation or protected draft is active. No Windows startup task is installed.

## Three interfaces, one decision model

| Interface | What it provides |
|---|---|
| Browser | Project selection, search, record creation and editing, alternatives, lifecycle changes and history. A resizable right panel places compact decision controls above results; administration replaces those controls with a decorative logo. Drafts survive validation errors and conflicts. |
| CLI | Granular project, decision, option, reference, link, query, change and data commands. Structured input comes from a file or stdin. Data commands use the shared HTTP service. |
| API | Versioned `/api/v1` routes, typed changes and durable request IDs. Authenticated `GET /api/v1/schema` exposes OpenAPI. |

The [portable agent skill](skills/decision-tracker/SKILL.md) explains explicit project binding, credential use and conflict recovery. Copy its folder into your agent's supported skill directory. An MCP server is not included in this alpha.

[Quiet live updates](docs/live-updates.md) indicate when displayed data is stale. They do not move the reader's focus, reorder visible results or replace an open draft.

## Integrity and data boundaries

Decisions are open, closed or deprecated, with separate work, challenge and evidence states. Protected baselines require amendment. A rejected option is distinct from an unselected one. There is no hard-delete or silent-overwrite operation.

A batch advances the ledger once and retains immutable snapshots of affected decisions. Backups and exports are contained, hashed artifacts. Imports create candidates and never replace active data. Restore checks use isolated copies.

The app serves its packaged assets independently of Polymath home. Password verifiers are separate from project ledgers; retained agent tokens use current-user Windows DPAPI. The deployment descriptor at `%LOCALAPPDATA%/DecisionTracker/deployment/deployment.json` contains paths and identity, not secrets. See [security boundaries](SECURITY.md) and [operations](docs/operations.md).

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

Environment folders, credentials, project databases and generated evidence stay outside tracked source. The [tracking guide](docs/tracking-boundaries.md) explains the boundary. The [repository contract](docs/repository-contract.json) records ownership and implementation authority.

## Status and rights

Version `0.1.0.dev0` is for private local use. The [verification record](docs/verification.md) distinguishes automated proof, browser observations and operator acceptance. The QA Engine and Polymath Ledger migrations are planned separately; neither has been executed. Public distribution and broader platform qualification remain outside this checkpoint.

No distribution license or public release has been selected. Third-party license terms still apply.

---

<p align="center">Maintained by Polymath Global</p>
