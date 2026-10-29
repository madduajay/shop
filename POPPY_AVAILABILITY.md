# Availability messages and events

The demo uses Poppy draft 0.2 §7 conversation messages and authenticated Server-Sent Events, as specified at https://personalagentprotocol.org/docs/0.2/spec. Thread discovers FORME’s advertised Poppy conversation endpoint. It sends a standard `Message` with a stable ID only after the user opts into an existing availability offer and authorizes `availability:watch`. The `forme_availability` object inside `message.data` is FORME application data, not a new protocol field or method.

FORME creates a durable watch bound to the verified client, pairwise user and signed-in account. Thread opens `GET /poppy/conversations/{id}/events` with the SDK’s DPoP authentication and `Accept: text/event-stream`. FORME advances its synthetic restock clock and emits a standard company-role message event over that connection. There is no invented webhook endpoint. Browser availability polling is no longer the notification transport. Thread UI refresh only displays messages already received by its server-side listener.

Conversation ownership and message-ID/content conflicts are enforced by the SDK. Conversations and message receipts persist in a separate SQLite database; session credentials do not. Streams check the exact session token for expiry/revocation, close on disconnect, and reconnect using Last-Event-ID. Bounded SDK reconnects and a 15-second retry backoff prevent tight retry loops. Inbox events have a customer/event unique key; cursor advancement follows durable inbox insertion. Cancelled/expired watches do not generate new notifications, and notification dismissal persists. Existing browser-created watches can attach to a Poppy conversation using their original consent ID without creating a duplicate watch.

Catalog discovery, product details, bag changes, order review and explicit simulated checkout continue through the controlled browser. A notification never places an order.

# Browser activation trace

The controlled Chrome process captures the activation POST using `Network.requestWillBeSent` and `Network.requestWillBeSentExtraInfo`, and its intermediate response using `Network.responseReceivedExtraInfo`, before following the redirect. The Poppy trace shows the real 303 status, Location, and Set-Cookie name and attributes. Credential values remain masked. Response bytes captured by the company handler are correlated with Chrome using X-Atlas-Capture-ID; they are not reconstructed from the final page. When Chrome can provide a non-redirect error body, it is captured with Network.getResponseBody. Unavailable bodies are explicitly labelled.

The server-side capture is merged into a single browser-carried Poppy exchange; ordinary follow-on storefront navigation is not represented as another activation. Request/response sections remain collapsed, with full captured non-secret headers/body, timing and direction available on expansion. SSE responses retain their actual received event frames. Older archives are preserved as historical evidence and cannot acquire network fields that were never captured.

## Verified deployment — 2026-10-19

Live separate service: PID 72644, https://atlas.localhost:8443/ and https://jacket.localhost:8443/shop. Full final regression: **337 passed, 7 skipped, 0 failed** (`evidence/poppy-final-tests.xml` and `.log`). The seven skipped checks require actual GPT credentials in the test process; the live service retains its existing configured model. The earlier trace-validation metadata regression was corrected and its focused rerun passed.

Actual Chrome verification exercised an isolated customer 099 on temporary port 8447: unavailable red tie → explicit chat opt-in → scoped FORME sign-in → Poppy subscription → real-time event → image notification → dismissal → reload with dismissal retained. No simulated purchase was made during this UI check. The temporary server and tabs were closed. Isolated automated tests also verified duplicate delivery suppression, cross-user conversation rejection, cancellation, restart recovery, cookie issuance and invalid-assertion failure.

The user's 21-message live conversation was saved as archive `59132639859e05bab9c10357998eb591`. All 32 older archives and eight customer/commerce tables were hash-verified unchanged, including 100 profiles and nine existing orders. Both original port-443 apps returned HTTP 200. Evidence: `poppy-deployment-verification.json`, `poppy-availability.json`, `poppy-after-deploy.json`, `poppy-303-browser.png`, `poppy-restock-event.png`, and `poppy-restock-notification.png` in `evidence/`.

## Consent-loop regression fix — 2026-10-19

The archived failing GPT trace (`2fdaaad807f88225209134c9b426b96e`) showed catalog search returning an availability offer, followed by attempted subscription, an extra consent prompt, unsupported_question, and another subscription attempt. The harness had no explicit waiting-for-user boundary.

The harness now stops after an offer (`waiting_user`) or authorization request (`waiting_auth`). A pending consent ID binds natural affirmative/negative replies to one specific offer; unrelated conversation invalidates that conversational binding. Authorization resumes its bound consent ID once. Repeated approvals use the existing watch, and a rejected or unsupported step cannot keep looping after the consent question. Repeated successful tool actions are suppressed while retaining the existing result instead of appending the generic repeated-action error. The availability workflow instructions were updated to version 1.0.1.

Verification: 33 targeted checks passed, plus two GPT-enabled parameterized journeys passed (30 actual calls to gpt-4.1-mini-2025-04-14). Both red shoes and red tie were exercised with missing authorization and existing authorization, yes/notify me/no, repeated approvals, SSE delivery, dismissal, and unrelated assent. No verification check was skipped in these selected runs; one purchase-producing agent journey was deliberately deselected. No test purchase or live subscription was created. Screenshots: `evidence/consent-single-offer.png` and `evidence/consent-auth-pause.png`. Reports: `consent-root-cause.json`, `consent-gpt-shoes.json`, `consent-gpt-tie.json`, `consent-targeted-tests.xml`, and `consent-gpt-tests.xml`.

Deployed PID 74469. Original port-443 sites remain healthy. Eight customer/commerce table hashes are unchanged, including 100 profiles, nine orders and three carts. All 33 prior archives remain unchanged; the failing conversation is preserved as the 34th archive. Current Thread sign-in remains customer 003.


## Conversation visibility fix — deployed 2026-10-19

The missing conversation POST was caused by an old availability offer expiring during sign-in (offer expired 01:51:52 UTC; authorization completed 01:52:38 UTC). The trace filter was correct; no conversation request had been sent. Repeated searches now refresh an offered notification through the browser, and explicit consent starts a separate bounded ten-minute authorization window. Expired consent now reports the recovery step and leaves the task awaiting the user rather than falsely completed.

Deployed separate service PID 75570. Thread: https://atlas.localhost:8443/ ; FORME: https://jacket.localhost:8443/shop ; traces: https://atlas.localhost:8443/traces . Original port-443 services both returned 200.

Verification: 46 targeted regressions passed (visibility-regressions.xml); two actual GPT journeys passed (consent-gpt-tests.xml), exercising shoes and ties, consent, delayed authorization crossing the original offer expiry, POST 201, and event-stream delivery. An initial GPT attempt had one transient incomplete catalog turn; the subsequent two-case run passed. An initial combined regression invocation had three fixture-port failures; corrected fixture initialization passed all 46. No full-suite rerun or purchases in this change.

Actual Chrome verification in an isolated fixture rendered the Thread-to-FORME conversation POST/201 and incoming restock SSE message, with details collapsed by default and correct directions. Evidence: visible-poppy-messages.json, visible-poppy-subscription.png, visible-poppy-restock-event.png. Fixture server and tabs were closed. No live notification was created.

All eight customer/commerce table hashes stayed identical, including 100 profiles and nine existing orders. All 34 prior chat archive payloads are unchanged; the failed conversation was recoverably archived as e07e3a9aacc799cab7def01234b2d3c4, bringing the total to 35. Live Thread reloaded successfully with the original customer and draft preserved. A fresh search and explicit consent are needed to create the requested notification; the expired attempt was not silently replayed.
