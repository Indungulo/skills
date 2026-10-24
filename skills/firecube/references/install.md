# Firecube Installation

Use this reference when installing, upgrading, verifying, or removing the `firecube` CLI, or when choosing which optional extras to install.

Firecube is a plugin-based batch ingestion CLI that turns Earth Observation products into analysis-ready datacubes (Zarr, Parquet, Tensogram `.tgm`). The core package ships no dataset plugins; see plugin-development.md for plugin installation details and cli-surface.md for the full command tree.

## Requirements

| Requirement | Value | Notes |
| --- | --- | --- |
| Python | 3.12 or later | `firecube 0.1.7` declares `requires-python >=3.12`. |
| Package | `firecube` on PyPI | https://pypi.org/project/firecube/ |
| `uv` on `PATH` | Needed for `firecube plugins install` and `plugins uninstall` regardless of how Firecube itself was installed | Both commands wrap `uv pip install` / `uv pip uninstall` against the interpreter running Firecube. |
| S3 credentials | Only for `s3://` targets | See configuration-storage.md. |

Install into an isolated virtual environment. Do not install into the system Python.

Pin the release this skill covers. Firecube is pre-1.0 and a newer release may rename commands, flags, or plugin hooks, so `firecube==0.1.7` is the version every command in these references was verified against. Move to a newer release only after re-checking `firecube --help` and the changelog at https://github.com/eumetsat/firecube/blob/main/CHANGELOG.md.

## Locate The CLI First

Find the command on `PATH` before proposing any install: `command -v firecube` on Linux and macOS, `where firecube` on Windows. Never assume a project `.venv`, a personal virtualenv directory, or any other path; the user says where their environment is. If the command is missing, install it into one of the standard user-tool locations below, or into a virtual environment at a path the user names (`<venv>`).

| Method | Executable lands in | Environment lives in |
| --- | --- | --- |
| `uv tool install` | `~/.local/bin` (Linux, macOS); `%USERPROFILE%\.local\bin` (Windows) | `~/.local/share/uv/tools`; `%APPDATA%\uv\tools` |
| `pipx install` | `~/.local/bin`; `%USERPROFILE%\.local\bin` | `~/.local/pipx/venvs`; `%USERPROFILE%\pipx\venvs` |
| Virtual environment | `<venv>/bin` (`<venv>\Scripts` on Windows) | `<venv>`, a path the user chooses |

If the executable directory is not on `PATH`, `uv tool update-shell` or adding it to the shell startup file fixes that; say which file only after asking which shell the user runs.

## Install As A User Tool (Recommended)

```bash
uv tool install --python 3.12 'firecube==0.1.7'
firecube --version
```

`firecube plugins install <spec>` installs plugins into this same tool environment, including git URLs (verified). `pipx install --python 3.12 'firecube==0.1.7'` is the equivalent with pipx, but `plugins install` shells out to `uv`, so `uv` must still be on `PATH`.

## Install Into A Virtual Environment

When the user wants Firecube inside a project or a specific environment, use the path they name:

```bash
uv venv <venv> --python 3.12
uv pip install --python <venv>/bin/python 'firecube==0.1.7'
<venv>/bin/firecube --version
```

Or with pip: `python3.12 -m venv <venv>` then `<venv>/bin/python -m pip install 'firecube==0.1.7'`. Activate the environment or call the executable by its full path; `uv` must be on `PATH` for `plugins install` either way.

## Optional Extras

| Extra | Install | Unlocks | Without it |
| --- | --- | --- | --- |
| `tensogram` | `uv pip install 'firecube[tensogram]==0.1.7'` | `firecube archive create|info|list|restore|validate`, `.tgm` archives | Archive commands fail with an error mentioning the tensogram extras. |
| `obstore` | `uv pip install 'firecube[obstore]==0.1.7'` | `--storage-driver obstore` (alternative to the default `fsspec`) | Selecting `obstore` fails with an error containing the install command. |
| `healpix` | `uv pip install 'firecube[healpix]==0.1.7'` | `firecube.ingestor.extensions` HEALPix regridding helpers for plugin code | Plugins importing HEALPix helpers fail at import time. |
| `patterns` | `uv pip install 'firecube[patterns]==0.1.7'` | `firecube.ingestor.extensions.parse_pattern(pattern, text)` (Trollsift filename-pattern parsing) for plugin code | Plugins importing `parse_pattern` fail at import time. |
| `virtualzarr` | `uv pip install 'firecube[virtualzarr]==0.1.7'` | Pins `virtualizarr` as an optional dependency | No CLI command or documented feature in `firecube 0.1.7` requires it; install only when a plugin asks for it. |

Combine extras in one install:

```bash
uv pip install 'firecube[tensogram,obstore]==0.1.7'
```

Extras are declared in the project `pyproject.toml`; see https://github.com/eumetsat/firecube for the current list.

## Upgrade

Do not run an unpinned `--upgrade`. Firecube releases are not guaranteed compatible with each other before 1.0, and installed plugins declare `firecube>=<version>` without an upper bound, so a silent upgrade can break a plugin that worked yesterday. When the user decides to move to a newer release:

```bash
uv pip install 'firecube==<new-version>'
# or
python -m pip install 'firecube==<new-version>'
```

Re-install extras in the same command (`'firecube[tensogram]==<new-version>'`). Afterwards run `firecube --help`, `firecube plugins list`, and the plugin's tests; treat any changed command, flag, or hook as a reason to revalidate this skill against the new release.

## Verify

```bash
firecube --version
firecube --help
firecube plugins list
```

Expected on a clean install of `firecube 0.1.7`:

| Command | Expected output |
| --- | --- |
| `firecube --version` | `Firecube 0.1.7` (any other value means the pin was not applied) |
| `firecube --help` | Command groups `Core`, `Inspect`, `Tools` and the global `--config-file` option |
| `firecube plugins list` | `No plugins registered.` |

`No plugins registered.` is correct before any plugin is installed. Firecube discovers plugins through the `firecube.plugins` Python entry point group, so a plugin must be installed into the same environment as `firecube`.

Optional checks:

```bash
firecube archive --help        # lists commands even without the tensogram extra; execution needs the extra
firecube zarr --help
firecube chunks --help
```

## Shell Completion

`firecube completion {bash|zsh|fish}` prints a completion script. Add one of these lines to the shell profile:

```bash
# bash (~/.bashrc)
eval "$(firecube completion bash)"

# zsh (~/.zshrc)
eval "$(firecube completion zsh)"

# fish
firecube completion fish | source
```

Write the script to a file instead of stdout with `--output <path>`:

```bash
firecube completion zsh --output <workdir>/_firecube
```

Completion only works in shells where the environment containing `firecube` is activated.

## Config File

`firecube --help` reports the default configuration file:

```text
--config-file PATH  Firecube TOML config file (default: ~/.config/firecube/config.toml)
```

The file is optional. Pass `--config-file <path>` before the subcommand to use another file:

```bash
firecube --config-file <workdir>/config.toml ingest <plugin-name> --show-options
```

Precedence is CLI flags, then environment variables (`FIRECUBE_*`), then `config.toml`, then built-in defaults. See configuration-storage.md for the schema and S3 settings.

## Uninstall

```bash
# remove installed plugins first (optional, keeps the environment tidy)
firecube plugins uninstall <plugin-name>

# remove firecube itself
uv pip uninstall firecube
# or
python -m pip uninstall firecube
```

Deleting the virtual environment directory removes everything at once. Uninstalling does not touch product data, `.firecube/` control-plane directories inside products, or `~/.config/firecube/config.toml`.

## For Plugin Developers

Install a plugin project into the same environment as `firecube`:

```bash
firecube plugins install <path-or-spec>             # directory, wheel, sdist, PyPI name, or git+ URL
firecube plugins install --editable <path>          # editable install for local development
firecube plugins list                               # confirm the plugin ID is registered
firecube plugins describe <plugin-name>             # inspect options before ingesting
```

`plugins install` is mutating: it changes the active Python environment through `uv pip install` and then re-checks plugin discovery in a fresh interpreter. Scaffold a new project with `firecube plugins create <plugin-name>`. Full guidance lives in plugin-development.md.

## Links

- Installation quickstart: https://eumetsat.github.io/firecube/latest/quickstart/installation/
- Install the example plugin: https://eumetsat.github.io/firecube/latest/quickstart/plugins/
- Storage drivers and the `obstore` extra: https://eumetsat.github.io/firecube/latest/reference/storage-drivers/
- Archive prerequisites (`tensogram` extra): https://eumetsat.github.io/firecube/latest/operations/archive/
- PyPI: https://pypi.org/project/firecube/
- Issues: https://github.com/eumetsat/firecube/issues
