# Install EUMDAC

Use this reference for installing EUMDAC and checking the local environment.

## Locate The CLI First

Find the command on `PATH` before proposing any install: `command -v eumdac` on Linux and macOS, `where eumdac` on Windows. Never assume a project `.venv`, a personal virtualenv directory, or any other path; the user says where their environment is. If the command is missing, install it into one of the standard user-tool locations below, or into a virtual environment at a path the user names (`<venv>`).

| Method | Executable lands in | Environment lives in |
| --- | --- | --- |
| `uv tool install` | `~/.local/bin` (Linux, macOS); `%USERPROFILE%\.local\bin` (Windows) | `~/.local/share/uv/tools`; `%APPDATA%\uv\tools` |
| `pipx install` | `~/.local/bin`; `%USERPROFILE%\.local\bin` | `~/.local/pipx/venvs`; `%USERPROFILE%\pipx\venvs` |
| Virtual environment | `<venv>/bin` (`<venv>\Scripts` on Windows) | `<venv>`, a path the user chooses |

If the executable directory is not on `PATH`, `uv tool update-shell` or adding it to the shell startup file fixes that; say which file only after asking which shell the user runs.

## Installation Choices

As a user tool, which keeps it out of every project environment:

```bash
uv tool install 'eumdac==3.1.1'
eumdac --version
```

Into a virtual environment at a path the user names:

```bash
uv venv <venv>
uv pip install --python <venv>/bin/python 'eumdac==3.1.1'
<venv>/bin/eumdac --version
```

For an existing Python environment:

```bash
python -m pip install 'eumdac==3.1.1'
eumdac --version
```

With pipx:

```bash
pipx install 'eumdac==3.1.1'
eumdac --version
```

For conda, use the official EUMETSAT channel package guidance:

```bash
conda install -c eumetsat-forge eumdac=3.1.1
eumdac --version
```

EUMDAC also publishes standalone CLI binaries in its GitLab releases. Mention this option when Python installation is not possible; check that the release tag is `3.1.1`.

Do not run an unpinned install or `--upgrade`; this skill is verified against 3.1.1 only. When the user decides to move to a newer release, install that exact version and re-check `--help` for the commands you use.

## Verification

Run these credential-free checks:

```bash
eumdac --version
eumdac --help
python -c "import eumdac; print(eumdac.__version__)"
```

## Version-Specific Behavior

After installation, inspect the installed CLI instead of relying only on docs:

```bash
eumdac --help
```

For example, the validated `eumdac 3.1.1` package uses `describe` for Data Store discovery/listing.
