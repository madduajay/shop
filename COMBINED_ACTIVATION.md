# Combined activation — live

Activated positive-color eligibility, notification Dismiss and collapsed Request/Response descriptions after the user's explicit archive/reset/restart approval at 20:21 UTC on 18 October 2026. Separate demo PID: 49434. No orders submitted.

Live URLs: https://atlas.localhost:8443/ and https://jacket.localhost:8443/shop. Original https://atlas.localhost/ and https://jacket.localhost/shop both returned HTTP 200; untouched.

## Live browser verification

- Archived the active chat through Archive & clear. Archive a257a2fd9067b1a3abb3415b68ea1961 contains 4 messages and 24 trace events. Past chats opens it read-only and shows both original white/red searches.
- Dismissed the existing Red Silk Classic Tie availability card through its new button. It stayed hidden after reload and multiple polling cycles. The original inbox/watch records are unchanged; a separate per-customer dismissal record was added.
- Submitted “show me red shirts”, then “under $80”. Both return honest no-stock messages with no product cards. Rendered trace payloads confirm requested AND returned `color=red`, `include_colors=red`; budget goes from 100 to 80; products remain zero.
- Verified 22 Request/Response summaries have visible brief descriptions while collapsed. Expanded and collapsed a payload successfully. Live handler trace confirms accepted browser assertion and website-issued cookie. Screenshots contain no expanded credentials.
- Left the new test conversation open, ready to use; did not clear it again.

## Preservation evidence

SHA-256 row comparisons before and after show all 100 profiles, 6 existing orders, 1 persisted cart, 3 reviews, 100 accounts, 100 delivery records, company preferences and purchase-memory keys unchanged. All prior 14 archive rows are unchanged; one archive added (15 total). Availability inbox and watches unchanged. Expected changes are temporary shopping context from reset/test queries, a context-reset marker, the new archive and one notification dismissal. No new orders, authorization changes, payment or account changes.

Evidence: evidence/combined-activation/before.json, archived.json, after.json, all-before.json, result.json and live-color-proof.json. Screenshots: live-chat.jpg and live-traces.jpg. Pre-activation combined focused suite: 40 passed; actual GPT and disposable desktop/mobile UI tests also passed. Live verification uses the user's Chrome through the browser tool. No remaining blockers or failed product checks; an initial exact-role selector mismatch during trace inspection was resolved with the rendered summary locator.

Future restarts should preserve active conversations and saved data; this activation approval is not blanket approval to clear future chats.
