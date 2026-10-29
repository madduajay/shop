# Exact product selection remediation

Deployed 2026-10-19 to the separate Thread/FORMe demo, process 81339.

## Cause and fix

Archived chat `9e12dddeb3670d39dd8390824e5523c3` confirms that “add red shoes to cart” caused an actual browser add of Dawn Geta-inspired Sandal, black, size 9. The planner supplied a historical card ID and execution accepted it without binding it to the current request. Evidence: `evidence/wrong-item-root-cause.json`.

`card_context.py` now resolves an explicitly named historical product or current ordinal independently of the model-supplied card ID, checking explicit color, size, and category constraints. Ambiguous or conflicting selections stop before mutation. Generic requests such as “add red shoes to cart” become product discovery and require an exact selection. `agent_tools.py` stops the planning loop after a blocked selection. Earlier explicitly named cards retain their original variants after category changes. Existing authorization, browser activation, stock, price, and duplicate-add safeguards remain in place.

## Verification

- Actual GPT/TLS controlled-browser test plus adversarial stale-card test: **2 passed** (`evidence/exact-add-gpt.xml`). The successful journey used 22 model calls and created zero orders.
- Unavailable red shoes after black-shoe cards: no add or authorization queue; bag unchanged; availability offer refers to the requested unavailable product.
- Earlier named shirt after switching to shoes: correct size L queued and added after sign-in; repeated authorization resume added once.
- Explicit shoe-card selection, then repeated selection: exactly one size-9 shoe line.
- Wrong color, wrong size, and non-action price question: model-proposed stale card blocked before selection or mutation.
- Card/product/tool regressions: **6 passed, 3 skipped, 1 deselected**. GPT-dependent cases skipped in that offline invocation; purchase journey deliberately excluded.
- Protocol conformance/resilience: **19 passed** (`evidence/exact-add-protocol.xml`).
- Final availability, watch expiry, card context, and stale-variant regressions: **5 passed** (`evidence/exact-add-final-regressions.xml`). Explicit creation → `/messages` → `/events` and retry deduplication remain intact.

Two earlier real-GPT attempts stopped safely during category switching with an intermittent planner failure; the final attempt passed. Follow-up reproduced a premature completion claim citing old card IDs, repaired its bounded recovery, and passed three real-GPT repetitions; see `PLANNER_COMPLETION_FIX.md`. The original attempts did not retain their exact exceptions. These finite tests do not establish universal natural-language interpretation. Ambiguous selections intentionally require clarification.

## Deployment and preservation

- Thread: https://atlas.localhost:8443/
- Store: https://jacket.localhost:8443/shop
- Traces: https://atlas.localhost:8443/traces

Verified running process is this workspace's `wardrobe/app.py`. Read-only health checks passed for demo discovery/assets and original https://atlas.localhost/ and https://jacket.localhost/shop. User Chrome renders the restarted Thread page with its existing identity and saved notification (`evidence/exact-add-deployed.png`).

All nine table hashes match before/after deployment: 100 profiles, 100 accounts and addresses, 9 orders, 3 carts and reviews, 3 company contexts, 7 purchase-memory keys, and 38 archived chats. See `evidence/exact-add-predeploy.json` and `evidence/exact-add-after.json`. The pre-existing incorrect sandal line was not removed or otherwise altered. No live purchase, new availability watch, trust-setting change, or external publication was performed for this remediation.
