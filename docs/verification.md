# Verification state

Implementation: internal alpha. Owner acceptance: pending. Production qualification: not claimed.

All tests run through native Calamum. Generated run logs, proof manifests and screenshots are retained locally and excluded from Git. The final handoff receipt supplies exact run IDs and source hashes.

| Area | Evidence route |
|---|---|
| State, history, retries, pagination, UTF-8 | dt-focus / dt-integration pytest lane |
| API, sessions, scope, Host/Origin/CSRF, paths | dt-integration pytest lane |
| Concurrency, interrupted write, busy bound, restart | dt-integration pytest lane |
| Real CLI HTTP and mutation command coverage | dt-integration pytest lane |
| Export/import, backup, restore, tamper detection | dt-integration pytest lane |
| Actual browser, responsive shell, home launch | dt-browser empirical lane |
| Environment/package and bounded process cleanup | dt-bootstrap / dt-integration |

Retained failures include the initial Windows backup-handle defect and browser label-encoding defect. Corrections require subsequent passing evidence; failed observations are not erased.

Two source-project migrations remain excluded. No real project database has been registered by proof. The browser service uses isolated synthetic data and is stopped after review.

Current responsive behavior supersedes the earlier compact-collapse experiment: at 980 CSS pixels or narrower the panel is always visible in document flow and the focus icon is hidden. Desktop focus glyph is 18px at 60% opacity inside a 44px target. Actual 390px observations show no horizontal overflow, including entry from desktop focus mode. Full browser qualification, actual 200% zoom and assistive-technology review remain pending.

Native integration run `20261005T081958Z-dt-integration` passed 64 tests with source correspondence. Run `20261005T082504Z-dt-integration` passed 64 test assertions but its wrapper failed source correspondence because files changed during execution; it is not a whole-source pass. Focused run `20261005T082844Z-dt-live-focus` passed 10 tests with source correspondence, covering the notification/transport/parser increment. Subsequent changes were UI refinements and handoff artifacts. The next stable integration receipt is retained separately rather than written into its own tested source snapshot.

Browser evidence includes red/yellow/green/gray states, unchanged observer focus/content/scroll on notification, retained drafts, explicit comparison/rebase followed by a separate save, desktop resizing and compact stacking. These are partial observations, not a full empirical-lane pass. The preview source was refreshed during operator review and cannot serve as immutable whole-run source proof.

The skill's metadata validator checks structure only. Existing real HTTP CLI tests cover bindings, mutations, replay and conflict; they do not establish independent-agent usability. Normal-startup instructions do not claim production credential provisioning or real-data activation.


Credential/lifecycle increment: native integration `20261005T102315Z-dt-integration` passed 78 tests with unchanged source. Focused credential run `20261005T101845Z-dt-auth-focus` passed; empirical `20261005T101935Z-dt-account-browser` passed observed login, footer placement, password-form layout, draft retention and 640px behavior. Browser proof used disposable preprovisioned credentials. Native API tests cover setup/password change; browser credential-change submission was not exercised. Retained earlier failures include named-pipe mode, response lifetime, busy reconnect and Windows connection timing.

Installed local handler and normal cold start/reuse were observed separately from immutable software proof. This does not prove all LC01–LC10 or AC01–AC10 adversarial/OS cases. Actual 200% zoom, screen-reader review and owner acceptance remain unverified. Real owner password setup and agent grants are private operator actions, not completed by implementation.

Final focused proof `ff15f9b34b4c43779bc715555b31350f` passed with unchanged source after adding malformed-URI rejection, unknown-listener refusal before authorization headers, and migration prevalidation checks. The official agent-skill metadata validator also passed through native Calamum; installed skill bytes match the repository copy.

Latest focused run `20261005T103305Z-dt-auth-focus` passed with unchanged source, including a status-poll regression: status leaves the idle timestamp unchanged while a project read advances it. This follows the 78-test integration checkpoint; subsequent runtime changes were covered by focused proofs rather than a repeated broad suite.
