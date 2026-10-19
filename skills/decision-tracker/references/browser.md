# Browser-specific behavior

These retained owner descriptions are not fresh GUI qualification. Recheck the actual
installed surface before giving navigation instructions. Authority and allowed changes
come from the entrypoint and changes.md; switching a UI choice never grants approval.

Authenticated schema advertises `closed_context_v1` and explicit closed/protected allowlists. The browser enables reference/relationship controls and the Evidence action only with this capability. The selected record action top row is Edit, Status, Evidence; each of the three action groups has three buttons with full wrapping labels, and no duplicate Evidence button in the record. Status sets open work to Queued or Under investigation; deferred work uses Resume. Status remains unavailable on closed records. The record’s Evidence state readout currently uses structured JSON. Unavailable substantive child controls remain hidden, and the action groups remain in place. Evidence forms submit changed slots only, confirm clearing, and retain drafts through failure/session recovery for explicit re-review. No supplemental change may share a request with a lifecycle/planning change affecting the same record. No SQL migration is required; after new writes use a compatible current runtime and checked backup/restore paths. Older binaries may not recognize the new operation even at the same ledger schema.

## Browser resolution choices

Explicitly switching the resolution radio choice replaces the Decision, Why this choice and Change note fields. Selecting a proposal fills these fields from that proposal; selecting Write a different answer clears the answer and rationale and resets the generated change note. Drafts are not cached per choice and there is no additional preservation prompt. Editing a proposal answer converts it to a written answer while retaining the text being edited. Approval details remain independent of the solution choice.

The browser label Decide invokes the existing `decision.close` operation; CLI `decision close` and status `closed` are unchanged.

