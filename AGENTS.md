# Decision Tracker agent instructions

Read README.md, docs/repository-contract.json and docs/calamum.md first.
This is a Polymath-owned private repository, not a client-owned tree.
Apply the organization workspace/naming and workflow authorities from the
operator's Polymath workspace. Machine-local authority locations belong in
.local, not portable runtime code.

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

A dedicated agent-access GPT skill is a planned follow-up. Do not create a
stub skill that advertises unimplemented commands.
