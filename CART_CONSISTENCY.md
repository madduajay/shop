# Shared account bag correction

Confirmed cause: the Poppy browser handler used `Store.states[session_id]['cart']`, while direct storefront sessions used persistent `storefront_carts` rows keyed by `account:<FORME account>`. Both authorized sessions mapped to customer 001 but saw different carts.

Read-only live evidence: the internal browser's existing `/shop/cart` DOM contained Essential Crew Tee, L ×1, and Cliff Guayabera-inspired Shirt, L ×1. The direct account row contained Essential Crew Tee, XS ×1. Company cart-add activity confirmed the two Thread additions. No add or checkout was replayed during diagnosis.

The correction binds every authenticated Poppy request to the same persistent account cart used by the storefront. Reads refresh after request-body awaits; browser-local CSRF, filters and review state remain session-scoped. A review records the shared cart revision and rejects concurrent changes. Add forms carry an account-bound idempotency key. Existing cart contents and delivery details are preserved. The same company-owned browser pages remain the action boundary; Thread does not read company SQLite.

`test_shared_cart.py` uses a real disposable headless Poppy browser plus independent storefront sessions. It covers both directions, size/quantity edits, parallel changes, stale edits, repeated form submissions, another account's empty cart and persistence in a new app instance. It creates no orders and never uses the live databases.

Deployment must preserve the old process's in-memory cart and chat before a restart. The live process is deliberately retained until that preservation step is approved/completed. Do not reconstruct or automatically replay additions from chat text or event logs. `evidence/live-cart-readonly.json` is an actual existing-browser DOM snapshot, not an inferred cart.

Live reconciliation completed after a second unchanged-DOM check: the prior XS tee was retained, and the two existing L-size entries were copied once with a transaction guarded by the original account cart contents/revision. No add request was replayed. The real user FORME tab was refreshed and showed all three variants, total USD 139. The running process and active Thread chat remain untouched. Permanent code activation is pending safe archive/restart approval. Full regression: 255 passed, zero failures.

The user approved archival and restart. The 13-message conversation and 56 trace events were archived as `7f9aa25730ab8525f3bddde6d473b6dc` before activation. All nine checked persistent tables were unchanged across deployment. A follow-up regression fixes fresh-session bag/checkout recovery. `verify_shared_cart_ui.cjs` verifies two real Chrome pages, both directions of cart visibility, and a fresh Thread login/reconnect without orders. Earlier pending-deployment statements above describe the historical staging state.
