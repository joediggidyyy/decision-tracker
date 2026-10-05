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
