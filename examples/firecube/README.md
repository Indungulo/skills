# Firecube Examples

These examples are sanitized prompt scenarios for the `firecube` skill, grounded in the PyPI release `firecube 0.1.7`. They are not live-current claims about plugin availability, product contents, counts, or timings.

Do not record S3 credentials, private bucket names, user data paths, or copied user data in examples. Source data is always supplied by the user; examples never invent input files.

## Scenarios

| File | Scenario | What it tests |
| --- | --- | --- |
| [install-verify.md](install-verify.md) | Install Firecube from PyPI and verify the CLI | Isolated venv, Python 3.12 requirement, read-only checks, extras |
| [first-ingestion.md](first-ingestion.md) | Run a first ingestion with an installed plugin and user-supplied files | `--show-options`, full target URI, required `--write-mode`, confirmation before writing |
| [no-source-data.md](no-source-data.md) | User names an EUMETSAT collection but has no files | Never invent data, `eumdac` search offered as advice only |
| [template-choice-evidence.md](template-choice-evidence.md) | User asks which template for a named collection with no file | No inference from IDs, filenames, listings, or sibling tutorials; ask for a product or the format spec |
| [existing-plugin-fci.md](existing-plugin-fci.md) | User asks for a plugin a public plugin already covers | Known plugins table checked before scaffolding, L1C vs L2 clarification |
| [plugin-scaffold.md](plugin-scaffold.md) | Scaffold and test a new plugin for a user dataset | Template choice, `plugins create`, editable install, local `file://` test run |
| [crash-recovery.md](crash-recovery.md) | Recover an interrupted ingestion | Read-only chunk inspection first, safe recovery order, destructive confirmation |
| [benchmark-tune.md](benchmark-tune.md) | Benchmark and tune a run | `advise` commands, what to hold constant, tuning knobs, no invented numbers |

## Quirk Handling

Expected answers apply the known 0.1.7 quirks from `cli-surface.md` inside the proposed commands and never narrate them. An example that mentions a quirk in its expected behaviour is describing what the agent does, not what the agent says.

## Safe Validation Boundary

Examples prefer `firecube --version`, leaf `--help`, `plugins list|describe`, `ingest <plugin> --show-options`, `chunks list`, and dry-run flags. Mutating commands appear only with an explicit confirmation step and placeholder URIs.
