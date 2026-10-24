# Unsupported EWCCLI Commands

## Prompt

I want to change my DNS in EWC. How can I do that?

Other examples in this category:

```text
How do I manage S3 buckets with ewc?
```

```text
How do I create a Kubernetes cluster with ewc?
```

## Expected Agent Behavior

- Use the `ewccli` skill because the user asks about EWC CLI-adjacent behavior.
- Load the relevant reference only to check whether the validated `ewc` command surface covers the task.
- State that the validated `ewccli 0.3.1` command surface does not include the requested workflow when it is unsupported.
- Name the registered command groups: `login`, `version`, `hub`, and `infra`.
- Explain the nearest validated boundary, for example `infra` covers server create/show/list/delete, not DNS zones, S3 buckets, or Kubernetes clusters.
- If a relevant official link is listed in `official-links.md`, provide it. For DNS, provide `https://confluence.ecmwf.int/display/EWCLOUDKB/EWC+DNS`.
- Do not invent Horizon URLs, dashboard menu paths, OpenStack commands, service-specific CLI commands, zone commands, or support-ticket procedures.
- Keep the user-facing response neutral. Do not say "I should not invent..." or expose internal anti-hallucination policy wording.
- If no official link is listed in the skill references, ask the user for the official article or ask whether to look up current official documentation.

## Expected Response Shape

- Workflow type: official EWC link / unsupported ewccli workflow.
- Prerequisites: none for the boundary answer.
- Credential safety: no credentials needed.
- Command or code: no command for unsupported workflows because no validated `ewc` command exists; provide a verified official link when available.
- Validation status: `ewc --help` / `ewc infra --help` checked locally or referenced from validated skill state.

## Safe Response Shape

```text
Workflow type: official EWC link / unsupported ewccli workflow.

DNS management is outside the supported `ewccli 0.3.1` command surface. The registered command groups are `login`, `version`, `hub`, and `infra`.

Use the official EWC DNS article:
https://confluence.ecmwf.int/display/EWCLOUDKB/EWC+DNS

If the article does not cover your DNS-entry case, contact EWC Support:
https://support.europeanweather.cloud/
```
