# Explicit color exclusions

## Confirmed live failure

The exact message was `show me a shirt - not white color`. Read-only inspection found Thread's current request stored `colors: ["white"]`, and FORME's recorded browser-form filters contained `color=white` and `prefer_color=white`. The three newly rendered products were white: Essential Crew Tee, Pine Guayabera-inspired Shirt and Cliff Guayabera-inspired Shirt. Their imagery matched those attributes. Sanitized traces show interpretation followed by a completed browser filter; this was not stale image substitution. The trace redacts the normalized model command, so its exact wording was not recovered or assumed.

Both `Memory.edit` and `Flow.chat` treated any color mention as positive; the preference schema, browser form and retailer eligibility function had no color-exclusion representation. The previous 256-test suite did not cover negated colors and missed this real requirement gap.

## Correction

`color_constraints.py` separates positive alternatives and negative lists from the original utterance before model normalization. Original explicit exclusions survive even a deliberately lossy model rewrite. Supported negation includes not/no, don't want, without, avoid/exclude, except, anything but, neither/nor, lists and postposed rejection. Contradictory same-message requirements request clarification and invalidate current selections.

`excluded_colors` is a validated preference/request field. `exclude_colors` and `include_colors` are application-specific website filter fields, not invented Poppy protocol fields. The controlled browser submits those fields in the normal FORME filter form. Exclusions filter catalog eligibility before sorting, so saved or inferred preferences cannot reintroduce excluded products. They persist across refinements, cached result batches and retailer Next links. New searches remain request-scoped; explicit lasting memory uses existing opt-in semantics. FORME displays an editable exclusion input and active-filter chip. Matching no products produces the normal honest empty result, without substituting excluded products. Availability candidates also honor exclusions.

Existing single-color form behavior remains compatible; multiple positive alternatives use include_colors. Exclusions apply to the catalog's primary color, not every accent pixel or background in a photograph. This is not a claim to understand every possible natural-language negation.

## Verification

- Targeted unit/integration coverage: compound negatives, aliases, positive alternatives, contradiction, stored-vs-current precedence, persistent memory/isolation, saved request override, availability, signed-in Poppy browser form, cached and server pagination, no results, image metadata, and no profile/order changes.
- Live-GPT headless Thread UI fixture: exact reported phrase, `show more`, `not blue either`, more results, and `find blue or navy shirts but not white`. All returned cards/images satisfy exclusions. Contradiction asks for clarification. 8 actual parser calls plus 3 GPT explanation calls; 100 profiles unchanged; 0 orders.
- The first broad run found two integration expectations to resolve: preserve the existing single-color form contract and include the newly added exclusion control in the full filter matrix. Final rerun: **272 passed, 0 failed, 0 skipped**, in 127.606 seconds; recorded in `evidence/negative-colors-regression.xml`.

Evidence: `negative-colors-before.json`, `color-exclusions-browser.json`, `color-exclusions-live-ui.json`, `color-exclusions-live-model.json`, `negative-colors-focused.xml`, and `negative-colors-live-gpt.png` under `evidence/`.

## Deployment

Activated after explicit archive/restart approval. Live process: 16831. The latest conversation is durably archived (13 messages, 73 trace events), its stored hash survives restart, and all four prior archives are unchanged. The user browser renders the archived conversation and retains its Thread login. Live FORME renders the new exclusion control. Original Atlas at https://atlas.localhost/ remains available.

Post-activation live-GPT headless end-to-end verification used isolated profiles: the exact request returned blue/burgundy/blue; the negative refinement returned burgundy/burgundy/burgundy. All 100 fixture profiles stayed unchanged and no orders were created. No live shopping-test messages or new authorization grants were submitted. Live profiles, carts, reviews, orders, accounts, addresses and purchase-memory keys match pre-restart checksums. The approved archive resets temporary requests; the authenticated storefront inspection updates recent browsing constraints/activity through its normal GET behavior. Thus not every database table is byte-identical.

Thread was refreshed and is ready for a fresh request at https://atlas.localhost:8443/. No Thread login was needed; reconnect FORME through its normal sign-in flow if a future account-dependent action prompts for it. No new scopes or purchases were authorized or performed. See `evidence/negative-colors-readiness.json` for deployment evidence.
