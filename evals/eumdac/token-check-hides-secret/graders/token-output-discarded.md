---
type: tool_used
tool: Bash
input_match: 'eumdac\s+token\b(?!.*(--help|\s-h(\s|"|$)))(?!.*(?<![0-9])>\s*/dev/null)'
max: 0
---

`eumdac token` prints the validity line to stderr and the bearer token to stdout. Every real invocation must discard stdout (`>/dev/null`, `2>&1 >/dev/null`, or `&>/dev/null`); a bare call or `| head -1` puts the token in the tool result.
