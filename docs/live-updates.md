# Live updates

[Documentation](README.md) · [Home](../README.md)

The authenticated project event stream reports committed revisions. The browser uses a bounded SSE parser over fetch so X-Ledger-UUID remains required. The shared service wakes watchers only after commit; a shared project reconciliation task checks durable state after missed wakeups. Streams do not extend session idle life. Limits are eight streams per principal, 32 overall, one pending state per subscriber, 15-second heartbeats and five-second reconciliation. Graceful server shutdown is bounded at five seconds.

The header dot is green when displayed data is current, yellow when results/context are stale, red when the selected record is stale, and gray when freshness cannot be established. Notification receipt never replaces displayed content, reorders results, moves focus or changes editor preconditions. Refresh results/context and Review changes are explicit actions. Review compares displayed, saved and draft values; rebase preserves fields and requires a separate Save. Identity changes never silently rebind a tab.

The rounded half-shaded focus square remains fixed below the header, toggling the context/results panel. The former main-detail Results and Focus buttons are removed. Keyboard controls, tooltip and pressed state express the same action. The icon is 18px at 60% resting opacity within a 44px target and returns to full emphasis on hover/focus. At 980px or narrower it disappears; the stacked panel stays visible and has no collapse toggle.

## Evidence and limits

Native Calamum tests cover post-commit ordering, replay/dry-run suppression, notifier failure, identity checks, context fingerprints, connection limits, latest-state coalescing, session idle expiry, real HTTP events, project disable and missed-wakeup recovery. Actual browser observations cover quiet red notification, yellow/green explicit refresh, fixed icon position, keyboard toggle, gray disconnect and retained-draft comparison/rebase/save.

Full LU01-LU10 qualification is not claimed: actual 200% zoom and an assistive-technology review remain to be recorded. The focused lane also exercises fragmented UTF-8/CRLF, malformed and oversized frames, wrong identity, obsolete revisions, both connection caps and a blocked network send. Node is used only for network-mocked JavaScript unit tests; the application remains Python plus browser assets, with no Node build or runtime requirement. The operator confirmed system-browser testing on 2026-10-05. Source-project migration and broad production qualification are not implied. The canonical execution contract remains the complete acceptance authority.

---

<p align="center">Maintained by Polymath Global</p>
