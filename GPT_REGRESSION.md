# Actual GPT regression — 18 October 2026

Testing completed against the current application source, with the existing configured **gpt-4.1-mini-2025-04-14**, real API calls (no model mocks), disposable databases and headless Chrome profiles on the Mac. Selected evidence records **97 actual model calls**. Additional first-pass/retry calls are excluded from that count. Browser form actions, authentication and checkout remain deterministic application operations; their enclosing journeys used GPT where indicated below.

No application code was edited. The live :8443 app was not restarted or archived. No live user messages, subscriptions, grants, preferences, accounts, carts, addresses or orders were changed by this run. Simulated purchases occurred only in temporary fixtures. Test fixture data was removed on completion; evidence contains synthetic data only. Live service remains the previously activated version (PID file 24428).

## Coverage matrix

| Flow | Result | Actual model use / evidence |
|---|---|---|
| Local name, profile, remembered size, fabric/fit, combined name/budget, unknown age | Passed | Actual GPT; `context/chat-log.jsonl`, `followups.json` |
| Local customer isolation | Passed for fixture customers 1 and 2 | Actual GPT name lookup; `followups.json`. Fixture preservation checks compare all 100 profiles; not 100 separate GPT conversations. |
| Thread preference edits, read, JSON and clear/archive persistence | Passed | Actual GPT in edit journey; 6 calls in `verified/intents/model.json`; deterministic exact read commands also exercised |
| Temporary request precedence and real expiry | Passed | 7 actual calls; waited 62 seconds, active request became unknown while saved clothing size remained L; `expiry.json` |
| FORME editor, save, reload, clear, desktop/mobile layout | Passed | GPT configured but **zero calls**: deterministic UI coverage, `verified/preferences` |
| Authorized FORME view and separately labeled comparison | Passed | Actual GPT; local name question also works while company authorization is pending; `context/chat-log.jsonl` |
| Conflicting FORME/Thread preferences; explicit direct filters; no automatic copying | Passed | 2 isolated integration tests; actual GPT used for shopping, 5 calls; `separation/results.xml`, `separation/model.json` |
| Preference persistence, stale revision, CSRF, other-account isolation | Passed | Deterministic supporting assertions in same integration run; not attributed to GPT |
| Search, filtering, next page, current request budget/color | Passed for tested requests | Actual GPT; `followups.json`, `verified/shopping`, `verified/colors` |
| Negative color exclusions and contradictory colors | Passed | 8 actual calls; images/results checked; `verified/colors` |
| Short product explanations | Passed | Actual GPT-grounded explanations in corrected shopping/purchase runs, not fallback; `verified/shopping/model.json` |
| Product details, explicit add and shared cart across browser sessions | Passed | Actual GPT shopping followed by controlled-browser actions; `verified/shared-cart` |
| Bag typos/paraphrases and contextual follow-ups | Passed | 11 actual calls; includes “baf”, “crat”, “in there”, “altogether”; `verified/bag-language` |
| Direct cart quantity/size edits and Remove | Passed | Deterministic UI with GPT configured; `verified/store`, `store-extra/retry.log` |
| Authentication, wrong password, popup close/reopen, resume, logout | Passed for tested shopping/storefront paths | Actual GPT shopping journey plus deterministic direct-store checks; `verified/purchase`, `store-extra` |
| Review, synthetic address, explicit approval and duplicate prevention | Passed | Actual GPT shopping journey; exactly one fixture order after repeated approval; `verified/purchase` |
| Previous orders and other-account isolation | Passed | Exact order commands used **zero GPT calls**; deterministic supporting coverage, `verified/orders`. Actual GPT purchase-summary lookup separately passed in `context`. |
| Expandable traces, archive, clear, mobile layout | Passed after harness load-wait correction | Actual GPT query precedes trace inspection; `verified/traces/retry.log`, `thread-traces-ui.json` |
| Red shoes unavailable → yes/no | **Failed** | 2 actual calls: both replies produce unrelated Thread/FORMe clarification; `availability/chat-log.jsonl` |
| Exact “buy red tie” → offer → “yes” / “no” | **Failed** | 2 actual calls, watch remains offered, no authorization/subscription/order; `tie-reproduction.json` |
| Notification authorization → real one-minute restock → actionable card → item actions | **Blocked by preceding GPT consent failure** | Not claimed as GPT-enabled E2E coverage. Earlier deterministic timer tests are not a substitute. |
| Watch restart/reconnect with actual GPT | **Blocked / unverified** | Cannot reach active watch through the broken natural consent route without bypassing the behavior under test. |
| “another color please” follow-up | **Failed** | Unsupported response despite existing results; `followups.json` |
| “show me shrits” shopping typo | **Failed** | Generic read-only lookup error; `followups.json` |
| Outside-domain/ambiguous questions | **Inconsistent / failed cases** | “Who won the football game?” and “what about that account?” returned lookup-error text in observed runs. Weather fallback passed elsewhere. `context/chat-log.jsonl`, `followups.json` |

## Confirmed cause and minimal proposed corrections

The highest-priority failure is reproducible: `Flow.chat` calls generic GPT question handling before `watch_command`. `yes` and `no` route as unknown, and unknown text is treated as a question whenever GPT is available. The model has no pending notification context and returns the unrelated ambiguity branch. The offer stays unaccepted, so authorization and the real one-minute notification cannot proceed. Dispatch replies to a pending notification before generic QA; retain normal consent, expiry, account authorization and checkout gates. Add model-enabled regression cases for accept, decline, repeat, expired offer, pending auth and reconnect.

A related routing limitation treats unknown shopping typos as read-only questions. Route supported shopping paraphrases/typos with conversational shopping context, while keeping ordinary name/profile/preferences Thread-local and explicit company reads separately authorized. Do not broaden “yes” into checkout approval. The precise internal reason for the intermittent generic lookup-error responses was not captured; investigate model tool-plan/output validation rather than assuming a credential or network failure.

No fixes were silently applied. Application changes and live activation remain separate from this testing request.

## Test-harness corrections and limits

The first collector introduced an `import json` scoping error that caused post-check failures and interfered with one explanation-inspection wrapper. Those results are not treated as product failures; affected suites were repeated with the collector corrected under `verified/`. Trace testing initially read a newly opened page before its DOM loaded; adding a test-only load wait made it pass. The supplementary cart test initially tried quantity zero, which the application correctly rejects; using the actual Remove form passed. No application code changed for these corrections.

All ten corrected browser suites passed, with trace passing on its documented retry. The broader exploratory/context and availability runs still contain the product failures above. This is coverage of the listed scenarios, not a claim that every phrasing, all 100 customers or every failure mode is bug-free. No live account was used for consent or purchase testing. No full fixture process-restart watch flow was completed with actual GPT because natural consent is blocked.

Evidence: `evidence/gpt-regression/model-audit.json`, `final-results.json`, per-suite logs/JSON, and screenshots under `verified/`. Original first-pass logs are retained to make harness failures distinguishable from application failures.
