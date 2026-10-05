# Verification state

Internal alpha for local use. On 2026-10-05 the operator confirmed successful password setup, testing in the system browser and launch through the Polymath home card. This is operator-reported acceptance, separate from agent-observed and automated proof. No real source project has been migrated.

## Retained evidence

| Checkpoint | Result |
|---|---|
| 20261005T102315Z-dt-integration | 78 tests passed; source unchanged |
| 20261005T103305Z-dt-auth-focus | 15 focused tests passed; source unchanged |
| 20261005T101935Z-dt-account-browser | Observed password sign-in, footer account placement, form layout, draft retention and narrow layout passed |
| 20261005T105347Z-dt-auth-focus | 20 focused tests passed; source unchanged; concurrent launch, stored-agent CLI, online/offline recovery, revocation, interrupted token publication and shutdown admission |
| 20261005T105612Z-dt-integration | Final pre-push checkpoint: 87 tests passed; source unchanged |
| Agent skill metadata | Official validator passed through native Calamum; installed skill matches repository source |

Native software evidence is retained under ignored `.calamum/generated/runs` and `.local/proofs`. Proof copies bind imports to copied source and use bounded Windows process supervision. Tests use disposable credentials; no owner password or real project database is a fixture. History contains earlier checkpoints; later source correspondence is checked explicitly rather than inferred from older runs.

Failed runs remain retained. Closeout failures included two incorrect test expectations (scoped project nondisclosure and public health versus authenticated access), then an actual Windows connection-abort edge during shutdown. The corrected test follows the existing authorization contract; the runtime now returns a controlled unavailable error for the abort. It must still stop within the original deadline.

Existing integration covers decision rules, revisions/history, HTTP/CLI binding, retries, scope, Host/Origin/CSRF, bounded input, paths, notifications, artifacts and candidate-only recovery. Final combined evidence and native project aggregate are retained in the local closeout audit.

## Limits

Actual 200% zoom and screen-reader checks remain explicitly deferred by the operator for local use. Cross-platform qualification, public distribution, MCP and the two source-project migrations are separate. Current-user Windows tests do not establish protection from a compromised OS account or exhaustive cross-user/OS failure coverage. LC/AC planning matrices are not blanket security certification.

The historical home-layout proof needs retained `.local/home-integration` artifacts, deliberately excluded from Git because the business home page is private. A new clone needs an authorized sanitized local fixture before that empirical/history check; do not copy the private page or secrets into the repository to make the suite self-contained.
