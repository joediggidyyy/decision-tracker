# Documentation

[Home](../README.md) · [Contributing](../CONTRIBUTING.md) · [Security](../SECURITY.md) · [Changelog](../CHANGELOG.md)

Use this map to find the guide for your task. These documents describe the local-use alpha in the public source repository; approved business plans and project migration plans remain in Polymath custody.

## Use and operate

| Guide | Purpose |
|---|---|
| [Decision workflow](decision-workflow.md) | When to record a decision, agent-owned choices and approval escalation. |
| [Saved decisions](saved-decisions.md) | Reusable content, optional tags, staging, repeated publication and portable backups. |
| [Interfaces](interfaces.md) | Planning links, CLI and API commands, authentication, project binding and change envelopes. |
| [Operations](operations.md) | Start and stop the service, manage credentials, back up data and recover safely. |
| [Legacy imports](legacy-import.md) | Preserve original decision history, retrieve source content and recover inactive import candidates. |
| [Live updates](live-updates.md) | Freshness colors, explicit refresh, draft preservation and panel behavior. |
| [Agent-access skill](../skills/decision-tracker/SKILL.md) | Portable instructions for agents using the CLI or API. |
| [Configuration example](config.example.json) | Example configuration fields; not a credential store. |

For lifecycle approval and repair compatibility, read [Deprecation](decision-workflow.md#deprecation), [Approval evidence](interfaces.md#decision-approval-events-schema-2), [Runtime replacement](operations.md#history-compatibility-for-runtime-replacement) and [Current qualification](verification.md#current-status).

## Develop and review

| Guide | Purpose |
|---|---|
| [Contributing](../CONTRIBUTING.md) | Local environment, native validation and review workflow. |
| [Architecture](architecture.md) | Catalog, ledgers, shared service and application boundaries. |
| [Calamum workflow](calamum.md) | Native definitions, retained runs and proof correspondence. |
| [Packaging](packaging.md) | Build and inspect local wheel/source candidates, install, upgrade and hand off support material. |
| [Verification](verification.md) | Actual evidence, operator acceptance and deferred checks. |
| [Tracking boundaries](tracking-boundaries.md) | What belongs in Git, what stays local and pre-push review. |
| [Repository contract](repository-contract.json) | Machine-readable ownership, scope and publication authority. |
| [Agent instructions](../AGENTS.md) | Repository-specific working rules. |

The Polymath mark in the repository README reuses the application's existing approved [logo asset](../src/decision_tracker/static/logo.png). No separate project mark or new brand asset is introduced.

---

<p align="center">Maintained by Polymath Global</p>

Windows users: [Setup, first launch and repair](windows-installation.md).
