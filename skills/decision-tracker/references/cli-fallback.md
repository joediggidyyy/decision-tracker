# Conditional CLI equivalents

Read only when CLI access is allowed by the actual assignment. Ordinary retrieval routes
to api-access.md. These owner-supported CLI examples do not authorize a forbidden route,
service start, credential provisioning or fallback after an essential access failure.
The selected configured origin overrides the generic default described below.

## Connect and identify

Use the configured CLI executable (or the application repository's local environment), service origin and credential-variable **name**. The default service origin is `http://127.0.0.1:8765`. Never read, echo, place in command arguments, or store a credential value. First read any deployment-provided names-only agent-access descriptor and reuse the configured persistent agent principal and existing scope. Do not create per-session credentials or narrow established project visibility by default. Provision a separate principal only within explicit authorization; each operation still requires the intended project/UUID and capabilities. The following examples assume its environment variable is `DT_AGENT_TOKEN`; do not silently substitute the operator credential if it is absent.

```text
decision-tracker service status --token-env DT_AGENT_TOKEN --json
decision-tracker project list --token-env DT_AGENT_TOKEN --json
decision-tracker project show --project example --bind .local/example-binding.json --token-env DT_AGENT_TOKEN --json
decision-tracker decision list --project example --binding .local/example-binding.json --token-env DT_AGENT_TOKEN --json
```

Replace `example` with the intended project ID. Create the ignored binding directory if needed. A binding is an exclusive-created file containing project ID and ledger UUID, not credentials. Reuse an existing matching binding. Never infer identity from the working directory, silently rebind, or register a project to bypass a mismatch. Pass `--base-url` explicitly when using a configured alternate origin.

Use `decision get`, `decision history`, `query context`, and `query impact` with `--key D000001` and the same project/binding/token flags. Follow collection cursors and revision-pinned text chunks when responses indicate incomplete content. A stale cursor requires restarting the read; do not combine pages from different revisions. Impact results can be truncated.

