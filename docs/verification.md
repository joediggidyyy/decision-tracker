# Verification state

[Documentation](README.md) · [Home](../README.md)

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

## Decision-form implementation checkpoint — 2026-10-05

The form update is implemented in source. Native run `20261005T134201Z-dt-integration` passed all 104 tests with source unchanged. The final proof is `.local/proofs/8b8f853697264d2d83cc4d882c43db17/proof-manifest.json`. The final focused approval suite passed 16 tests at `20261005T134629Z-dt-approval-focus`, including process exit immediately before and after upgrade commit.

Actual browser observations are retained in proof folders `1031c8842d164c7b932959333929a824` and `2eb74de9ee404ade8e4daf230292b59f`. They cover proposal/manual/historical saves, edited-text protection, single/multiple/no eligible choices, long text, rejected/retired options, future-date correction and error focus, DST gap/fold handling, unknown dates, 640-pixel layout, lost-response replay without another close revision, and committed-save/failed-refresh distinction. Final source also fixes the obsolete selection notice and replaces raw parser text with plain wording; the latter correction is included in the final automated run.

**Qualification remains incomplete.** The empirical lane remains no-go because actual 200% zoom was not observable through the connected in-app browser. Earlier app-wide zoom deferral does not waive this form's new requirement. Operator acceptance of these revised workflows has not been recorded. Full keyboard/session-expiry observations for the revised form remain incomplete; existing account/lifecycle tests are supporting evidence only. Upgrade process-exit recovery is directly tested before and after commit.

Upgrade tests cover backup failure, restore-check failure, partial DDL failure, final-validation failure, concurrent replay, v1 preservation, schema2 exchange/recovery, immutable approval evidence, aggregate bounds and reopening/edit chains. These tests do not claim exhaustive OS crash or storage-failure certification. All failed attempts and the first browser timeout remain retained.

The active migration-planning project remains schema 1, revision 1, UUID `0267a702-4f9e-47b9-b0c2-65bca35b1a57`. Backup `b4fde29f-3944-4384-802a-bfd920ce5449` was independently restore-checked successfully without activation. Its SHA-256 is `205f5db3850897e6f3a13b0eacae7ee9941c789b3fddc1869bf9ac73dc50eb34`. No live schema upgrade, service restart, proposal rename or credential expansion was performed. The running installation shares the source directory; the new browser form checks schema before opening and displays the required-upgrade message for schema 1.

Live activation is not yet ready under the approved F01–F09 acceptance contract. Preserve the tested implementation and backup; finish the missing observations and operator acceptance before the separately scoped live upgrade. The portable repository skill describes schema2; its installed copy must be synchronized when this update is activated.
## Limits

Actual 200% zoom and screen-reader checks remain explicitly deferred by the operator for local use. Cross-platform qualification, public distribution, MCP and the two source-project migrations are separate. Current-user Windows tests do not establish protection from a compromised OS account or exhaustive cross-user/OS failure coverage. LC/AC planning matrices are not blanket security certification.

The historical home-layout proof needs retained `.local/home-integration` artifacts, deliberately excluded from Git because the business home page is private. A new clone needs an authorized sanitized local fixture before that empirical/history check; do not copy the private page or secrets into the repository to make the suite self-contained.

---

<p align="center">Maintained by Polymath Global</p>
