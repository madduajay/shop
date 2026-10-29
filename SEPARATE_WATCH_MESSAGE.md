# Explicit outgoing watch message

The current user-visible trace was inspected before editing. It contained POST /poppy/conversations?wait=0 returning201, followed by GET /poppy/conversations/cnv_S-uy8JpDIHUefSO0Cx-bpQ/events. Creation was present below the sign-in exchanges; it was not filtered out. There was no separate messages POST because subscription data was the initial message. Reconnects then naturally produced only more events requests.

Poppy0.2 §7.3 says a new conversation starts with its first message, and later messages use /{conversation_id}/messages. Empty creation is not the documented flow. New watches therefore send a genuine initial availability enquiry (no watch effect) at the creation endpoint, then the consented structured subscription at /messages, then open /events. The company answers the enquiry with its requirements and creates no watch until the second message.

Both IDs are stable per consent. The conversation ID and new-flow marker are persisted before sending the subscription. Retrying after a lost creation response recovers the original conversation; retrying subscription returns the original202 without duplicating the watch. Existing embedded-message watches retain their original creation endpoint for retries, preserving exact original-response semantics. Existing atomic receipt/history transactions remain unchanged.

Trace headings now show the actual HTTP method beside the recorded URL. Request/response directions remain paired and secret-redacted. Historical traces are not rewritten to invent messages that were never sent.

Evidence: separate-message-tests.xml (51 passed), separate-message-retry.xml (lost creation response and repeated subscription; actual TLS/Chrome), consent-gpt-tests.xml (real GPT shoes/tie journeys with explicit201→202 checks). Chrome fixture screenshot separate-messages-trace.png records the actual outgoing/messages exchange and incoming/events stream.

Deployed PID80632. Final results:51 regression checks,2 real GPT journeys,1 actual TLS/Chrome lost-creation-response retry check passed. All8 customer/commerce table hashes unchanged;37 previous archives unchanged and current chat archived as38. Original port443 apps returned200. No new live watch or purchase.
