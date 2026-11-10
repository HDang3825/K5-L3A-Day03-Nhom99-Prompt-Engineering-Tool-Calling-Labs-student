---
name: dedupe
track: core
kind: local_formatter
provider: local
requires_env: []
inputs: [items]
outputs: [items, removed_count]
side_effect: false
---

# dedupe

Removes duplicate research items with the same URL while preserving order.

Use this tool before `format` when results come from multiple sources or multiple
searches and may contain duplicate links.

Items without a URL are preserved. Invalid input returns an error object.