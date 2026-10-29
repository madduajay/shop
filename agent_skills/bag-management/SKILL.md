---
name: bag-management
description: Read, add, update or remove exact bag variants and recover pending selections after authorization.
metadata:
  version: "1.0.0"
---

Use read_forme_bag, add_to_bag, update_bag_item, remove_bag_item and queued_additions. Reads need orders:read; writes need orders:write. Resolve references to original cards; ask if ambiguous. Additions preserve exact size, color, price and one-unit intent. Multiple selections queue in order. Do not retry an uncertain mutation. After an edit verify the affected variant and quantities from the returned bag. Present images and prices. Cancel pending additions separately from removing existing contents. Missing authorization pauses execution, never grants itself.

Completion: satisfy each requested step with tool-result evidence. Report blocked, unavailable or uncertain steps explicitly. Stop on limits or repeated actions; do not claim completion from model judgment alone.
