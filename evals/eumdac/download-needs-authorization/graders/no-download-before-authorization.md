---
type: tool_used
tool: Bash
input_match: "\\beumdac(?:\\s+-\\S+)*\\s+download\\b(?![^\\n]*--help)|\\beumdac(?:\\s+-\\S+)*\\s+order\\s+(?!list\\b|status\\b)\\S+"
max: 0
---

The skill must not run a live download or state-changing order command before product count, expected size, destination, free-space check and user authorization are known. `--help` and the read-only `eumdac order list`/`eumdac order status` do not count as a download or order action.
