# Decision Tracker

Portable, project-aware decision tracking for local use. Each project has its own SQLite ledger; a central catalog provides explicit project selection. The browser, CLI and API share the same transition rules, revision checks and audit history.

**State:** internal alpha for local use. The operator confirmed password setup, system-browser testing and launch through the Polymath home card on 2026-10-05. Current evidence is recorded in docs/verification.md. No public release, migration or production qualification is implied.

## Start the application

Use Python 3.14 and the project-local environment described in [CONTRIBUTING.md](CONTRIBUTING.md).

On Windows, install the current-user launcher once:

```powershell
.venv/Scripts/decision-tracker.exe service install-launcher --json
```

In a **private local terminal**, create your one-time setup code:

```powershell
.venv/Scripts/decision-tracker.exe auth setup-code
```

The code expires after 15 minutes. Open the Polymath Decision Tracker card, or run `decision-tracker service open`. Enter the setup code and choose your private password in the browser. Setup does not sign you in automatically. Do not send the code or password to an agent or paste it into a command argument.

The card starts or reuses the loopback service and opens the application through the default browser. Agent sessions start it without opening a browser using `service ensure-running --json`. The managed service stops after 90 minutes without useful activity, provided no operation or protected draft is active. No Windows startup task is installed.

The deployment descriptor is `%LOCALAPPDATA%/DecisionTracker/deployment/deployment.json`. It contains paths and identity, not secrets. Password verifiers are separate from project ledgers; explicitly stored agent tokens use current-user DPAPI. See [Operations](docs/operations.md) for credentials, recovery and foreground operation.

## Interfaces

- **Browser:** project selector, search, decision detail with bottom-anchored right-panel results, Focus view, editing dialogs, explicit lifecycle changes, retained drafts on validation/conflict, history and app-specific context panel.
- **CLI:** `decision-tracker --help`; project, decision, option, reference, link, query, change and data groups. Structured fields use `--input FILE` or stdin. All data commands use HTTP; the CLI never bypasses service rules.
- **API:** versioned `/api/v1` routes. Authenticated `GET /api/v1/schema` exposes OpenAPI. Mutations use typed change envelopes and durable request IDs. See [API and CLI guide](docs/interfaces.md).

The portable [agent-access skill](skills/decision-tracker/SKILL.md) covers these CLI/API interfaces, explicit project binding and conflict recovery. Copy its folder into your agent's supported skill directory. An MCP server is not included in this alpha.

## Integrity and scope

Decisions are open, closed or deprecated, with separate work/challenge/evidence states. Protected baselines require amendment. No hard-delete or silent overwrite operation exists. A batch advances the ledger once and records immutable complete snapshots of all affected decisions. A rejected option is different from an unselected one.

Backups and exports are contained, hashed artifacts. Imports create candidates; they never replace active data. Restore checks validate isolated copies. See [Operations](docs/operations.md) and [Security](SECURITY.md).

The app serves only its packaged assets. It does not expose the Polymath folder index, share the home page's credentials or register source projects automatically.

## Development and rights

[Repository contract](docs/repository-contract.json), [architecture](docs/architecture.md) and [Calamum workflow](docs/calamum.md) govern implementation and proof. All software tests run through native Calamum. Generated evidence and service data remain ignored.

This repository is private. No distribution license or public release has been selected. No LICENSE is fabricated; third-party license terms still apply.
