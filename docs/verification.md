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

Latest regression: native Calamum run `20261005T073816Z-dt-integration` passed with source correspondence verified (proof `71d47f29c721438aa68cf9ae19695b25`). Responsive browser observations verified compact collapse, expansion, selection, no horizontal overflow, desktop dragging, keyboard resizing and preference persistence. Full browser qualification, including actual 200% zoom, remains pending; partial observations do not constitute a full browser pass.

Live-update implementation and evidence scope: see [live-updates.md](live-updates.md). Native run `20261005T081958Z-dt-integration` passed with source correspondence verified; its snapshot includes the final comparison UI but predates the five-second graceful-shutdown setting. Browser observations are retained as partial qualification, not a full empirical-lane pass.
