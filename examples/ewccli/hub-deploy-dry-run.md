# Dry-Run An EWC Community Hub Item

## Prompt

I want to deploy an EWC Community Hub item, but first show me how to inspect it and dry-run the deployment.

## Expected Agent Behavior

- Use the `ewccli` skill and load `hub.md`.
- Start with discovery:

```bash
ewc hub list
ewc hub show <item>
```

- Confirm profile, federee, tenant, item name, server name, item inputs, external IP, image/flavour/network/security overrides, and SSH key availability.
- Prefer dry-run before real deployment:

```bash
ewc hub deploy <item> \
  --profile <profile-name> \
  --server-name <server-name> \
  --dry-run
```

- If the item requires inputs, use repeated `--item-inputs key=value`.
- Do not suggest a real deploy until the user confirms resource/cost implications.

## Expected Response Shape

- Workflow type: Hub.
- Prerequisites: installed `ewccli`, profile, credentials, network, selected item.
- Credential safety: no secrets on screen.
- Commands: list/show/dry-run and a clearly separated real deploy template if needed.
- Validation status: help/list/dry-run status, no live deployment claim unless actually run.
