# Semantic bag lookup

## Confirmed failure

Read-only inspection of the live Thread conversation found the exact user message `show me what is on the baf`, followed by `Thread: I don’t have that information in the available records.` The route matcher accepted only a small set of exact bag/cart forms. The typo and nested phrasing missed it, so the general context question handler ran. That handler exposed identity/preferences/metadata tools but no bag reader, and its company-tool gate did not recognize bag/cart questions. There was no grounded FORME bag lookup behind the response. The issue was semantic routing and missing tool coverage, not evidence that the bag was empty.

## Changes

The native GPT context tool set now includes `read_forme_bag`, a server-bound, zero-argument read-only tool. It reuses `show_bag` and the Poppy controlled browser rather than introducing a cart API or letting GPT choose an account. It understands bag/cart/basket paraphrases and likely typos. Prior read questions and a bounded last-read marker support follow-up references. Existing exact commands retain their direct route. Container-related language reaches semantic interpretation before clothing keywords can turn it into product discovery; GPT decides whether it is a read, unsupported mutation, or ambiguous request.

Disconnected reads request the existing demo `orders:read` scope through normal FORME sign-in and resume once. Already connected reads verify matching account identity and authorization, then visit the cart page through the controlled browser. Output is assembled from observed item/size/quantity/price fields, not invented by a response model. Unsigned sessions, unexpected pages or missing cart data cannot be reported as an empty bag. No write tools, checkout approval authority, customer selector, cookie injection or purchase API were added.

## Verification status

The first real-GPT UI run exposed an additional routing gap: colloquial `lemme see whats inside the shopping basket` was captured by the shopping keyword without being recognized as a question. The container routing gate was corrected and the full suite and live-GPT UI rerun are recorded under `evidence/bag-language-*`.

The first full regression passed 275 checks and failed one existing stub that omitted page/session evidence; that stub now reflects the real controlled-browser cart snapshot. The final run is recorded in `evidence/bag-language-regression.xml`.

Tests cover the exact typo, nested wording, basket/cart synonyms, content-specific questions, follow-up references, invalid tool arguments, wrong-account rejection, disconnected/connected reads, empty/nonempty bags, fresh flows, minimal read scope, resume once, unchanged fixture cart/profiles, zero orders, and inability to call mutation tools. Existing shared-cart persistence, identity isolation, color exclusions and approval tests are included in the full regression.

Final result: **276 passed, 0 failed, 0 skipped** (147.68s). The rendered real-GPT fixture made 11 model calls, used only `orders:read`, preserved all 100 profiles and the seeded cart, and created zero orders. Screenshot: `evidence/bag-language-live-gpt.png`.

## Deployment

Tested changes are on disk only. The live process has not been restarted; the current user conversation remains active. Activation requires approval to archive the current chat and restart. No live cart, order, preference or account-scope mutation was performed for this investigation.
