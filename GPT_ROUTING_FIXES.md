# GPT conversation routing fixes

Implemented and verified on disk; **not activated in the live :8443 process**. Live chats, data and grants were untouched. Activation requires fresh approval to archive the active conversation and restart the separate demo.

## Changes

Notification controls are handled before generic question answering. Pending yes/no/notify/cancel replies now use the existing consent state machine, expiry checks and FORME authorization. Plain “yes” never approves an order.

“Another color please” and equivalent short color refinements exclude colors in the current results while retaining previous exclusions, budget, size and current-request scope. They do not change lasting preferences. Missing or expired results cause a clarification; exhausting eligible colors returns no matching products rather than dropping constraints.

Explicit discovery requests can correct an unambiguous adjacent-letter transposition in a supported clothing noun, including “show me shrits.” Correction is bounded to discovery language and excludes profile, memory, account, order and cart commands. It does not claim support for every typo.

Generic context QA now rejects unrelated subjects with the standard unsupported response instead of inviting arbitrary personal/company tool calls. Unresolved “that account” references get a consistent clarification; ordinary name/profile/preferences retain Thread defaults. Existing authorized FORME reads and separately labeled comparisons remain intact. Model/transport errors on genuinely supported read requests still return a safe lookup-error message.

Changed application files: `app.py`, `context_qa.py`. Added deterministic guard tests in `test_conversation_routing.py`. Browser image checks now wait for image decoding in `verify_availability_ui.cjs` and `verify_color_exclusions_ui.cjs`.

## Verification

Actual model: **gpt-4.1-mini-2025-04-14**, existing credential used in process memory only. The audit records 113 real calls across selected successful evidence; additional reconnect-integration calls are not included in that count. No model was mocked or disabled in runs labeled actual GPT. Notification controls themselves are intentionally deterministic; the browser journeys ran with GPT enabled and verified actual model responses before consent.

| Area | Result |
|---|---|
| Shoes/tie offer, no, yes, signed-out login/resume, signed-in consent | Passed with actual GPT enabled |
| Real one-minute notifications | Shoes **60.448s**, tie **60.102s**; both accurate images loaded |
| Notification reload/poll deduplication, detail, explicit add, duplicate add rejection, repeat scenario, checkout guard | Passed in headless Chrome; zero orders in notification fixture |
| Cancel before authorization, invalid login, expired offer, cancellation after disconnect | Passed in actual-GPT integration fixture |
| Process/application restart, reconnect, durable inbox, account isolation and event deduplication | Passed; integration uses controlled due-time advancement, while the separate browser run above waits real time |
| Another-color refinement with available alternatives | Passed; excludes white while retaining $100 budget and saved navy preference |
| Exhausted alternatives | No matching items; exclusions retained, no silent relaxation |
| “Show me shrits” | Returned shirt results without company sign-in |
| Unsupported trivia and ambiguous account reference | Standard unsupported response / explicit clarification as appropriate |
| Local identity/profile, preference JSON, clear/archive persistence | Passed with actual GPT in the journeys |
| FORME authorized context, separate source labels, conflicting preferences | Passed; source-separation integration **2 passed** |
| Bag typos/contextual follow-ups, checkout review/approval/idempotency | Passed actual-GPT browser regressions |
| Broad supporting suite, including protocol/security and isolation | **287 passed, 0 failed**, 152.68s; these are supporting tests, not all real-model tests |

The first timed UI run and color run checked images before decoding finished. Test-only decode waits resolved both; successful retries are recorded explicitly rather than hiding the first failures. The six affected browser suites passed after these retries. Separate actual-GPT watch/reconnect integration: **2 passed, 24 deselected**, 78.61s. Source separation: **2 passed**, 15.56s.

Evidence: `evidence/gpt-fixes/readiness.json`, `availability/availability-real-minute-ui.json`, `availability/retry.log`, `availability-reconnect.xml`, `separation.xml`, `positive-refinement.json`, `context/chat-log.jsonl`, and `supporting-regression.xml`.

Screenshots: `evidence/gpt-fixes/availability/availability-desktop.png` and `availability-mobile.png`, both disposable fixture views. No live authorization or simulated live order was added. No OS trust or external credentials changed. Remaining limit: bounded typo and paraphrase coverage is not a guarantee for every possible utterance. Deployment is the only outstanding step for the tested fixes.
