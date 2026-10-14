# Changelog

## Unreleased — Projects identity and overview

- Show selected project identity and registration metadata without Details. ID values copy on activation, with hover feedback, Copy tooltips and manual-copy recovery.
- Group data actions beside the selected name and separate access controls. Add exact revision-bound decision counts, latest activity and guarded View decisions.
- List authorized source documents as inactive links until DocDoc integration. Summary and source failures remain independent, with right-aligned Retry.

## Unreleased — full page Decisions and Projects layout

- Match Library's flat presentation with independent scrolling and per-page resize preferences. Decisions preserves record-left/browse-right orientation; Projects keeps browse-left/selected-data-right.
- Place counts beside search. Retain loaded decision counts with `+` for additional pages; Projects counts filtered visible enabled and disabled registrations.
- Keep full decision action labels with Edit, Status and Evidence first. Add compact Back navigation that retains filters, pagination, selection and scroll; preserve dirty drafts and browser history.
- Keep disabled-project administration separate from the active operational binding. Retain confirmed access changes, prepared-candidate registration and data-manager recovery; reject late results for changed context.
- Reconcile Library: move the filtered count beside search, remove its heading total and the three introductory/staging/publication passages, and remove the solid header rectangle.
- Wrap long compact project headings across the full width. Use the page's matching viewport background to keep sticky context readable without a separate panel fill.

## Unreleased — Decide dialog context

- Remove the introductory resolution explanation and the choice-switching explanation from Decide.
- Keep project name, decision ID and question visible while the dialog scrolls above 600 pixels. Preserve normal scrolling at mobile widths. Bound unusually long pinned questions so the form remains reachable.

## Unreleased — sticky Decisions heading

- Keep the existing project heading, selector and connection indicator visible while the decision section scrolls. Search and record content continue to scroll independently; no new visible controls or decoration are added.
- Preserve wrapped headings and keyboard scroll clearance at compact widths and actual browser zoom. Make Skip to content focus the main region without changing the selected decision or application route.

## Unreleased — Library browse, review and staging

- Show a plain integer displayed-row count in the main Library column; Groups counts groups only, regardless of expanded members. Staging retains its X staged label.

- Replace Library selection and Review overlay with compact Groups/Decisions rows and inline details; one open group and one open source detail. Move tags into details.
- Add flat +/− controls to group and decision rows, ordered identity-deduplicated staging, atomic group commands, bounded local Undo/Redo and explicit undoable staged-copy replacement.
- Keep copied staging visible beside browsing, or before the list at narrow available widths. Remove redundant Browse/Staging navigation. Use one unboxed Groups | Decisions toggle with the inactive label muted; use a two-choice in-place Settings menu with focused group and transfer popups so the heading cannot deform. Selection, Escape and click-away dismiss the menu.
- Add complete bounded questions to revision-pinned saved summaries for literal search, retaining compatible preview fields and response-size paging. Preserve existing publication approval, exact retries, partial receipts and native permissions.

## Unreleased — Evidence action placement and support reconciliation

- Move Evidence into the side-panel top row beside Edit and Status. Use three controls per row, including the disabled empty state; remove the duplicate action beside Evidence state.
- Retain Status for Queued/Under investigation on open decisions and clarify its help. Evidence continues to track implementation, verification and acceptance separately.
- Repair UTF-8 decision-list separators, removing the stray encoding artifact shown between identifiers, titles and work states.
- Align portable agent guidance, browser workflows, session recovery, compatibility and qualification summaries with the implemented behavior. Existing archives and compiled Setup retain their earlier source snapshots.

## Unreleased — closed decision supporting context

- Allow ordinary relationships and appended references on closed/protected closed decisions, preserving approved content and existing lifecycle restrictions. Related-to links can be removed from either endpoint.
- Add dedicated delivery Evidence controls and `decision set-evidence` partial patches through the shared browser/CLI/API rules, with clear confirmation, revision/replay protection and runtime capability discovery.

## Unreleased — stale browser sessions

- Automatically show Sign in after confirmed session expiration, including live connections, downloads and failed fetches. Retain open forms and pending requests for explicit review after signing in.
- Keep Sign out usable when its bounded server request fails, with an honest server-confirmation message.

[Home](README.md) · [Documentation](docs/README.md) · [Verification](docs/verification.md)

Changes to the local application are recorded here. This is a development history, not a packaged release announcement.

## Unreleased — deprecation approval and source controls

- Reuse normal resolution approval for deprecation, including derived current human authority and reported external approval. Retain legacy reference requests and record distinct immutable deprecation evidence without replacing the original resolution approval.
- Fix removed source controls remaining in form validation. Share applicable-control recovery and approval controls; add filtered API/CLI evidence reads and explicit older-runtime recovery limits.
- Remove the bottom narrative paragraphs from control-panel help tooltips while preserving action descriptions and interaction.

## 0.1.0a1 - Windows installer candidate

- Add current-user Windows 11 x64 Setup with pinned Python 3.14.8 and offline runtime dependencies. Add Start menu launch, optional desktop shortcut and graphical first-time setup.
- Keep application files separate from credentials, projects and Library. Repair owned bindings safely; retain data on uninstall and reinstall. Refuse foreign bindings and busy drafts. Preserve interruption evidence for repair.
- Add native compiled-installer qualification and Windows installation/support guidance. Publication and second-machine acceptance remain separate.

## Unreleased — packaging preparation

- Align browser, Library, recovery and agent guidance with completed behavior. Add a packaging/support guide and explicit source-distribution contents; qualify archive boundaries alongside fresh wheel installation. Keep version 0.1.0.dev0 and publication separate.

## Unreleased — project selector placement

- Move the shared project selector and connection-status control from the header into the existing heading area on Decisions and Projects. Preserve selection across page navigation and wrap within narrow screens.

## Unreleased — saved decisions and optional groups

- Library group dropdown, persistent decision selection and Check all; Edit/Delete are inside View. Publish records approval and finishes injected decisions closed and protected, with phase-specific replay for browser, CLI and API.

- Add a blank Library page for reusable decisions, optional editable tag relationships and staging with individual add/drop.
- Use Projects and Library as the short page labels. Reuse the application shell with Library controls above staging in the right panel, and a compact-screen panel toggle.
- Reuse ordinary question/draft forms in individual action popups. Keep staged selections across page navigation and browser Back/Forward; retain conflict review and exact pending saves.
- Publish copied content through ordinary project Change requests, retaining next numbering, repeat publication and exact retry behavior. Group metadata ends at staging.
- Add shared saved-decisions API routes and `data saved-*` CLI commands, portable current-content bundles and checked saved-history backups.
- Preserve saved drafts during conflict/unknown-outcome recovery; damaged saved storage leaves project work available.

## Unreleased — coherent refresh and modal recovery

- Refresh results stages results, selected detail, collections and context at one revision, with identity/generation guards, one retry and a 20-second deadline.
- Bind the final selected decision stream; wait for a sufficiently recent state frame before reporting refresh completion. Restore monitoring on persisted pageshow.
- Keep refresh accessible through Review workspace updates inside the editor. Comparison preserves drafts and exact pending saves; explicit rebase validates current state without saving.
- Make popup retry and sign-in reconcile without a browser reload. Keep domain-specific refresh actions scoped.
- Require actual planning links and linked-value readback for closed decisions in the portable and installed agent skills.

## Unreleased — planning-link terminology

- Rename the browser cycle to closed/link/linked, including the form, result rows and History. An owner-authorized omitted anchor displays recorded.
- Make `decision link`, `decision planning-links`, `decision.link`, `/planning-links` and anchor-aware API fields primary. Keep previous commands, routes and fields as compatibility aliases; no CLI root is added.
- Preserve schema-3 storage, immutable receipts and exact old-request retries. New operation histories require a compatible binary.
- Update current user/agent guidance and product planning. Earlier entries below retain their recorded terminology and are superseded for current usage.

## Unreleased — Apache licensing

- Add Apache License 2.0 and Polymath Global attribution, replacing the earlier unselected-license status.
- Declare the SPDX license expression and include LICENSE and NOTICE in package artifacts.

## Unreleased — planning document selection

- Define the decision-registration threshold in the public skill and user guidance, including agent-owned engineering choices and separate approval escalation.
- Expand the popup to 900 pixels while file selection is open; retain compact selection/section entry and responsive wrapping on small screens.
- Replace path-only entry with the planning document pool dropdown and Add document folder browsing/paste option.
- Load sections automatically and disable application until a valid selection is ready; retain existing root permissions and file custody.
- Add bounded, paginated read-only document discovery; no new CLI group or mutable document registry.

## Unreleased — planning application

- Add the closed/apply/applied tag cycle, a two-field planning-anchor form and immutable application receipts. Reopen resets current application while preserving history.
- Add bounded canonical planning section resolution, document/policy conflicts and owner-local anchor policy. Imports preserve evidence without granting filesystem access.
- Add `decision apply`, `decision applications` and nested `project policy show/set`; retain all ten top-level CLI groups.
- Extend explicit backup/restore-checked upgrades and native interchange to schema 3; schema 1/2 remain readable.
- Allow a superseded question's replacement to remain open, preserving the deprecation reason and relationship.

## Unreleased — explicit resolution choice switching

- Replace answer, explanation and change note when switching proposals; clear answer and explanation when choosing a written answer.
- Remove the extra edited-text preservation prompt and its focus movement. Approval details remain independent of the solution choice.
- Add public agent guidance to read and address challenge history during investigation.

## Unreleased — public source and user launch instructions

- Reflect operator-enabled public repository visibility without inventing a distribution license.
- Document runtime-only installation and the installed `decision-tracker service open` user launch command.
- Qualify fresh wheel installation, CLI startup/reuse, sign-in-page serving and safe shutdown without the maintainer's environment or development dependencies.

## Unreleased — decision wording and tooltip layering

- Rename the browser decision action and dialog title to Decide; retain CLI/API names and the closed lifecycle state.
- Raise visible control-panel help above sibling pane dividers and workspace controls.
- Refresh current interface guidance and distinguish historical verification checkpoints from current deployment state.

## Unreleased - decision page and action forms

- Grouped Controls panel, blue primary headings, stable Close/Reopen placement and uniform Edit/Retire buttons.
- Consistent New/Edit/lifecycle/item forms, structured evidence editing and clear conditional approval-source fields.
- History/snapshot toggles, protected drafts and responsive layouts.
- Native integrated regression: 107 passed; isolated Chromium includes session recovery, lost-response replay and actual 200% zoom saves. No production data upgrade or migration performed.

## Unreleased — decision approval form

- Visible proposal choices, generated decision/explanation/change note and protected edited text.
- Automatic human approval identity/time; separate reported dates with exact/date-only/unknown precision.
- Immutable schema2 approval events, guarded backup-first upgrades and versioned exchange/recovery.
- Retained-request recovery, plain errors and approval readback. Automated integration: 104 tests passed. At this historical checkpoint, live activation and revised-form owner acceptance remained pending; see later Verification entries for subsequent activation and evidence.

## 0.1.0.dev0 — internal alpha

### Decision workspace

- Central project catalog and separate SQLite decision ledgers.
- Shared lifecycle rules, immutable history, revision checks and durable request retries.
- Authenticated loopback API, comprehensive CLI and editable browser workspace.
- Candidate-only import, verified export and backup, and isolated restore checks.
- Independent Polymath home launch with a matching application shell.
- Resizable context/results panel, subtle desktop focus icon and always-visible stacked panel.
- Quiet revision notifications, freshness indicator and explicit draft comparison and rebase.

### Local access and operation

- On-demand Windows launch and reuse, 90-minute idle shutdown and bounded draft protection.
- Password setup and changes, session revocation, CLI-only recovery and separate agent tokens.
- Subtle account access, owner-local administration and protected deployment storage.
- Controlled handling of Windows connection aborts during shutdown.

### Development and documentation

- Project-local environment and native Calamum execution with retained evidence.
- Portable agent-access skill for the implemented CLI and API.
- Focused lifecycle and credential checks, integrated regression and browser observations; see the [verification record](docs/verification.md) for coverage and limits.
- Operator acceptance of password setup, system-browser use and Polymath home launch.
- Branded README, documentation site map, private security reporting and explicit environment guidance.
- Tracking boundaries and pre-push controls. Migration work remains for the next session.

---

<p align="center">Maintained by Polymath Global</p>

## Projects & data refinement — 2026-10-05

- Replace expanded administration forms with compact guided dialogs and one project table.
- Keep project selection on administration; restore decision controls only when returning to a decision.
- Add prepared-candidate discovery and preparation through shared API/CLI rules; retain legacy registration and request replay.
- Replace accumulated data output with one summary and refreshed file rows; retain safe service stop.
- Verify isolated browser recovery, responsive layouts and actual 200% zoom; activate the installed backend without changing migration decisions.

## Closed-record controls — 2026-10-05

- Enforce closed-record content/work restrictions in the shared service, API and CLI, including dry runs and atomic batches.
- Preserve historical request replay and approval history; withdraw new edit-resolution writes.
- Keep the fixed control grid, disable unavailable actions, hide child mutation controls and place Protect/Amend beside Approval.
- Scope notices to committed page navigation and preserve drafts after closure by another session.

## Unreleased — immutable legacy decision origins

- Add the packaged closed legacy-import/v1 contract, token-preserving E1 origin tables and native v4 interchange.
- Preserve original source identities, ordered history, unknowns, attribution, references and appearances separately from native approvals and transactions.
- Extend existing decision/query/data commands and read-only browser source views; retain existing CLI roots and supported native formats.
- Add durable candidate import intent/replay and digest-bound inactive export, backup, verification and independent restore checks.
- Keep sparse exceptions provenance-bound and new native resolutions strict. No live-ledger upgrade, migration execution or cutover is included.

- Correct concurrent Windows launch-lock initialization to use the existing bounded contention retry path and close failed handles.
