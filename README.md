# Decision Tracker

<p align="center"><img src="src/decision_tracker/static/logo.png" alt="Polymath Global" width="150" height="180"></p>

> A lasting decision record for human–agent collaboration on complex projects.

Complex projects depend on many critical, specific decisions. As plans evolve and people or agents join the work, you need to retrieve what was decided, why it was decided, and the evidence behind it—without losing or rewriting the history.

Decision Tracker gives you and your agents a shared project decision ledger. Capture questions, compare alternatives, record approvals and preserve immutable decision snapshots throughout the project lifecycle. When a decision changes, its earlier record remains available for review.

**Local-use alpha · Windows launcher · Python 3.14**

## Keep the reasoning with the decision

A decision is more useful when you can recover its context. Each record brings together the question, answer, rationale, alternatives and supporting references. Relationships connect decisions so you can investigate dependencies and the impact of a proposed change.

- **Investigate:** record an open question, compare options and attach evidence.
- **Decide:** save the answer, reasoning and approval as a closed decision.
- **Revisit:** explicitly reopen a decision when circumstances change, or amend a protected baseline.
- **Retrieve:** search project records and inspect earlier revisions, approvals and relationships.
- **Retire:** mark decisions as deprecated while preserving their history and replacement relationships.

Decision approval, implementation and verification are recorded separately. Deciding what to do does not mean the work has been completed or tested.

## Work together across sessions

Use the browser to review and decide. Give your agents scoped access through the CLI or API to retrieve context, prepare proposals and make authorized changes. All three interfaces use the same decision rules and history.

Each project has its own ledger within a central project catalog. Explicit project identity and revision checks help prevent changes to the wrong project and protect against overwriting work made by another participant. If a request is interrupted, retained request IDs support safe retries.

The [agent-access guide](skills/decision-tracker/SKILL.md) explains credentials, project binding and conflict handling. Agent access does not replace your approval requirements. This version provides CLI and API access; it does not include an MCP server.

## Preserve history as the project evolves

You can edit an open decision, but you cannot silently rewrite a closed one. Reopening is an explicit, recorded step before further edits. Protected baselines require an amendment, and deprecated records remain available for inspection.

Committed changes retain immutable snapshots of affected decisions. Earlier answers, rationale and approval records remain retrievable as the current record evolves. The application has no hard-delete operation for decisions.

Backups and native exports preserve ledger history. Restore checks use isolated copies, and imports create candidates for review rather than overwriting active data. See the [operations guide](docs/operations.md) for backup and recovery procedures.

## Quick start

The managed browser launcher currently supports **Windows with Python 3.14**. Download or clone this repository, then open PowerShell in its folder:

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\python.exe -m pip install .
.\.venv\Scripts\decision-tracker.exe --help
```

This installs the application, browser assets and CLI with their runtime dependencies. Installation requires access to the Python package index unless you supply compatible offline wheels.

Initialize your local deployment and register the `decision-tracker://open` application link:

```powershell
.\.venv\Scripts\decision-tracker.exe service install-launcher --json
```

For first-time password setup, run these commands in your private terminal:

```powershell
.\.venv\Scripts\decision-tracker.exe auth setup-code
.\.venv\Scripts\decision-tracker.exe service open
```

Enter the setup code in the browser, choose your password and sign in. The code expires after 15 minutes. Keep your password and setup code private; agents use separate credentials.

**To launch again:**

```powershell
.\.venv\Scripts\decision-tracker.exe service open
```

This starts or reuses the local backend and opens your browser. Keep the installed environment in place because the launcher records its location. If you activate `.venv`, you can use the shorter command `decision-tracker service open`.

You can also open the registered application link from a browser that permits external applications. If the browser leaves a blank tab or blocks the link, use the CLI command above.

For agent access without opening a browser:

```powershell
.\.venv\Scripts\decision-tracker.exe service ensure-running --json
```

The backend normally stops after 90 minutes without useful activity when no operation or protected draft is active. It does not install a Windows startup task.

## Your data stays local

Project ledgers use SQLite in local, nonsynchronized storage. The application listens on your computer's loopback interface; this version is not intended for network hosting. Password credentials are separate from project ledgers, and stored agent tokens use Windows account protection.

Keep active databases out of synchronized folders and source control. Use verified backups and exports for recovery. The [security guide](SECURITY.md) describes access controls, trust boundaries and how to report a concern privately.

## Guides

| You want to… | Read |
|---|---|
| Give an agent access | [Agent-access guide](skills/decision-tracker/SKILL.md) |
| Use commands or integrate with the API | [CLI and API guide](docs/interfaces.md) |
| Manage passwords, launch, backups or recovery | [Operations guide](docs/operations.md) |
| Understand refresh and concurrent work | [Live updates](docs/live-updates.md) |
| Understand how the application works | [Architecture](docs/architecture.md) |
| Review tested behavior and current limitations | [Verification](docs/verification.md) |
| Contribute code or run tests | [Contributing](CONTRIBUTING.md) |
| Find all documentation | [Documentation index](docs/README.md) |

## Availability

Version `0.1.0.dev0` is a local-use alpha. Windows installation and managed CLI launch have been tested; broader platform support is not yet qualified. Source is available in this public repository. No distribution license or packaged release has been selected; third-party license terms still apply.

---

<p align="center">Maintained by Polymath Global</p>
