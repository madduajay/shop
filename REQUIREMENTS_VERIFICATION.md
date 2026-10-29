# Thread × FORME — consolidated requirement verification

This report reconciles the original build request and subsequent refinements. Latest instructions take precedence: sign-in is required when adding to the bag, and ordinary preference capture stays in Thread until explicitly shared. Status describes finite evidence, not a guarantee that every possible input is bug-free.

## Delivered application

- Thread: https://atlas.localhost:8443/
- FORME: https://jacket.localhost:8443/shop
- Separate traces: https://atlas.localhost:8443/traces
- Original apps remain at https://atlas.localhost/ and https://jacket.localhost/shop.
- Synthetic logins: customer001–customer100@thread.local and corresponding @forme.local accounts; demo password `wardrobe`. Changing customer requires signing out/in, not merely typing a different customer number.

## Requirement matrix

| Requirement | Status | Evidence and limits |
|---|---|---|
| Separate app; preserve existing Atlas and jacket store | PASS | Separate workspace and port8443. Both original443 URLs return200. Existing SDK reused read-only. No OS trust/security change. |
| Preserve existing records and current conversation | PASS | Approved archive contains13 messages and56 trace events; visible in Past chats after restart. Nine persistent table checksums unchanged: `evidence/cart-deployment-preservation.json`. |
| 100 isolated durable synthetic profiles | PASS | All100 parameterized memory persistence tests; all100 login checks; company context restart/isolation. `comprehensive-tests.xml`. |
| Shirt, waist, shoe size, colors, fabric quality, price range, brands, fit, material, occasion, style | PASS | Profile fields, explicit editing, budget validation, per-customer persistence. Extra width, inseam and exclusions. |
| Realistic sizes and fit | PARTIAL | Explicit US apparel/shoe and inch waist variants, stock checks. UK/EU preferences can be recorded but unsupported size systems do not silently convert. Only standard-width footwear stocked; no fit guarantee. |
| Chat-only personal-agent interaction | PASS | Chat selection and inline product dialog/add; no default navigation away from Thread. Authentication occurs on FORME-owned popup. |
| Sleek compact Thread; consistent professional retailer branding | PASS, SAMPLED VISUAL | Shared FORME logo/CSS across storefront and login. Desktop/mobile screenshots; polish is a visual judgment, not mechanically provable. |
| Clothing AND footwear with international variety | PASS | 1000 listings:800 clothing,200 shoes; men/women.38 generated style families,15+ inspiration regions. Kurta/haori/guayabera/kaftan plus geta/jutti/babouches/huaraches/espadrilles etc. Inspiration labels do not claim provenance. |
| Product images match item/color on both surfaces | PASS FOR MAPPING; SAMPLED VISUAL | All992 expanded listings map to matching family/color/material metadata and38 served images. Thread reuses storefront image URLs. Six legacy photos and two availability images checked separately. Not1000 unique photos; every image/listing combination has not been manually reviewed. |
| Rich filters, details, stock variants, pagination | PASS |18 browser controls plus combination/empty cases, sorting/reset/Next; stock/variant validation. `filter-matrix.json`. |
| No unsupported empty filter choices; footer spacing | PASS FOR TESTED STATES | Dependent positive-count facets; invalid combinations render honest empty state. Mobile390px width,40px pager spacing. Exhaustive Cartesian filter combinations not tested. |
| Deterministic selection; concise GPT explanations grounded in current/company context | PASS | Eligibility/ranking deterministic. GPT selects bounded supported facts, server renders reasons. All1000 deterministic fallback lengths verified; live GPT sample previously15words each. Does not promise independent garment-quality assessment. |
| Distinct Thread/FORME identities and memories | PASS | Independent logins, account linkage and scopes; local profile reads do not browse FORME. Empty company context remains empty until explicit sharing. Cross-account and archive authorization tests. |
| Temporary vs lasting preferences; current request precedence and expiry | PASS | Scope/expiry/request binding tests, restart persistence, clear cancels temporary context, no automatic promotion from filters to lasting preferences. |
| Generic user-context questions, honest unknowns | FINITE COVERAGE | Read-only native tool calls, server-bound identity/allowlists, evidence/source checks. Unknown general requests use exact `Sorry i am not sure how to handle this request`; missing personal facts state unknown. Arbitrary model paraphrases cannot be exhaustively guaranteed. Current live-GPT fixture acceptance passed with25 actual model calls and0 orders. |
| Add-to-cart sign-in, cancel/resume once | PASS | Pending-add cancellation, mismatched-account rejection, authorized resume, duplicate prevention. Supersedes earlier checkout-only login behavior. |
| Actual Poppy controlled browser | PASS | Website navigation/forms; signed top-level assertion POST; website-issued cookie. No cookie injection or purchase API. Browser client and server trace corroborate activation/cookie use. |
| Discovery URL distinct from activation | PASS | Application `/storefront.json` yields `/shop`; protocol `web.browser_session_endpoint` is separate. No invented discovery field is presented as Poppy standard. |
| Signature, audience, binding, expiry, replay, return URL, cookie scope | PASS | Actual browser/assertion tests reject wrong signature/aud/user/session, expired/overlong expiry, replay, disallowed return URLs. Secure HttpOnly SameSite=Lax host-only Path=/ cookie. Current draft spec checked at https://personalagentprotocol.org/docs/spec. |
| Shared persistent account cart between Thread and ordinary FORME | PASS | Fixed split ephemeral/persistent cart. Two actual browsers verify add visibility and quantity edits in both directions; fresh Thread login reconnects. Stale revision and duplicate add submissions rejected. `shared-cart-browser-ui.json`, `shared-cart-verification.json`. |
| Recovery after fresh session/restart | PASS IN FIXTURE; LIVE FINAL STEP BLOCKED | New bag/checkout flow connects before claiming empty. Expired sessions reopen; persistent bag survives new app instance. Real user browser reaches company consent prompt; auto-review blocked final live authorization. |
| Explicit approval and duplicate-order prevention | PASS | Review required; stale approval/review/cart revision/address rejected; repeated checkout idempotent. Current synthetic purchase UI rerun passed:exactly1 fixture order,repeat approval rejected,all100 profiles unchanged; plus protocol integration test. No real payment/delivery integration. |
| Company addresses, own order history | PASS |100 distinct synthetic saved addresses; review displays quantity/currency/address; read-only in Thread. Own orders only; direct retailer permits address edit. |
| Red shoes/tie availability demo | PASS WITH APP-SPECIFIC LIMIT | Real one-minute fixture timing previously verified for both; opt-in/cancel/reconnect/expiry/dedup regression. Polling requires running app/browser session; not native Poppy push or an external notification service. |
| Separate concise expandable traces; no screenshot secrets | PASS | Authenticated traces route, source/protocol labels, redaction allowlist, archive ownership, clear and mobile tests. Screenshots show rendered content; raw sign-in ticket URLs excluded from deliverable screenshots. |
| Actual rendered flows in user's browser | PASS UP TO LIVE CONSENT | Original archive visibly recovered; current Thread loads; FORME ordinary cart verified. Live reauthorization could not be completed without approval. Fixture headless Chrome verifies full purchasing flow. |
| No real purchases, external publication, persistent external credentials, account changes | PASS / LIVE AUTH BLOCKED | Only synthetic fixture orders; no payment/delivery. Existing local TLS reused. Live authorization was rejected and not bypassed. |

## Current regression evidence

`evidence/comprehensive-tests.xml`: **256 passed,0 failed,0 skipped**,120.10seconds. Includes preference/auth/protocol/filter/stock/cart/checkout/scopes/availability/traces tests.

New `verify_shared_cart_ui.cjs`: PASS after correcting the test assumption that clearing chat logs out. It now opens a fresh Thread login, reconnects through FORME, reads the persisted quantity2, creates0 orders and leaves all100 profiles unchanged.

Two initial live-GPT runs stopped at additional company consent and reported “Combined sources missing”; the diagnostic output showed an authorization prompt, not a completed answer. The corrected acceptance test handles additional scoped consent in its disposable fixture and PASSED:25 live GPT calls,0 orders,all100 profiles unchanged (`context-qa-live-model.json`). The temporary response-format experiment was removed; application behavior was not changed for that harness failure.

Earlier evidence files are historical, not interchangeable with this report. In particular `photo-verification.json` describes an earlier17-family image iteration; the current catalog has38 matching families, verified by the current regression. `final-readiness.json` previously reported254 tests and must not be used as the current overall result.

## Remaining limits and blocker

No zero-bug guarantee is possible. Model wording, every possible natural-language request, all filter combinations, long-duration concurrent load, all browsers and all1000 individual product visuals are not exhaustively tested. This is a local synthetic demo, not a production security audit or arbitrary-retailer browser agent.

Live saved-bag authorization is pending. Automatic approval review rejected clicking **Authorize & connect** for the live FORME account because it grants Thread order-history access and the request prohibited account changes. No workaround was attempted. Specific user approval is needed to finish that live step. Fixture authorization/checkout checks are unaffected.

## Final approved live verification

After explicit user approval, the renewed customer001 connection granted only `orders:read` and succeeded. Both company sign-in popups auto-closed. Thread, the signed-in ordinary storefront and SQLite agree: current bag empty (revision11); customer1 has two existing orders—Oxford white L ×1,USD59 (`FM-F6C268CB`), and Tee white M ×1,USD32 (`FM-B11A5441`). No customer2 order leaked. No bag edit, review creation or purchase occurred.

The bag had already changed from the earlier three-line revision7 snapshot before this authorization. It was not restored or modified by verification. Profiles,orders,reviews,accounts,addresses,company memory/activity and purchase-memory keys were unchanged during the read checks; the original archive byte hash still matches. Customer1 cart contents stayed empty. Ordinary sign-in incremented its revision10 to11; cart-table metadata changed, so the cart table was not byte-for-byte unchanged. See `evidence/final-live-read-verification.json`. Earlier blocked-status rows above are superseded by this completed live verification. No remaining permission blocker; existing sizing/visual/model/coverage limits remain.

## Newly reported negative-color gap

The earlier suite missed negated colors. The live request `show me a shirt - not white color` incorrectly became a positive white filter. This supersedes any implication that the earlier filter checks covered negative preferences. The fix adds hard exclusions across parsing, memory, browser form and retailer eligibility; see `COLOR_EXCLUSIONS.md` and its specific regression evidence. Tested on disk; live activation pending preservation of the active conversation.

Final negative-color regression: **272 passed, 0 failed, 0 skipped** (127.606s). The live-GPT fixture made 8 parser and 3 explanation calls, preserved all 100 profiles, and created no orders. This correction remains **tested, not deployed**; post-activation live smoke testing is pending approval to archive the active conversation and restart. See `COLOR_EXCLUSIONS.md` and `evidence/negative-colors-readiness.json`.

Activation update: approved archive/restart completed; PID 16831 serves the fix. Post-activation isolated live-GPT browser checks passed; live Thread login and archive rendering, FORME exclusion control, and original Atlas availability verified. Protected record checksums match. No new grants or purchases. See `COLOR_EXCLUSIONS.md` for precise preservation scope and fixture/live distinction.

Semantic bag lookup fix: **276 regression tests passed**, including color exclusions, shared-cart persistence and identity isolation. Live-GPT headless UI passed the exact `baf` typo, bag/cart/basket paraphrases, follow-up context and normal read-only authorization/resumption. Fixture cart and all 100 profiles unchanged, zero orders. Tested on disk, **not deployed**: current live chat remains active, and archive/restart needs new approval. See `BAG_LANGUAGE.md` and `evidence/bag-language-readiness.json`.

FORME preference editor: **278 tests passed**. Catalog-backed dropdowns, individual clearing, optimistic revision validation and responsive headless UI verified. Direct FORME shopping uses FORME memory; Thread-controlled searches explicitly exclude it and use Thread preferences/current intent. FORME changes remain available through a fresh separately sourced authorized view. No automatic preference copying during Thread shopping. Tested on disk, not activated; current conversation requires fresh archive/restart approval. See `PREFERENCES_EDITOR.md` and `evidence/preferences-readiness.json`.


## Preferences activation — 2026-10-18

Fresh approval received; archived active Thread chat and restarted only separate :8443 demo as PID 23255. Nine archives persist, prior eight unchanged. All protected records pass before/after checksum equality. Live Chrome preferences page renders, Thread login persists, unsent draft restored. Post-activation isolated integration: 2 passed; desktop/mobile fixture editing passed. Full pre-activation regression remains 278 passed, zero failed/skipped. No live preference mutation or expanded grant. See PREFERENCES_EDITOR.md and evidence/preferences-readiness.json.

## GPT routing corrections — tested, awaiting activation

See GPT_ROUTING_FIXES.md and evidence/gpt-fixes/readiness.json. Pending watch replies now precede generic QA; contextual alternate colors, swapped-letter discovery nouns and unsupported-question routing are corrected. Actual GPT browser flows verified both real one-minute notifications, consent/auth, deduplication and item actions. Actual-GPT restart/reconnect tests passed. Broad supporting regression: 287 passed. No live restart or live-state mutation; fresh archive/restart approval required.
