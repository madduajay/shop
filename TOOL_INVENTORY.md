# Thread agent inventory — active build

Activated after explicit fresh-chat restart approval. Live server PID 65508. The build has 19 application tools plus the internal finish_request tool; exact schemas are in evidence/commerce-images/tool-schemas.json.

## Application tools

| Tool | Source / effect | Access |
|---|---|---|
| read_thread_user_data | Saved Thread name/email | Authenticated Thread principal |
| read_user_preferences | Separate Thread or FORME records | Thread; explicit FORME needs preferences:read |
| update_preferences | Explicit lasting updates to selected source | Thread; FORME preferences:write |
| read_forme_user_data | FORME email/shipping address; billing absent | account:read |
| read_forme_orders | Purchase records with item images | orders:read |
| read_forme_bag | Exact bag variants/images/prices | orders:read |
| thread_user_context | Defined Thread categories, no files/SQL | Thread |
| forme_user_context | Defined company categories | Per-category company scope |
| catalog_search | Public catalog search/refinement | No FORME customer login |
| product_details | Exact previously shown card | No FORME customer login |
| add_to_bag | One unit of selected card; ordered authorization queue | orders:write |
| update_bag_item | Absolute quantity/size via real form | orders:write |
| remove_bag_item | Exact variant via real form | orders:write |
| queued_additions | Show/cancel pending intentions | Thread |
| availability_notifications | Existing offer/watch subscribe/cancel/status/dismiss | Company watch scope for subscription; owned local status/dismiss |
| connection_status | Verified connection state | Does not broaden permissions |
| checkout_review | Current variants/images/total and synthetic delivery | orders:write; no purchase |
| confirm_checkout | Current reviewed simulated order | orders:write plus exact current approval phrase |
| unsupported_question | Ambiguity/unavailable capability | No side effects |

All schemas are exposed in each model tool-loop turn. Tool visibility never grants scope. The Thread UI itself still requires Thread sign-in; the public FORME storefront and public catalog tools do not require FORME customer sign-in. No arbitrary filesystem, SQL, credentials or billing-data tool exists.

## Loaded workflow skills

Version 1.0.0: identity-preferences, product-discovery, bag-management, checkout, availability. Files are under agent_skills/*/SKILL.md. workflow_skills.py provides the name/description catalog. When the model selects a tool, the corresponding skill is loaded before execution, returned to the model, and recorded with version/SHA-256 in the trace. The model then reselects its action under that workflow. Code retains authorization and mutation validation regardless of skill text. All five skill files pass the skill-creator validator.

## Request loop

A structured model planning step records the current requirements. Each tool turn receives all schemas, current owned card references, verified bag context, workflow metadata and prior native function_call/function_call_output messages. Tools execute sequentially through validated server dispatch. Results return to GPT for evaluation and further calls. finish_request must cover every requirement index and refer to real executed result IDs; unavailable/blocked results cannot satisfy a requirement. User-visible answers come from executed tool results, not a model-generated claim of actions.

The loop has a 16-turn cap, 12 execution cap, 90-second per-active-run deadline, repeated-call stop, and no automatic uncertain mutation retry. Authorization pauses retain task state; poll continuation supplies the resolved result before further planning. Mixed requests may require additional grants. Exact checkout approval is checked independently of model selection. Queue adds keep existing per-card idempotency; bag edits are absolute/revision checked; receipt creation remains review-ID idempotent.

Greetings use no tools. First greeting uses authenticated Thread preferred_name/display_name/name if present. Later greetings avoid repeated naming; absent identity gets a generic greeting. Thread profile and company records remain distinct.

## Verification and activation

Image integration and mobile/archive checks passed before the larger harness change. Earlier read-tool GPT suite: 47 passed. Current harness unit tests: 5 passed. The expanded actual-GPT journey passed (5 tests): identity, preference update/read, public discovery, two queued additions, authorization recovery, imaged bag, quantity edit, review, exact approval, duplicate prevention, composite reads, availability status, no-match catalog, and customer isolation. The final actual-GPT rerun passed all 6 tests in 86.11 seconds; a separate two-section actual-GPT check passed the final scoped composer wording. The latest broad regression had 328 passed, 7 skipped and one outdated test expectation; corrected routing/authentication checks then passed all 11. Five harness unit checks passed. Final consolidated results are recorded below when available.

A temporary UI fixture initially shared the live Thread cookie name and signed the user browser out. Fixture cookie names now include their port, preventing collision with the live Thread cookie. Authentication checks pass with this separation. Saved records and prior archives remain intact; the live process is deliberately still running because any unarchived conversation may remain in its former process-local session. The user explicitly approved the fresh-chat restart; it completed without changing saved records. The inaccessible active chat was not recovered or claimed as archived.

Final consolidated regression: **330 passed, 7 skipped** in 177.61 seconds (`evidence/commerce-images/consolidated-regression.log`). Actual-GPT journey plus unit tests: **6 passed** in 86.11 seconds. Two final scoped composite-answer sections passed with actual GPT. All nine saved-data table hashes match across activation; original Atlas and jacket URLs return HTTP 200.

Live Chrome verification: named greeting, combined identity/bag request, normal FORME read authorization and resume, empty bag, and eight loaded existing-order images passed. The live bag was empty, so filled bag/review/receipt images were verified in isolated fixtures; no live bag mutation or purchase was made. `live-orders.png` records the live order cards.
