---
name: availability
description: Offer, consent to, inspect, cancel or dismiss availability notifications.
metadata:
  version: "1.0.1"
---

Use catalog_search to check unavailable products. If its result asks whether to notify the user, STOP and return that single question. Wait for a new user turn. Do not call availability_notifications or unsupported_question to complete an offer. A waiting-for-user or waiting-for-authorization result is a normal pause, not an unsupported request. Explain the offer before subscription. Subscribe only after explicit consent; company watch scope is required. Status reads and local dismissal must not widen scopes. A notification is not a purchase or automatic bag addition. Verify the resulting watch state. Expired offers require a fresh search. Do not promise restock beyond the fixture offer; cancel safely and retain ownership isolation.

Completion: satisfy each requested step with tool-result evidence. Report blocked, unavailable or uncertain steps explicitly. Stop on limits or repeated actions; do not claim completion from model judgment alone.
