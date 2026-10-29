# Planner completion recovery

## Finding

The earlier two test attempts did not retain their exact exceptions. A bounded three-run reproduction of the same category-switch journey captured full masked model exchanges and errors: **two failed, one passed**. Both failures were `ValueError: Unsupported completion` at the completion-evidence guard. The model returned HTTP 200 and valid tool-call JSON, but selected `finish_request` before any tool executed for the new request, citing an old product-card ID as its evidence. The current request had zero results. This is a planner routing/evidence error, not a demonstrated provider outage, JSON/schema parsing error, or exact-selection rejection. The guard correctly rejected the claim; the missing recovery path caused the generic user-facing failure.

Evidence: `evidence/planner-diagnosis-before-1.json`, `evidence/planner-diagnosis-before-2.json`, and `evidence/planner-diagnosis-before.xml`. This establishes the reproduced cause, not retrospective certainty about uncaptured original exceptions.

## Repair

`agent_tools.py` offers `finish_request` only once the current request has an execution result. Invalid completion evidence still fails validation. The planner receives a tool result explaining the rejection and listing current result IDs/statuses, with one correction attempt; a second invalid completion stops as incomplete. Rejection itself never executes a shopping action. Existing action signatures, exact selection, consent, authorization, and duplicate suppression remain in force. A satisfied outcome still requires verified evidence. A rejected completion after execution retains the grounded reply/cards instead of replaying the action.

## Verification

- Pre-fix actual GPT/TLS controlled-browser reproductions: 1 passed, 2 failed as described above.
- Post-fix same three isolated journeys: **3 passed in 77.25 seconds**, no exceptions, no bag changes, no sign-in queues, no orders. See `evidence/planner-diagnosis.xml` and `evidence/planner-diagnosis-{0,1,2}.json`.
- Deterministic recovery and existing tool-loop tests: **9 passed, 1 purchase journey deselected**. Covers premature evidence, bad evidence after execution, invalid success on unavailable evidence, bounded repeated rejection, and no repeated execution. See `evidence/planner-repair-unit.xml`.
- Protocol conformance/resilience: **19 passed** (`evidence/planner-repair-protocol.xml`).
- Actual GPT exact-selection/browser sign-in and adversarial stale-card tests: **2 passed in 36.04 seconds**, including duplicate authorization resume and repeated card selection (`evidence/planner-repair-exact.xml`).
- Explicit creation → `/messages` → `/events`, watch expiry, and historical card regressions: **4 passed in 21.86 seconds** (`evidence/planner-repair-messages.xml`).

## Deployment

Deployed to the separate service on 2026-10-19, process 82296. Thread: https://atlas.localhost:8443/ ; storefront: https://jacket.localhost:8443/shop ; traces: https://atlas.localhost:8443/traces . User Chrome renders the restarted page (`evidence/planner-repair-deployed.png`). Original Atlas and jacket-store health checks remain successful.

All nine data-table hashes match before and after deployment, preserving 100 profiles, accounts and addresses, existing carts/reviews, 9 orders, company contexts, purchase-memory keys, and 38 archived chats (`evidence/planner-repair-before.json`, `evidence/planner-repair-after.json`). No new live watches, live bag mutations, purchases, external publishing, credentials, or trust changes were made. No known blocker remains for this reproduced failure; finite tests do not guarantee universal model behavior.

## Historical wrong item

The historical red-shoes request **actually mutated the bag**, rather than merely claiming success: the browser `add` response contains Dawn Geta-inspired Sandal, black, size 9 (`m-loafers-009`). See `evidence/wrong-item-root-cause.json`. This investigation did not alter that existing bag line.
