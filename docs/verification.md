# Verification state

## Planning document dropdown and browsing — 2026-10-06

Final resource-bound proof `20261006T053207Z-dt-applications` passed **97 tests**, including a changing-file test that underreports stat sizes while actual reads exceed the aggregate budget. Inventory now charges actual bytes. Source remains unchanged in `.local/proofs/55639220522a4730a2610911f92903eb`; the thirteen browser checks remain passing. Final safe activation is instance `d6ef6fa0-7d33-422a-9550-16110d1d31b8`, recorded in `.local/document-browse-final-activation-20261006/activation.json`. The same 16-document discovery, migration section preview, unchanged records and matching served assets were rechecked. This supersedes the intermediate source/activation state below.

Native `20261006T052355Z-dt-applications` passed **96 tests**, including document discovery, retained-path pool membership, nested navigation, denied outside/redirected roots, missing local permissions, enumeration bounds, changed-inventory cursors and Unicode response-size limits. The browser recorded **13 checks** with no page errors: pool selection, Add document navigation/Cancel, pasted missing paths, disabled Section/Apply, late section responses, changed files, application lifecycle, prefill and 320-pixel horizontal layout. Narrow selector and applied-state screenshots were inspected. Final action-form proof `.local/proofs/45b6fb8feaf049d0aed0aed6a6350361` passed four tests. Runtime, tests and public skill match the retained source manifests. The supplied skill validator passed and the installed skill is synchronized.

The failed first run `.local/proofs/f0ea0d1d49174fde924bc16d434eaf0c` remains retained: the test removed an intercepted request before releasing it, causing a Playwright double-handling error. The corrected test preserves its late-response assertion. Final application proof is `.local/proofs/b270001100124af3a2b308d3fe191485`.

Safe restart activated instance `807ec91e-543c-42f3-abb9-c5f2815f2c5a`. Read-only live checks discovered 16 canonical documents, including the migration plan, verified its section preview and registered-root navigation, and matched three served assets byte-for-byte. The pilot remains schema 3, revision 12 with ten unchanged decisions. Required-anchor policy revision 1 is unchanged. Activation evidence is `.local/document-browse-activation-20261006/activation.json`. No decision/application/policy/credential write, import or remote push occurred. Operator browser testing remains separate from these native and installed-service observations.

## Planning application and browser sessions — 2026-10-06

Schema 3 planning applications are implemented and enabled for the migration pilot. The status row uses lowercase `apply`, matching `closed` and `applied`. Both browser authentication paths expire after 90 minutes idle or 8 hours absolute; passive events and draft leases do not extend browser idle time.

Native integration `20261006T045522Z-dt-integration` passed **182 tests**. After the final label and timeout changes, `20261006T050144Z-dt-applications` passed **92 tests**, including exact idle/absolute boundaries, application lifecycle, anchor/policy conflicts, immutable provenance, upgrade rollback/crash recovery and the isolated browser workflow. Final action-form proof `20261006T050256Z-dt-action-forms` passed **4 tests**. Each run retained source manifests and unchanged proof-copy evidence. Final runtime and portable-skill bytes were checked against the focused proofs. The application browser recorded ten checks with no page errors; inspected screenshots cover matching translucent tags and the soft green noninteractive applied state.

The managed backend restarted safely as instance `66ff2d4e-f362-41e9-af55-d90c9fbf97fb`. Explicit schema 2-to-3 upgrade retained backup `fa4f6f31-9d01-4803-8376-6214be7f7b72` after independent restore verification. The pilot remains ledger revision 12 with ten unchanged decisions and unchanged transaction history. Owner-local policy revision 1 registers the existing authoritative planning directory and keeps anchors required. Three served application assets match local bytes. Activation evidence is `.local/application-activation-20261006/activation.json`; no application receipts or source-project imports were created.

The supplied skill metadata validator passed through native Calamum after its missing YAML dependency was installed in the ignored development environment. The installed skill matches the public skill; previous bytes are retained. Failed integration timing assertions, missing-validator-dependency output and activation evidence-collection attempts remain retained. The browser timing guard was corrected before the passing integration run. These observations do not establish full assistive-technology qualification or operator acceptance. Anchor/hash checks do not prove semantic incorporation or generator verification. Remote push remains held until pilot completion.

[Documentation](README.md) · [Home](../README.md)

Internal alpha for local use. On 2026-10-05 the operator confirmed successful password setup, testing in the system browser and launch through the Polymath home card. This is operator-reported acceptance, separate from agent-observed and automated proof. No real source project has been migrated.

## Reading this record

The latest resolution-choice proof is native `dt-action-forms`, retained at `.local/proofs/b0162b559d8d4816a27cebd0a1e4de40`. Isolated Chromium recorded 30 checks with no page errors. It verified switching to a written answer clears answer and rationale and resets an edited change note; switching to another proposal replaces all three fields, including when a benefit is absent. The extra preservation prompt is removed and selection does not pull the dialog downward. Saving the selected proposal, session-expiry recovery and conflicting-update draft retention also passed. Runtime and browser-test hashes match the proof copy. This supersedes earlier descriptions of edited-text protection when explicitly switching solution choices.

Public source visibility was verified after the operator changed the repository setting. User-installation proof `.local/proofs/a892b22b0b844caeae24da6e02b703d8` passed through native `dt-package` with source unchanged: a new wheel installation used runtime dependencies only (no Calamum or test runner), the installed console script started and reused an isolated managed service, HTTP served the sign-in page, and safe shutdown completed. The `service open` command was exercised with only browser dispatch stubbed. This is Windows package/CLI launch evidence, not a cross-platform or real-browser external-protocol qualification. Subsequent changes document these results without changing tested runtime or package behavior.

The dated sections below preserve historical checkpoints. Statements about schema 1, revision 1, missing zoom evidence or pending activation describe their checkpoint, not current deployment state. Later sections supersede those specific limits where evidence is provided. Current project revisions and permissions must be read through the service; they are operational data and are not maintained in this portable document.

The browser now labels the resolution action **Decide**. Earlier references to the Close button describe its former label. The CLI/API operation and the `closed` state are unchanged.

## Tooltip and Decide wording — 2026-10-05

Native integration `20261006T021525Z-dt-integration` passed **152 tests** with source unchanged during execution; retained proof is `.local/proofs/39d0207be1384583a3f009f2514e6814`. Focused native browser/form proof `.local/proofs/80ab35560ffd40c1b30fb307c945420d` verifies the Decide button and dialog title, visible-tooltip hit testing across its footprint, lifecycle workflows and actual 200% browser zoom. The tooltip screenshot was inspected and shows uninterrupted help above both pane dividers.

An initial added coverage assertion ran with help hidden and was therefore insufficient. The corrected check explicitly waits for visible help before hit testing; both attempts remain retained. Installed-service reads returned matching bytes for the three changed UI assets. This establishes served-source correspondence, not operator acceptance. The final verification-note addition is documentation only; runtime, tests, tools and catalog remain identical to the integrated proof.

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

## Decision-page layout and action forms — 2026-10-05

Native run `20261005T145013Z-dt-integration` passed **107 tests** with source unchanged. Proof: `.local/proofs/ea82cd7f9cf04108b206e4893a7e5d52/proof-manifest.json`. Final UTF-8 punctuation correction and line-ending normalization are verified by the focused action-form proof retained in the final implementation evidence.

The isolated Chromium workflow recorded 21 named checks spanning New/Edit, structured evidence clearing, option/reference operations, rejected-option requirements, relationship/unlink, lifecycle actions, Close/Edit resolution, item retirement, history/snapshot toggles and late-response cancellation. Session expiry preserved the draft through reauthentication; a lost save response replayed the identical request. Wide and 320-pixel layouts, keyboard focus/Escape, and actual browser zoom at 200% were exercised. New decision and Close both saved at 200%. Screenshots were inspected. This supersedes the earlier lack of actual zoom evidence for these tested scenarios; it is not blanket assistive-technology certification.

The current page refinement is ready for operator reassessment. The operator previously accepted the Close form's appearance; this is not acceptance of every revised workflow. No active-project schema upgrade, migration, credential change or remote push was performed. Earlier deployment facts are historical and must be rechecked before any future activation.

Retained failed attempts include UTF-8 subprocess capture, an unavailable default browser binary, a test expecting immediate checkbox clearing despite the confirmation step, and an assertion racing the post-save refresh. The final source-corresponding run passed. Browser/package locations remain in ignored local configuration.

## Compact control size limits

Operator-directed sizing: preserve each row's proportions while shrinking to a floor. Three-column buttons retain a 2:1 ratio and minimum 64 by 32 CSS pixels; Edit/Status retain 3:1 and minimum100 pixels wide. The controls footprint is bounded between240 and280 pixels. Below the minimum viewport width, overflow preserves geometry instead of squeezing or wrapping buttons. Native focused proof `.local/proofs/27e000695f904c9aad3a7f127ef7372d` passed four tests, including measured ratios at sidebar resize limits and a220-pixel viewport. The one panel tooltip and History toggle remain covered.

## Panel help formatting and centering

The single panel tooltip uses aligned abbreviation/description columns, full action names where needed, and subtle dividers in button order. The bounded control group is centered horizontally within wider panels. Native focused proof `.local/proofs/b9117ac241f34588a71f96a2b9b93798` passed four tests with unchanged source, including tooltip ordering and measured centering. The rendered tooltip screenshot was inspected.

## Projects & data — 2026-10-05

A1–A10 are implemented. Native integration run `20261005T170007Z-dt-integration` passed **112 tests** in 154.33 seconds, with source unchanged during the run. Proof: `.local/proofs/4681648700fc47efb6c405b966c86854/proof-manifest.json`. Application, test, catalog, tool and portable-skill hashes were compared again before publishing the canonical checkpoint.

The new isolated Chromium workflow records 13 checks: compact administration, name-generated IDs, protected catalog drafts, Results navigation, stable project scope, data/file refresh, exact-request replay, disabled selection, prepared-candidate registration, reauthentication, delayed responses, separate Stop confirmation, 320-pixel layout and actual 200% zoom. Wide, narrow and zoom screenshots were inspected. Candidate API/service tests cover preparation, changed content, receipt validity, pagination, permission and registration contracts. Existing decision-page tests passed in the same integrated run.

Earlier attempts are retained: text encoding was corrected; navigation assertions were made to wait for completed responses; a delayed-response test released its browser route in the wrong order and was repaired. The final integrated run has no failures. Full screen-reader qualification and operator acceptance are not asserted.

The installed service was safely stopped and restarted as instance `53216545-f8f3-42bf-89ec-7c380d2b4a8b`. Read-only live checks verified the candidate endpoint and byte-for-byte matching index, app, projects and stylesheet assets. The migration project remains schema 2, revision 1, with seven unchanged open decisions. No production registration, import, decision write or schema upgrade occurred. Activation receipt: `.local/projects-data-activation/activation.json`. This is installed-service verification; mutation workflows were tested using isolated data.

## File managers, navigation and persistent controls — 2026-10-05

Native integration proof `.local/proofs/5af0aaf3f3c34f12b7196156a21622e0` passed **116 tests** with source unchanged. Final focused proof `.local/proofs/0f9939bc2e7044b2b8d5d101b9c747ef` passed **11 tests**, matching current runtime source after the final administration footprint CSS adjustment. The focused browser exercises separate managers, radio selection, reset on page/size changes, saved page size, real previous/next paging, stale inventory, unknown creation without duplicate submission, late responses, a bounded 100-row layout fixture, 320-pixel layout, and actual 200% zoom geometry. Wide, narrow and backup-result screenshots were inspected. Compositor screenshots at actual zoom were unreliable; they are retained and are not claimed as visual evidence of the complete dialog. Zoom geometry confirms the dialog and footer fit the visual viewport. Existing decision/action proof remains retained.

Creation timestamps use two unbroken date/time lines. Each page retains its control pane; an empty decision project displays a disabled grid, and entry defaults to the first open decision by key with first-existing fallback. Valid explicit decision URLs remain honored. The favicon bytes match the existing Polymath/Accounts favicon. Conservative contrast analysis over the brightest possible watermark supports opaque labels and the brighter border.

Installed service restart is recorded in `.local/file-manager-activation/activation.json`: instance `aaf2637b-d91e-4bdf-a314-c2eb1115e977`, new manager paging verified, and eight served assets match local bytes. The migration ledger is schema 2, revision 1, with seven unchanged decisions. No production artifact, registry, decision, credential or schema writes occurred. Native mutation testing used isolated data. Operator reassessment remains separate.

Retained failures: an API test expected 400 rather than the established 422 status; an action test selector included the hidden administration pane; zoom screenshot capture required separate geometry qualification. Canonical business evidence is under `planning/evidence/file-manager-implementation-20261005` in Polymath custody.

## Closed-record policy checkpoint — 2026-10-05

Shared ordinary/content and work-state guards are implemented across browser, CLI and API. Reopening must commit separately before editing. Lifecycle transitions, generated lifecycle links, historical approval reads and exact committed-request replay remain valid. New edit-resolution requests are rejected; no data migration is required.

Native integration `20261005T191157Z-dt-integration` passed 152 tests with source unchanged. Focused policy evidence is `.local/proofs/5714b68c686f4ec081f15d5667cd9aee` (77 tests). Browser proof `.local/proofs/25a683e746024e2d848f90153545db3d` passed four tests, including the fixed grid, lifecycle placement, notice navigation, retained drafts after remote closure, History toggles and actual browser zoom saves. A final focused browser proof qualifies subsequent search-notice and live-review draft guards. Earlier failures are retained and were corrected without weakening policy requirements. Actual activation and final source correspondence are recorded in the canonical closed-record implementation checkpoint; operator acceptance remains separate.
