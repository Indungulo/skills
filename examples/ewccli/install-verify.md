# Install And Verify EWCCLI

## Prompt

Help me install the European Weather Cloud CLI and verify it works without using credentials.

## Expected Agent Behavior

- Use the `ewccli` skill.
- Recommend Python 3.11+ and an isolated virtual environment.
- Install `ewccli` from PyPI unless the user asks for source or container installation.
- Run only credential-free checks:

```bash
ewc --help
ewc version
ewc login --help
ewc hub --help
ewc infra --help
python -c "import ewccli; print(ewccli.__file__)"
```

- Do not run `ewc login`, `ewc hub deploy`, or `ewc infra create/delete`.
- Mention PATH remediation if the `ewc` script is installed outside `PATH`.

## Expected Response Shape

- Workflow type: install.
- Prerequisites: Python 3.11+, pip/venv, network for package install.
- Credential safety: no credentials needed for verification.
- Commands: concise install and verify block.
- Validation status: local checks performed or commands provided if not run.
