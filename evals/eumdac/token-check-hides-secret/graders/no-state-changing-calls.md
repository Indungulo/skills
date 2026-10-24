---
type: tool_used
tool: Bash
input_match: 'eumdac\b(?!.*(--help|\s-h(\s|"|$))).*\b(download|download-metalink|set-credentials|livefeed|subscribe\s+(add|download)|subs\s+(add|download)|tailor\s+(post|delete|cancel|clean)|order\s+(resume|restart|delete|housekeep)|local-tailor\s+(set|remove))\b'
max: 0
---

The prompt forbids live downloads, orders, subscriptions, tailor jobs and credential changes. Any Bash call that runs one of those eumdac subcommands (other than with --help) fails the case. Read-only describe/search/token/list/status/quota calls are allowed.
