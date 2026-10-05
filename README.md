# Decision Tracker

Portable, project-aware decision tracking for local use. Each project has its own SQLite ledger; a central catalog provides explicit project selection. The browser, CLI and API share the same transition rules, revision checks and audit history.

**State:** internal alpha implementation. Windows verification and owner acceptance are separate. Current evidence is recorded in docs/verification.md. No public release, migration or production qualification is implied.

## Start the application

Use Python 3.14 and the project-local environment described in [CONTRIBUTING.md](CONTRIBUTING.md).

1. Copy `docs/config.example.json` to an ignored local configuration file.
2. Choose a local, nonsynchronized data directory. Set `local_storage_confirmed` to true after checking its location. Relative paths resolve from the configuration file's directory; omitting `data_root` uses the user's local application-data directory.
3. Inject a high-entropy credential through `DT_OPERATOR_TOKEN`. Use an owner-managed secret mechanism or a hidden terminal prompt. Never put the credential in a URL, command argument, committed file or chat.
4. Run the foreground service:

```powershell
.venv/Scripts/decision-tracker.exe service serve --config .local/config.json
```

Open [Decision Tracker](http://127.0.0.1:8765/) or its card in the Polymath home page. The card opens a new tab and requires the service to be running. Sign in using the injected credential, then create a project. The browser supports record mutation, lifecycle transitions, child records and maintenance actions.

Stop the foreground service with Ctrl+C. No daemon or automatic startup is installed. An occupied port fails; the service never silently changes its port. A configured alternate port requires changing the deployment's home link.

## Interfaces

- **Browser:** project selector, search, decision detail with bottom-anchored right-panel results, Focus view, editing dialogs, explicit lifecycle changes, retained drafts on validation/conflict, history and app-specific context panel.
- **CLI:** `decision-tracker --help`; project, decision, option, reference, link, query, change and data groups. Structured fields use `--input FILE` or stdin. All data commands use HTTP; the CLI never bypasses service rules.
- **API:** versioned `/api/v1` routes. Authenticated `GET /api/v1/schema` exposes OpenAPI. Mutations use typed change envelopes and durable request IDs. See [API and CLI guide](docs/interfaces.md).

A GPT agent-access skill is a follow-up against these interfaces. An MCP server is not included in this alpha.

## Integrity and scope

Decisions are open, closed or deprecated, with separate work/challenge/evidence states. Protected baselines require amendment. No hard-delete or silent overwrite operation exists. A batch advances the ledger once and records immutable complete snapshots of all affected decisions. A rejected option is different from an unselected one.

Backups and exports are contained, hashed artifacts. Imports create candidates; they never replace active data. Restore checks validate isolated copies. See [Operations](docs/operations.md) and [Security](SECURITY.md).

The app serves only its packaged assets. It does not expose the Polymath folder index, share the home page's credentials or register source projects automatically.

## Development and rights

[Repository contract](docs/repository-contract.json), [architecture](docs/architecture.md) and [Calamum workflow](docs/calamum.md) govern implementation and proof. All software tests run through native Calamum. Generated evidence and service data remain ignored.

This repository is private. No distribution license or public release has been selected. No LICENSE is fabricated; third-party license terms still apply.
