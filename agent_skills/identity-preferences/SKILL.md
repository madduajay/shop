---
name: identity-preferences
description: Answer identity questions and read or explicitly update source-separated saved preferences.
metadata:
  version: "1.0.0"
---

Use read_thread_user_data and read_user_preferences for Thread by default. Explicit FORME requests use read_forme_user_data, read_user_preferences(source=FORME) or forme_user_context, after category authorization. update_preferences accepts an explicit lasting request only. Thread names come from the authenticated profile. Shipping is FORME-owned; billing is unavailable. Verify updated values through a read of the same source. Do not copy data across sources. Missing facts remain unknown. Pause on missing scope; do not substitute another account.

Completion: satisfy each requested step with tool-result evidence. Report blocked, unavailable or uncertain steps explicitly. Stop on limits or repeated actions; do not claim completion from model judgment alone.
