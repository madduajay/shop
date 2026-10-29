# Availability notification dismissal

**LIVE:** Activated together on 18 October 2026 after approved recoverable archive/reset/restart. PID 49434. Live browser checks passed; see COMBINED_ACTIVATION.md. The readiness notes below describe pre-activation testing.

Implemented and fixture-verified; not activated. Live PID 47967 was not restarted and no chat was archived or cleared. A final browser check found new active white/red shirt searches, so restart would discard in-memory conversation state and requires separate approval.

Each availability card has an accessible Dismiss button naming its product. Successful dismissal hides the card; errors retain it and announce the error in the existing status area. Mobile target measured 88.7 × 44 px, with a visible keyboard focus style.

Dismissals persist in a separate Thread-owned table keyed by authenticated customer and event ID. API requires current login and same-origin CSRF and rejects client-selected identities. Dismissal is idempotent, only accepts an event owned by the user, and does not modify the original inbox, message or trace evidence. State/poll/card responses filter dismissed cards; the frontend also suppresses stale in-flight responses and synchronizes dismissals across tabs on polling. Distinct future events remain visible. No storefront request, bag modification, authorization revocation or order is performed by dismissal.

Validation: 10 focused tests passed (dismissal, Thread authentication and trace isolation); dismissal test rerun passed with a new database connection to confirm persisted state. Coverage includes stale/duplicate delivery, repeat dismissal, CSRF, wrong-user and unknown-event rejection, per-user isolation, historical message/trace retention, new event delivery, unchanged profiles and orders. Headless Chrome fixture passed click-to-dismiss, refresh, polling persistence, a distinct future notification and mobile overflow/accessibility checks. No real-user notification was dismissed during testing.

Evidence: evidence/notification-dismissal/ui-result.json, run.log, dismiss-mobile.png. Existing live data was read-only inspected; no live restart or data mutation was performed.
