# Thread × FORME availability demo

Open https://atlas.localhost:8443/ and sign in to Thread with `customer001@thread.local` (through `customer100@thread.local`), password `wardrobe`. FORME independently uses the corresponding `@forme.local` account and public demo password.

1. Send **Red shoes** or **Red Tie**. Case and natural variants work, including “show me red shoes”, “find a red tie”, “red sneakers please”, and “red necktie please”.
2. Thread explains that the match is unavailable **in this staged demo scenario** and asks whether to notify you in chat. Send **yes**. **No** declines without a company watch or login.
3. Authorize FORME notifications. Sign in only if the company authorization browser does not already have a valid company-owned login. An existing company login shows an authorization confirmation instead of asking for its password again. This is separate from Thread login. No subscription exists until authorization succeeds.
4. Wait about **60–66 seconds** with Thread open. A highlighted card appears with the matching red product photograph, size, price, and **Add to cart** button. The red leather court sneakers cost $95 and support US whole sizes 6–13, standard width. The regular-length red silk tie costs $45 and is One size. Saved hard size, budget range, and material exclusions apply; unsupported sizes, budgets, brands, material or style requests receive an honest limitation rather than a substituted item.
5. Click **Add to cart**. No checkout happens. Say **checkout** for order authorization and a review; only a separate **I approve this order** can place a fictional order.

After a card has arrived, a fresh explicit red-shoes or red-tie search starts a new offered scenario and asks for consent again. Repeating the same search or “yes” during an active scenario reuses its original subscription and timer. The two triggers can run concurrently. Say **cancel watch** to cancel pending/active watches; **my watches** reports the active count. Each customer's scenario has a private product variant: it neither removes genuine regular catalog stock nor changes another customer's availability.

## What is implemented

This is an application feature built over existing Poppy session/device authorization and its controlled-browser website flow. `availability:watch` is an advertised company-defined OAuth scope. Subscription and cancellation use CSRF-protected FORME HTML forms; events are read from an authenticated FORME page through the same browser. Thread polls at 5.5-second intervals. This is **not** a new Poppy wire field, native push notification, MCP subscription, external stock claim, email, or OS notification. The current [Poppy draft specification](https://personalagentprotocol.org/docs/spec) was checked for custom scopes and Web Browsing; its signed assertion activation and website-issued cookie are unchanged.

FORME owns its SQLite watch/event storage, due timestamps, immutable event IDs, and scoped restock variants. It advances due transitions on company requests, including polling: if Thread is closed, the due transition is materialized on the next company request. The signed company account, personal-agent client and pairwise user own each watch. Thread separately owns consent records and a durable inbox. Event IDs deduplicate cards; cached events are reoffered on poll/state to recover a dropped response and survive reload. A conditional reservation prevents replaying an Add action across sessions; an interrupted action asks the user to check the bag rather than silently adding twice.

Offers/unfinished consent expire after 10 minutes; active watches and notification delivery/actions have a 24-hour lifetime (records remain for deduplication and history) and at most five watches per company identity. Cancellation immediately stops Thread delivery. Connected cancellation also reaches FORME; disconnected cancellation queues company cleanup for the next authorized connection and remains bounded by expiry. A full application/server restart preserves watches, timers, private variants and inbox entries. Because Poppy sessions are process-local in this demo, Thread asks to reconnect FORME before receiving new events after restart. It does not secretly recreate a signed-in cookie. Agent browser bags remain process-local, as before; direct-store bags and recorded orders are durable.

## Verification evidence

- `evidence/availability-tests.xml`: **245 passed, 0 failed/skipped** in the full regression suite, including original 100-profile isolation/persistence, Poppy signature/audience/session/expiry/replay/cookie checks, inventory/filter variants, local preference JSON, guest shopping, orders, approval/idempotency, and availability tests.
- `test_availability.py`: real controlled-browser tests with an advanced company clock; both triggers, ten natural variants, impossible constraints, decline, failed/wrong-account login, cancelled login, repeated callbacks/consent/events, active/fresh scenarios, scope upgrade without another password, cancellation, expiry, full application/server restart, durable inbox replay protection and cross-user isolation.
- `evidence/availability-real-minute-ui.json`: two genuine 60-second timers (observed delivery: shoes **65.938 seconds**, tie **65.518 seconds**) in disposable headless Chrome, signed-out login/resume, signed-in second watch, correct loaded red images, one highlighted card per event, mobile overflow check, reload deduplication, Add buttons, repeated Add rejection, fresh repeat scenario, and checkout guard. Fixture profiles remain unchanged and orders remain zero.
- `evidence/availability-desktop.png` and `evidence/availability-mobile.png`: inspected rendered notification cards.
- `evidence/availability-preservation.json`: before/after hashes of every pre-existing table in commerce, company memory, Thread identity/history, and FORME identity/session databases.

Passing this requirement-based matrix is not a claim that software is bug-free. Deliberate limits are local synthetic stock only, fixed supported demo products/variants, bounded polling while Thread is open, 24-hour notification delivery/action lifetime, and reauthorization after process restart. No real payment, delivery, public deployment, OS trust change or new external credential is involved.

## Image assets

Built-in imagegen produced `assets/photos/demo-red-shoes.png` and `assets/photos/demo-red-tie.png`. Prompts specified photorealistic catalog studio photographs on warm light-gray seamless backgrounds: (1) bright-red low-top leather sneakers, red laces, white rubber soles; (2) a solid bright-red silk necktie with a classic pointed blade and loose knot. Both forbid logos, labels, text and watermarks. The generated assets were visually inspected and copied into the project; no unrelated product image is substituted.

The focused browser flow was also rerun after adding explicit failed-password and repeated-login-callback assertions: 1 passed. Existing UI regressions are recorded in `evidence/availability-existing-ui-regressions.json`.


## Release checkpoint

Deployed to the separate port-8443 service (PID 6092). All **245 tests passed**, zero failed/skipped. The final full run includes the expanded explicit disconnect/reconnect and queued-cancellation flow. Product identity/size-label metadata was additionally checked in 22 focused passing cases. All three existing headless UI regressions passed. Both original port-443 apps return 200. The new Thread root redirects to its login as expected; discovery, advertised availability scope, and both red image URLs pass trusted-TLS health checks.

Every pre-existing table in all four persistent databases matched its before-deploy hash: 100 profiles, 3 orders, saved cart/review, company memory/history, independent identity accounts/sessions and Thread history. New watch/inbox/authorization tables are additive. No live watch, order or preference was created by verification. All watch scenarios and timers ran in isolated fixtures.

| Requirement | Result / evidence |
|---|---|
| Red shoes and Red Tie, case/natural variants; repeat versus active reuse | Passed: deterministic routing tests and real UI |
| Consent, decline, cancelled/failed login; duplicate yes/callback | Passed: controlled browser tests |
| Signed-out login/resume and already-authorized path | Passed: real UI; scope upgrade uses company login cookie without another password |
| Real one-minute company timers, correct images, one highlighted card | Passed: both timers ~66 seconds, desktop/mobile screenshots |
| Add to cart, duplicate Add, separate checkout approval | Passed: real UI and browser tests; zero fixture orders in timer runs |
| Cross-user isolation, replay IDs, independent scenario clocks | Passed: company and controlled-browser tests |
| Disconnect/reconnect, full application/server restart, dropped-response/reload recovery | Passed: durable inbox + browser restart tests |
| Cancellation, queued offline cancellation, offer/event expiry, impossible constraints | Passed: lifecycle/browser tests |
| Local-only preferences/JSON, guest browsing/cart, private orders, original protocol guards | Passed: full suite and three existing headless regressions |
| Preserve live records and original apps | Passed: table hashes and live TLS health evidence |

Machine-readable release evidence: `evidence/availability-readiness.json`. No critical requested path is left unrun. This finite test matrix does not prove the absence of all bugs.
