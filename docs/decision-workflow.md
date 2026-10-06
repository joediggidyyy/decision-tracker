# Recording project decisions

[Documentation](README.md) · [Home](../README.md) · [Interfaces](interfaces.md)

Record a choice or unresolved question when its **durable consequence needs an explicit, retrievable rationale**. Humans and agents use the same decision record throughout the project lifecycle.

## What belongs in the tracker

Record consequential choices about:

- The meaning or fidelity of project data.
- Identity, schemas, interfaces and compatibility contracts.
- Authority, permissions, custody and retention.
- Failure, retry, recovery and integrity guarantees.
- Substantial tradeoffs, dependencies or commitments that later work must respect.

These include engineering decisions owned by agents within delegated scope. Capture an unresolved choice before implementing work that depends on its answer. Record the question, alternatives, evidence, responsible role and affected scope. Once resolved under the applicable authority, preserve the answer and rationale.

## Registration and approval

| Step | Purpose |
|---|---|
| Register a decision | Make a consequential choice visible, discussable and retrievable. |
| Seek human approval | Obtain judgment or authority when a choice exceeds delegation, changes settled requirements or needs the human's judgment. |
| Record an authorized resolution | Preserve the selected answer, rationale and actual authority or approval evidence. |

An agent-owned decision can belong in the tracker without requiring a new human approval. Its resolution still needs actual delegated authority and the service permissions and approval evidence required by the application. Choosing an owner does not grant permission. Agents must not invent a human approval or claim that a proposal has been accepted.

## Practical boundary

| Example | Treatment |
|---|---|
| Select a legacy-data representation that determines future retrieval and compatibility | Record the choice and its tradeoffs. |
| Choose identity-collision or recovery behavior | Record the choice before dependent implementation. |
| Implement an already specified validation rule | Document the implementation; register any consequential ambiguity discovered. |
| Format a document or rename a private variable without changing a contract | Keep it in execution documentation. |
| Name a public field or select a format that creates a compatibility commitment | Assess and record the consequential choice. |

Search existing decisions first. Cite settled requirements and focus a new entry on the remaining choice. For example, a requirement to preserve unknown historical values can remain settled while the database representation is a separate engineering decision.

Use **New decision** to register a question and **Decide** to record its authorized resolution. Closed decisions retain immutable history. Incorporate the resolution into authoritative planning, then use **apply** with its planning anchor. Recording, planning application, implementation, verification and acceptance remain distinct. The [interface guide](interfaces.md) and [agent skill](../skills/decision-tracker/SKILL.md) cover supported commands and revision checks.
