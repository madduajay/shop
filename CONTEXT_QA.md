# Grounded read-only questions and private traces

Thread: https://atlas.localhost:8443/  
FORMe: https://jacket.localhost:8443/shop  
Private trace page: https://atlas.localhost:8443/traces

The existing apps on port 443 are separate and unchanged.

## Context tools

`thread_user_context(categories, fields)` reads only the server-authenticated Thread customer's allowlisted identity, preferences, current unexpired request, chat counts, local connection metadata and local watch consent records. Ordinary identity questions never open FORME. `forme_user_context(categories, fields)` navigates the controlled browser to a FORME-owned read-only context page; that website checks the signed-in company account and consented scopes before reading its own account, preferences, orders or watch records. No tool accepts a customer ID, SQL, path, shell command or arbitrary URL. Model planning and grounded composition use native Responses API function calling and structured output. No mutation tools are available in this path.

Unknown attributes are explicitly unknown. Unsupported questions use `Sorry i am not sure how to handle this request`; ambiguous source questions ask for clarification. Combined answers label Thread and FORME separately. Evidence references must match returned facts and sources. This is bounded model grounding, not a deterministic proof of every generated sentence. Without a configured model, existing deterministic shopping/status commands still work; new generic questions return the unsupported response.

Examples: “Remind me what you call me”, “Which shoe size do you have on record for me?”, “What is my name and my budget?”, “Compare my Thread budget with my FORME saved budget”, “What is the status of my red shoes watch at FORME?” Signed-out company questions request authorization and resume afterward; local questions still work while authorization is pending. Source-labeled JSON and existing order cards remain supported.

The company context endpoint and custom scopes are application conventions, not newly invented Poppy protocol fields. Poppy still establishes the authorized browser session; FORME validates the assertion and issues its own cookie. Purchases still require explicit chat approval and browser forms. Restock watches still require separate consent and use application polling.

## Trace page

The discreet chat link opens `/traces` in a separate tab. It is authenticated with the existing Thread session, reads only that session's current conversation, and lists only that customer's private archives. Clear chat archives the prior events; the current page then shows an empty state. `/traces?archive=<opaque-id>` checks ownership. Unknown or another customer's archive returns 404. Logout revokes access. Current conversations remain process-local; archives are durable.

Events include native HTTP client Poppy exchanges, server-observed browser activation/sign-in/storefront exchanges, browser actions, grounded context tools and availability event retrieval. Events retain UTC timestamps, direction, method/path, duration where observed, status, safe payload shape, cookie-presence/issuance flags and assertion validation outcome. Browser correlation references are abbreviated hashes. Protocol events and application-specific actions are labeled separately. No raw assertions, tokens, cookies, credentials, customer field values or hidden reasoning are displayed. Payload values are conservatively omitted; expandable entries preserve structure. The page refreshes on navigation/manual refresh, not a background stream. It reports observed exchanges only, and does not claim unsupported MCP messages or native server push.

## Verification

`test_context_qa.py` covers binding, injection, forbidden arguments/actions, unknown/ambiguous routing, evidence validation, native function-call transport, company login/resume and minimal read scopes. `test_trace_page.py` covers authentication, source isolation, archives, clear, secret redaction, escaped rendering and new-tab navigation markup. `verify_context_qa_ui.cjs` exercises live GPT in disposable Chrome against newly seeded synthetic fixture databases; it never reads the live customer databases. `verify_trace_ui.cjs` checks the actual rendered dedicated page, mobile width, retained chat, and archived/current navigation.

Evidence lives in `evidence/context-qa-*.json`, `evidence/context-qa-tests.xml`, `evidence/thread-traces*.png` and `evidence/thread-traces-ui.json`. See the final task report for the exact completed run counts and any remaining limitations.

## Thread stays in control of shopping

Product cards, images and titles now open a Thread detail dialog. Adding requests a FORME-owned sign-in/consent popup if necessary and resumes that selected add once. Closing the popup does not add anything; “cancel add” revokes the pending local selection. Login never places an order. Already-authorized adds proceed in Thread's internal headless browser. Availability cards use the same gate, with durable event deduplication. Review and final explicit approval stay in the Thread conversation.

FORMe owns an additive `delivery_addresses` table in its identity database. Each of its 100 demo accounts receives a distinct, clearly synthetic address only if none exists. Existing saved cart/order delivery details are preserved when seeding, and existing address-table entries are never overwritten. Thread retrieves the address only as part of the authorized browser-rendered order review, never from company SQLite. Address data is excluded from the generic QA tools, preference memory and model inputs. The review contains item/size/quantity, USD total and delivery address; final checkout rechecks the address has not changed. The existing direct FORME checkout can edit saved delivery details; Thread's review currently presents the address read-only. No real shipping or payment occurs.

## Concise recommendation reasons

FORMe now selects one or two supported reason IDs and renders a single sentence, targeting 15–25 words with a 25-word cap. Explicit material/fit/size/budget evidence takes priority. Inferred interests never become invented preference claims. Product facts, quantities and filtering remain unchanged. Invalid model selections fall back to the same concise, grounded renderer; no generated text is truncated mid-sentence. The same sentence appears in Thread and the storefront.
