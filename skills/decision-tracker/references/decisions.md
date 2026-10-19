## When to record a decision

Record a choice or unresolved question when its durable consequence needs an explicit, retrievable rationale: data meaning/fidelity; identity, schema, interface or compatibility contracts; authority, permissions, custody or retention; failure, retry, recovery or integrity guarantees; or a substantial tradeoff, dependency or commitment that later work must respect. This includes agent-owned engineering decisions within delegated scope. Admit a consequential unresolved choice before dependent implementation; retain alternatives, evidence, owner, affected scope and what must be settled.

Registration and approval escalation are separate. Resolve agent-owned choices only within actual delegated authority and the existing service capability/approval contract; assigning owner_role=agent grants no authority. Escalate choices that exceed delegation, change settled requirements or need the human's judgment. Never invent human approval. Record an authorized resolution and its rationale even when no new human approval is required.

Routine mechanics can remain in execution documentation when they implement an already defined contract without introducing a consequential choice. Formatting and private variable names usually qualify; public names or formats that create a compatibility commitment can require a decision. Search existing decisions first. Cite settled requirements and record only the new choice; do not reopen an approved requirement merely to choose its engineering representation. Use the existing decision/options/references/link operations, not a second editable register or a new CLI root. The repository's docs/decision-workflow.md gives human-facing examples; these instructions remain self-contained when installed alone.

## Recommended proposals

Whenever presenting multiple proposals for a decision, explicitly identify exactly one as **Recommended**. Explain why it is preferred for the current requirements, including its benefits and costs. Do not rely on proposal order or leave the operator to infer the recommendation.

Record that recommendation in the Tracker as well as in any review presentation. The current proposal model has no dedicated recommendation field: append `(Recommended)` to the recommended proposal's title and include a concise recommendation rationale in its description. Keep the proposal's benefit and cost fields informative. Use the existing option operations; preserve proposal IDs and unrelated content. When changing the recommendation, remove the old recommended label so each decision has one current recommendation. Read current decision and proposal state before editing, and respect revision and closed-record controls.

Recommended is advisory. It does not mean selected, approved, closed, implemented or accepted. Do not change proposal disposition, resolve the decision or report operator approval merely to identify a recommendation.

## Challenges during investigation

Use a challenge to record investigation feedback that questions a premise, proposal or answer. When a decision is contested, read `decision history --key KEY` with the same project, binding and credential flags before continuing the investigation, proposing a resolution or applying one. Follow history cursors until complete. The ordinary record exposes the contested flag; the challenge message is recorded as the transaction reason in history. Review subsequent messages and source evidence rather than treating the flag alone as sufficient context. Address the challenge in the next investigation response. Live notifications indicate changed data; they do not automatically start an agent or convey the complete conversation. Do not resolve a challenge merely because it has been read.

