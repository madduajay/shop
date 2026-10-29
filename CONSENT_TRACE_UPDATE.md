# Consent wording and collapsed trace update

Status: LIVE after Ajay’s explicit activation approval on 18 October 2026. Current chat recoverably archived and pending add session reset; service restarted as PID 47967. All protected saved-data hashes and prior archives preserved. Live browser verification confirmed collapsed payloads, expansion/collapse and recorded directions across 112 archived trace cards. No orders placed. Evidence: evidence/consent-trace/activation/result.json.

Observed cause: current rendered Poppy traces show a successful signed-in token carrying availability:watch and repeated controlled-browser account_status observations for forme_customer_001. Add-to-bag requires orders:write under the existing storefront policy. Thread conflated missing permission with missing authentication: both its add explanation and hard-coded popup button said “Sign in with FORME.” The existing company authorizer cookie already supports reuse of the authenticated identity, but the page heading also misleadingly asked to sign in.

Changes:
- Signed-in add requests explain additional shopping permission and retain the pending selection without mutating the bag before consent.
- API supplies Review FORME permissions for an authenticated flow; the button uses it. Signed-out flows retain Sign in with FORME.
- A valid matching authorizer login shows Review additional permissions, no credential inputs, and an explicit Authorize additional access action. Existing account matching, CSRF, scope approval, session binding and order-review protections remain.
- Trace Request/Response payloads are independently collapsed by default. Their summaries show the recorded caller/recipient and label return traffic “reply to this request.” Unknown historical directions are not guessed. Browser/Poppy categorization, masking, provenance and account isolation remain.

Validation:
- 12 focused trace, purchase-flow and Thread-auth tests passed, including button-label state, historical unknown direction and request/response collapse markup.
- Actual GPT headless trace fixture passed: expansion/collapse, desktop/mobile overflow, archives, credential masking, unchanged 100 profiles and zero orders. Screenshot: evidence/consent-trace/thread-traces.png.
- Actual GPT notification → consent → add fixture passed with two real model calls, same protocol session, credentials entered once, explicit incremental consent, one tie in the bag, duplicate-add prevention, 100 unchanged profiles and zero orders. The completed diagnostic retry fast-forwarded only the synthetic availability clock. An earlier real-time restock run reached the bag but its assertion expected a name without the rendered “ · red” suffix; corrected assertion matches the actual product label.

Evidence: evidence/consent-trace/result.json, run.log, trace-run.log and screenshots. No credential values are included.
