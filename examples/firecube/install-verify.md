# Install And Verify Firecube

## Prompt

```text
Help me install Firecube from PyPI and verify the CLI.
```

## Expected Agent Behavior

- Route to `install.md`.
- Locate the CLI with `command -v firecube` first. Require Python 3.12 or newer; install as a user tool or into an environment at a path the user names. Never assume a project `.venv` or a personal virtualenv directory.
- Install from PyPI pinned to `firecube==0.1.7`, the release this skill covers; do not run an unpinned install or `--upgrade`, and say why (pre-1.0, no compatibility guarantee between releases).
- Verify with read-only commands only. Do not run `ingest` or any `plugins install`.
- Mention optional extras only when the user's goal needs them, such as `firecube[tensogram]` for archive commands.
- Report `No plugins registered.` as the expected clean-install state, not as an error.

## Safe Setup Pattern

```bash
python3 --version
uv tool install --python 3.12 'firecube==0.1.7'   # executable in ~/.local/bin
# or, into an environment at a path the user names:
uv venv <venv> --python 3.12
uv pip install --python <venv>/bin/python 'firecube==0.1.7'
```

## Verification Commands

```bash
firecube --version
firecube --help
firecube plugins list
```

Observed result shape with `firecube 0.1.7`:

```text
Firecube 0.1.7
No plugins registered.
```

## Safe Response Shape

```text
Workflow type: install
Prerequisites: Python 3.12+, uv or pip, network access to PyPI
Safety boundary: read-only after install; no plugin or data mutation
Validation status: version, help, and plugins list run locally; no ingestion run
```
