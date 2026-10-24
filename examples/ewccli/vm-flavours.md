# Available VM Flavours

## User Prompt

```text
What are the available flavours in EWC?
```

## Expected Agent Behavior

- Route to `vm-plans.md`, not only `infra.md`.
- State that `ewccli 0.3.1` accepts `--flavour-name` but has no dedicated command to list every available flavour.
- Ask for the federee if the user did not provide one, because ECMWF and EUMETSAT use different plan names.
- Provide the official ECMWF and EUMETSAT VM plans links.
- Mention the `ewccli` defaults:
  - ECMWF: `4cpu-4gbmem-30gbdisk`
  - EUMETSAT: `eo1.large`
- If giving examples, use exact plan names from the official federee-specific lists.
- Do not invent generic categories such as small/medium/large/GPU examples.
- Do not offer to fetch official docs when the relevant official links and dated snapshot are already in the skill; say the KB should be rechecked before treating availability or pricing as current.

## Safe Response Shape

```text
Workflow type: infrastructure.

ewccli 0.3.1 does not have a command that lists every VM flavour. It accepts a selected flavour with `ewc infra create --flavour-name <flavour-name>`.

The full list is federee-specific:
- ECMWF: https://confluence.ecmwf.int/display/EWCLOUDKB/ECMWF+-+VM+plans+and+flavors
- EUMETSAT: https://confluence.ecmwf.int/display/EWCLOUDKB/EUMETSAT+-+VM+plans+and+flavors

Defaults from ewccli are ECMWF `4cpu-4gbmem-30gbdisk` and EUMETSAT `eo1.large`.

Which federee are you targeting?
```
