# Live updates

[Documentation](README.md) · [Home](../README.md)

The authenticated project event stream reports committed revisions. The browser uses a bounded SSE parser over fetch so X-Ledger-UUID remains required. The shared service wakes watchers only after commit; a shared project reconciliation task checks durable state after missed wakeups. Streams do not extend session idle life. Limits are eight streams per principal, 32 overall, one pending state per subscriber, 15-second heartbeats and five-second reconciliation. Graceful server shutdown is bounded at five seconds.

The dot beside the project selector in the Decisions or Projects heading is green when displayed data and a correctly bound live state match, yellow when results/context are stale, red when the selected record is stale, and gray when freshness cannot be established. Notification receipt never replaces displayed content, reorders results, moves focus or changes editor preconditions. Project/default selection binds the displayed decision key, with one stream per tab.

**Refresh results** collects filtered results, the same selected saved record, its collections and context before replacing the display. Responses must share a project identity and ledger revision. Collection retries at most once within a 20-second overall budget; a superseded or failed collection retains the previous coherent display. Filters, selection, scroll and surviving focus are preserved. Completion waits for a live frame at least as new as the collected snapshot; newer concurrent changes remain actionable. In Projects, the same action refreshes the catalog view. Artifact, candidate, planning and history actions keep their existing scopes.

While the editor is modal, use **Review workspace updates** inside the editor. It opens review above the draft. Refresh results updates results and presents a saved comparison without replacing editor fields, its saved baseline, revision preconditions or retained request. Review changes presents differences. **Rebase draft for review** explicitly installs the reviewed saved baseline/context and advances save preconditions while retaining typed fields; Save remains separate. Rebase rechecks current saved revisions and transition eligibility, and is blocked during saving or an uncertain pending outcome. Retry original save resolves retained requests first. Remote closure/protection requires the existing Reopen/Amend workflow. Without an editor, **Use latest** invokes coherent refresh.

**Retry connection** waits for verified readiness and reconciles data without a page reload; it stays in the popup until the outcome is known. Controls adapt to connection changes while the popup is open. Refresh remains available during transient disconnection when authorization is usable. Expired sessions offer explicit sign-in, while permission or identity failures remain unavailable. An explicitly stopped service retains its Start action. Persisted page restoration resumes monitoring without automatically replacing data or drafts.

The rounded half-shaded focus square remains fixed below the header, toggling the context/results panel. The former main-detail Results and Focus buttons are removed. Keyboard controls, tooltip and pressed state express the same action. The icon is 18px at 60% resting opacity within a 44px target and returns to full emphasis on hover/focus. At 980px or narrower it disappears; the stacked panel stays visible and has no collapse toggle.

## Evidence and limits

Native Calamum tests cover post-commit ordering, replay/dry-run suppression, notifier failure, identity checks, context fingerprints, connection limits, latest-state coalescing, session idle expiry, real HTTP events, project disable and missed-wakeup recovery. Actual browser observations cover quiet red notification, yellow/green explicit refresh, fixed icon position, keyboard toggle, gray disconnect and retained-draft comparison/rebase/save.

Full LU01-LU10 qualification is not claimed: actual 200% zoom and an assistive-technology review remain to be recorded. The focused lane also exercises coherent selected-detail/context refresh, modal comparison/rebase, uncertain-save replay, popup recovery, persisted restoration, navigation cancellation, two-attempt consistency failure, a 20-second deadline and scoped catalog refresh. It also exercises fragmented UTF-8/CRLF, malformed and oversized frames, wrong identity, obsolete revisions, both connection caps and a blocked network send. Node is used only for network-mocked JavaScript unit tests; the application remains Python plus browser assets, with no Node build or runtime requirement. The operator confirmed system-browser testing on 2026-10-05. Source-project migration and broad production qualification are not implied. The canonical execution contract remains the complete acceptance authority.

---

<p align="center">Maintained by Polymath Global</p>
