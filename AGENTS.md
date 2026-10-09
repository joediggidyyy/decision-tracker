# Decision Tracker agent instructions

Read README.md, docs/repository-contract.json and docs/calamum.md first.
This is a Polymath-owned public source repository, not a client-owned tree.
Apply the organization workspace/naming and workflow authorities from the
operator's Polymath workspace. Machine-local authority locations belong in
.local, not portable runtime code.

Read docs/packaging.md before preparing distribution artifacts. Package application code and public support material only; preserve runtime data and local evidence. Local candidate builds do not authorize publication.

All software tests run through native Calamum. Do not invoke PyTest directly.
Use tools/prove.py for bounded native execution; retain failures and verify
source correspondence. Do not confuse bootstrap proof with application proof.
Keep source, actual verification and owner acceptance distinct.

Keep .venv, .local, .calamum/generated, credentials and all project databases
out of Git. Do not read secret values. Do not push, publish, add account
permissions or activate monitors without explicit scope.

The approved product includes browser record mutation, a comprehensive CLI
and an API. Build the shared rules once. The Polymath home page and app shell
integration preserve independent app/data boundaries.

The portable agent-access skill is skills/decision-tracker/SKILL.md. Keep it
aligned with actual CLI/API behavior; do not advertise unimplemented MCP tools.

For this operator's installed deployment, read `.local/agent-access.json` when
present before service access. It records the persistent cross-project agent
principal and names-only connection settings. Do not recreate credentials per
session or narrow project visibility by default. Explicit project/UUID binding
and authorization for each requested mutation still apply.
