# Custom availability webhook — deployed and verified

Deployed 2026-10-19, separate service PID 84752. Thread: https://atlas.localhost:8443/ ; FORME: https://jacket.localhost:8443/shop ; traces: https://atlas.localhost:8443/traces . Original port-443 Atlas/jacket applications remain healthy and unchanged.

## Delivered behavior

Thread publishes its fixed callback URL in `thread_webhook` data in the initial authenticated Poppy conversation message. The subsequent standard `/messages` request activates the consented watch. New watches use `thread-forme-webhook-v1`: an autonomous FORME worker sends an actual HTTPS POST to Thread’s `/extensions/forme-availability`; no SSE connection is opened for this delivery. Standard Poppy endpoints and SSE remain supported for existing/explicit standard-mode watches.

This is a custom local-demo extension, not standard Poppy or A2A compliance. It uses the existing approved TLS private key for short-lived webhook signatures, with its certificate public key pinned at the receiver. No new persistent credential or OS trust/security setting was created. This shared-process demo does not establish independently administered company-key discovery.

Registration binds the authenticated Thread client, pairwise owner and unexpired consent. Only the fixed HTTPS origin/port/path is accepted; arbitrary destinations, queries and alternate hosts are rejected and redirects are not followed. Assertions bind issuer, audience, POST method, exact body digest, expiry and one-use proof ID. The receiver checks watch, event, customer/account, consent, grant, expiry and cancellation. Fresh retry proofs for the same event receive an idempotent acknowledgment; repeated proofs are rejected. Inbox, receipt and delivered-state writes commit atomically.

Attempt counts and exponential retry backoff persist on company watch rows. A restarted dispatcher reconstructs delivery from durable state. Cancellation is saved locally before remote cancellation is awaited. Initial registration and callback request/response appear in the Poppy trace view, with directions, descriptions, Custom extension labeling and masked authentication material.

## Verification

- Real local HTTPS integration: **1 passed**. Observed actual 503 then 200 responses, durable backoff and dispatcher reconstruction, no SSE requests, duplicate delivery acknowledgment, replay rejection, invalid issuer/audience/expiry/body, wrong account/event, invalid callback URLs and cancellation. No orders or bag changes.
- Actual GPT webhook/consent suite: **3 passed in 73.38s**, covering ties and shoes.
- Offline security/protocol/planner suite: **24 passed**.
- Standard SSE/messages, expiry and historical-card suite: **4 passed, 3 skipped** (GPT-dependent cases in an offline invocation).
- Separate actual-GPT exact-selection and malicious stale-card suite: **2 passed in 35.47s**. Earlier named variants, sign-in resume and duplicate-add safeguards remain verified.
- Mac Chrome: signed into a separate synthetic fixture, requested a tie through chat, explicitly consented and authorized FORME, observed the card after the normal one-minute restock, and inspected the actual registration and successful callback in the trace. Fixture was separate from live customer data.

Evidence: `evidence/custom-webhook-tests.xml`, `custom-webhook-gpt.xml`, `webhook-protocol-regressions.xml`, `webhook-standard-regressions.xml`, `planner-repair-exact.xml`, `custom-webhook.json`, `custom-webhook-ui-http.json`, `custom-webhook-browser-notification.png`, `custom-webhook-browser-trace.png`.

The first transport-test attempt failed before sign-in because its offline prompt was unsupported; the prompt was corrected to “show red tie” and it passed. Earlier approval-capacity failures prevented execution and are now resolved. No approval bypass or model change was used.

## Preservation and limits

The active live chat was archived through the normal UI as `f67f21e9274d3db5067016794967bc29`; all 38 prior archive payload hashes are unchanged, bringing the total to 39. Pre/post deployment hashes match for all eight non-archive preservation tables: 100 profiles, 100 accounts and addresses, 9 orders, existing carts/reviews, company context and purchase-memory keys. Saved company preference hashes also match. See `webhook-preservation.json`, `webhook-archive.json`, and pre/post deployment snapshots.

The historical mistaken sandal was not removed, and no live watch, bag mutation or purchase was created during this verification. Original Atlas health checks passed. No remaining blocker for this demo; finite tests and a shared-process local trust model are not a claim of universal protocol interoperability or distributed-service security.
