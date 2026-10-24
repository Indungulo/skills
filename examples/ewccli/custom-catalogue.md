# Test A Custom EWC Hub Catalogue

## Prompt

Help me test a local EWC Community Hub catalogue before I publish the item.

## Expected Agent Behavior

- Use the `ewccli` skill and load `custom-catalogues.md`.
- Check YAML structure with a parser.
- Use `--path-to-catalog` on the `hub` group, not after the subcommand:

```bash
ewc hub --path-to-catalog <path-to-catalog.yaml> list
ewc hub --path-to-catalog <path-to-catalog.yaml> show <item>
ewc hub --path-to-catalog <path-to-catalog.yaml> deploy <item> --dry-run
```

- Confirm `spec.items`, item name, source, deployable annotations, `pathToRequirementsFile`, `pathToMainFile`, and required inputs.
- Do not put private local paths, credentials, or account details in committed examples.

## Expected Response Shape

- Workflow type: custom catalogue.
- Prerequisites: installed `ewccli`, catalogue path, item source, profile for deploy dry-run.
- Credential safety: no secrets or private path leakage in reusable docs.
- Commands/config: minimal catalogue shape and validation commands.
- Validation status: YAML parse and `ewc hub` checks performed or not run.
