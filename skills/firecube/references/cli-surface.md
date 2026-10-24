# Firecube CLI Surface

Use this reference when you need the full registered command tree of `firecube 0.1.7`, the safety class of a command before running it, or the shared option vocabulary used across subcommands.

Source of truth is the installed `firecube <command> --help` output. The generated online page is https://eumetsat.github.io/firecube/latest/reference/cli/. For per-topic detail see install.md, configuration-storage.md, ingestion.md, zarr-parquet-archive.md, chunks-catalog.md, plugin-development.md, performance.md, and troubleshooting.md.

## Safety Classes

| Class | Meaning | Agent behaviour |
| --- | --- | --- |
| Read-only | Reads storage or metadata, writes nothing | Run freely. |
| Mutating | Creates or changes product data, control-plane records, files, or the Python environment | Confirm target and product name; prefer `--dry-run` where offered. |
| Destructive | Deletes data or performs an irreversible change | Always `--dry-run` first; require explicit user confirmation before `--yes-i-really-mean-it`, `--overwrite`, or `--force`. |

## Global Options

| Option | Scope | Notes |
| --- | --- | --- |
| `--config-file PATH` | Root only, before the subcommand | TOML config, default `~/.config/firecube/config.toml`. `firecube --config-file <path> zarr validate ...` |
| `--version` | Root | Prints `Firecube 0.1.7`. |
| `-h, --help` | Every command | Leaf help includes grouped options, examples, and `See also` lines. |
| `--workspace PATH`, `--quiet` | `firecube chunks` group | Local workspace override and banner suppression; leaf commands also accept `--workspace`. |

## Command Tree

```text
firecube
├── ingest <plugin>                     Core
├── archive {create,info,list,restore,validate}
├── zarr {compare,consolidate-time-coord,multires,preallocate,slots,validate}
│   └── index {show,verify,rebuild}     Inspect
├── parquet {consolidate,validate}
├── chunks {list,delete,delete-span}
│   ├── claims {list,clear}
│   ├── runs {list,abandon}
│   └── snapshots {status,rebuild}
├── catalog intake <plugin>
├── plugins {list,describe,explain,create,install,uninstall}   Tools
├── advise {batch-size,compliance}
└── completion {bash|zsh|fish}
```

Not present in `firecube 0.1.7`: `chunks migrate`, `chunks snapshots list`, a top-level `index` command. Use `chunks snapshots status` and `zarr index show` instead.

## Core

| Command | Purpose | Class | Needs |
| --- | --- | --- | --- |
| `ingest <plugin>` | Run an ingestion job; plugin reads source, Firecube manages write strategy, parallelism, chunk tracking | Mutating | Installed plugin; `--write-mode` required; S3 credentials for `s3://` (or `--storage-anonymous` for a public bucket); `--input-filters` to override discovery |
| `archive create` | Convert a Zarr store to a `.tgm` archive (`-s/--source`, `-a/--archive`) | Mutating; Destructive with `--overwrite` | `tensogram` extra; `--storage-anonymous` for a public source bucket |
| `archive info` | Show archive header metadata (`-f table|json|csv`) | Read-only | `tensogram` extra |
| `archive list` | List per-variable group entries in an archive | Read-only | `tensogram` extra |
| `archive restore` | Decode a `.tgm` archive into a Zarr store (`-a/--archive`, `-t/--target`) | Mutating; Destructive with `--overwrite` | `tensogram` extra; `--storage-anonymous` for a public target bucket |
| `archive validate` | Check archive integrity, exit 0 valid / 1 corrupt; `--quick` skips hashes | Read-only | `tensogram` extra |

`ingest --show-options` is read-only and exits without writing.

## Inspect

### `zarr`

| Command | Purpose | Class | Notes |
| --- | --- | --- | --- |
| `zarr validate` | Validate a group: shapes, dtypes, chunk boundaries, metadata; JSON summary | Read-only | `-p/--product`, `-g/--group` required; `--timeout`, `--max-chunks`, `--on-timeout warn|fail`, `--time-dim`; exits 1 when `is_valid` is false |
| `zarr compare A_URI B_URI` | Compare two stores: exit 0 when equivalent or layout-only (chunk shape, codecs) differences, exit 1 when content mismatches (values, shapes, dtypes, attrs, or missing arrays) | Read-only | `--storage-type`/`--storage-driver` optional, inferred from the URI scheme |
| `zarr slots <plugin>` | Emit chunk-aligned slot ranges for parallel ingestion (Argo/Kubeflow-compatible JSON) | Read-only | `--write-mode` required; `--slot-size`, `--no-resume`, `-f json|table|csv`, `--input-filters` |
| `zarr preallocate <plugin>` | Pre-create arrays for parallel ingestion; idempotent, exits non-zero on schema mismatch | Mutating (`--dry-run` is read-only) | `--write-mode` required; `--slot-start/--slot-end`, `--input-filters` |
| `zarr multires` | Build a multi-resolution pyramid for an existing product | Mutating | `-r/--resolutions` repeatable |
| `zarr consolidate-time-coord` | Rewrite per-slot time coordinate chunks into dense chunks; seals the cube read-only for further ingest | Destructive (irreversible without backup) | Always run `--dry-run` first; `--chunk-size`, `--time-dim`; `--storage-type`/`--storage-driver` required (not inferred) |
| `zarr index show` | Print the resolved-index record; `--json`, `--derived` | Read-only | Exit 3 when no record exists |
| `zarr index verify` | Verify the record and mirrored root attribute; optional `--plugin` | Read-only | Detects legacy records |
| `zarr index rebuild` | Rebuild the record from a plugin declaration | Mutating | `--plugin` required; installed plugin |

### `parquet`

| Command | Purpose | Class | Notes |
| --- | --- | --- | --- |
| `parquet validate` | Check PAR1 magic bytes on every `.parquet` file under the product | Read-only | `-p/--product`; `--storage-anonymous` for a public bucket |
| `parquet consolidate` | Merge scattered files into one via DuckDB; source untouched | Mutating (writes `-o/--output`) | `--codec` default `zstd`; `s3://` output accepted but not yet supported at runtime; `--storage-anonymous` for a public source bucket |

### `chunks`

| Command | Purpose | Class | Notes |
| --- | --- | --- | --- |
| `chunks list` | List tracked chunk records from `.firecube/` for one or all products | Read-only | `-n/--product-name <uri>`, date/span/type/pattern/meta filters, `--time-range` (data time), `-f`, `--limit`; `--include-replaced` also lists replaced spans and spans from failed runs |
| `chunks delete` | Remove chunk records and storage files | Destructive | `--dry-run` first; `--yes-i-really-mean-it`; `--manifest-only`, `--storage-only`; `--include-metadata` deletes `zarr.json` (dangerous); `--all-products`; `--start-date`/`--end-date`/`--range` filter by record time, `--time-range` by data time |
| `chunks delete-span` | Delete storage chunks described by span records (run/batch/group); can NaN-fill in place instead of removing chunk keys (`region_nan_fill`) | Destructive | `--dry-run` first; `--force` allows non-chunk-aligned spans and, when it would also destroy chunks shared with other active spans, additionally needs `--yes-i-really-mean-it` to acknowledge the collateral destruction; `--include-replaced` retries after a partial failure |
| `chunks claims list` | List active write-coordination claims | Read-only | |
| `chunks claims clear` | Release a stale write claim (`--domain`) or all stale claims (`--all-stale`) | Mutating | Bulk mode is a dry run until `--yes-i-really-mean-it`; `--force` skips the stale check |
| `chunks runs list` | List ingestion runs and status | Read-only | `--status started|complete|failed|abandoned` |
| `chunks runs abandon` | Mark a stuck run abandoned to unblock resume | Mutating | `--reason` required; `--run-id` or `--all-stale` |
| `chunks snapshots status` | Show snapshot age and event coverage | Read-only | |
| `chunks snapshots rebuild` | Rebuild the derived snapshot from the event log | Mutating (cache only) | `--dry-run` |

### `catalog`

| Command | Purpose | Class | Notes |
| --- | --- | --- | --- |
| `catalog intake <plugin>` | Write an Intake YAML catalog for a product | Mutating (writes `-o/--output`) | `--collection-id` required; `--no-storage-options` for local or public stores; installed plugin; `--storage-anonymous` for a public product bucket |

## Tools

| Command | Purpose | Class | Notes |
| --- | --- | --- | --- |
| `plugins list` | List registered plugins (entry point `firecube.plugins`) | Read-only | `-f table|json|csv`; prints `No plugins registered.` on a clean install |
| `plugins describe <plugin>` | Show plugin metadata and all `--option` keys with types and defaults | Read-only | |
| `plugins explain <plugin>.<tier>.<field>` | Explain one config option | Read-only | |
| `plugins create <name>` | Scaffold a plugin project | Mutating (writes files) | `--template zarr|parquet|base`, `--write-strategy xarray|zarr-python` (rejected on `--template parquet|base`), `--non-interactive`; `NAME` must start with a letter and use only letters, digits, `-`, `_` |
| `plugins install <spec>...` | Install plugin packages via `uv pip install` | Mutating (environment) | `-e/--editable`; needs `uv` on `PATH` |
| `plugins uninstall <plugin>` | Uninstall the distribution behind a plugin | Mutating (environment) | `--dist` bypasses resolution |
| `advise batch-size` | Recommend `pipeline_batch_size` from the time chunk shape | Read-only | `-p`, `-g` required; `--storage-anonymous` for a public bucket |
| `advise compliance` | Run structural compliance profile (`--profile cf-18`); exit 1 on errors, 2 with `--strict` warnings | Read-only | `--format text|json`; `--storage-anonymous` for a public bucket |
| `completion {bash|zsh|fish}` | Print a shell completion script | Read-only (`--output` writes a file) | |

## Shared Options

| Option | Appears on | Meaning |
| --- | --- | --- |
| `-t, --target URI` | `ingest`, `archive restore`, `zarr multires` (short form); `zarr slots`, `zarr preallocate`, `zarr index *`, `zarr consolidate-time-coord` (long `--target` only) | Product URI, `file:///<abs-path>/<product>.zarr` or `s3://<bucket>/<prefix>`. Strict: relative paths are rejected. |
| `-p, --product URI` | `zarr validate`, `parquet *`, `catalog intake`, `advise *` | Existing product URI; storage flags inferred from the scheme. |
| `--product-name` (`-n` short form on `ingest` and `chunks *` only; `zarr multires\|preallocate\|slots` take the long form only) | `ingest`, `zarr multires\|preallocate\|slots` (logical name) vs `chunks *` (full product URI) | Meaning differs by group: a logical name for ingest/zarr, the full product URI for chunks commands. |
| `-i, --input-data` | `ingest`, `zarr preallocate`, `zarr slots` | Raw plugin input: local path, `file://`, or `s3://` prefix; interpreted by the plugin. |
| `-s, --source` / `-a, --archive` | `archive create`, `archive restore` | Zarr store URI to archive / `.tgm` artifact URI. |
| `-o, --output URI` | `parquet consolidate`, `catalog intake` | Output artifact URI (`file:///...`). |
| `-g, --group` | `zarr validate`, `advise *`, `archive create`, `chunks delete-span` | Group path inside the product, e.g. `<group>/<subgroup>`; `.` or `/` for root in `advise compliance`. |
| `--storage-type local|s3` | Most storage commands | Inferred from URI scheme when omitted; explicit mismatch is rejected. Required on `zarr consolidate-time-coord` only; optional (inferred) everywhere else, including `zarr compare`. |
| `--storage-driver fsspec|obstore` | Most storage commands | Default `fsspec`; `obstore` needs the extra. Also `FIRECUBE_STORAGE_DRIVER` or `[storage].driver`. Required on `zarr consolidate-time-coord` only. |
| `--storage-anonymous` | `ingest`, `archive create\|restore`, `zarr validate\|slots\|multires\|preallocate\|consolidate-time-coord\|compare`, `parquet validate\|consolidate`, `advise batch-size\|compliance`, `catalog intake` (not on `chunks *`) | Presence-only flag: anonymous access for a public `s3://` bucket, overriding any configured or ambient credentials. No opt-out flag. Also `FIRECUBE_S3_ANONYMOUS` or `[storage].anonymous`; precedence CLI > env > config > default `false`. Applies only to `s3://` URIs. |
| `-w, --write-mode staged|direct` | `ingest`, `zarr preallocate`, `zarr slots` | Required; no inference from a local target. |
| `--option key=value` | `ingest`, `zarr preallocate`, `zarr slots` | Plugin or engine option; repeatable. Discover keys with `plugins describe`. List values are JSON arrays: `--option 'bands=["Oa09","Oa12"]'`; `[Oa09,Oa12]` and `Oa09,Oa12` are rejected, a bare `bands=Oa09` is accepted for `list[str]` only. |
| `--input-filters JSON` | `ingest`, `zarr slots`, `zarr preallocate` | One JSON list of glob filters. Positive globs add to the built-in formats; `!glob` excludes matches and exclusions always win; `\!` escapes a literal `!`; `[]` clears configured filters. Case-sensitive. Custom discovery hooks must apply filters themselves. Replaces the removed `--option include_patterns=...`. |
| `--slot-start`, `--slot-end`, `--slot-size` | `ingest`, `zarr preallocate`, `zarr slots` | Parallel ingestion slot window; see performance.md. |
| `--dry-run` | `archive create\|restore`, `zarr consolidate-time-coord`, `zarr preallocate`, `chunks delete*`, `chunks claims clear`, `chunks runs abandon`, `chunks snapshots rebuild` | Report without mutating; not on `archive info\|list\|validate` (read-only already, no flag). |
| `--yes-i-really-mean-it` | `archive create|restore`, `chunks delete*`, `chunks claims clear`, `chunks runs abandon` | Skip prompts; required for destructive operations without a TTY. |
| `--overwrite`, `--force` | `archive create|restore` / `chunks delete-span`, `chunks claims clear` | Escalate to destructive behaviour. |
| `-f, --format` | `archive info`, `zarr slots`, `chunks *`, `plugins *` | `table|json|csv` (some commands only `table|json`); `advise compliance` uses `--format text|json`; `zarr index show` uses `--json`. |
| `--workspace PATH` | `chunks` group and leaves | Local workspace directory override. |

## Renamed Flags (Strict-URI Refactor)

Old flags error out; Firecube adds a `Hint:` line pointing to the new name.

| Command | Old flag | Use instead |
| --- | --- | --- |
| `ingest` | `--source` | `-i, --input-data` (`--source` is now reserved for `archive create`) |
| `archive create` | `--target` | `-a, --archive` (`--target` now means product target URIs only) |
| `archive restore` | `--source` | `-a, --archive` |
| any | `--product` (where `--product-name` is expected) | `--product-name` (Click suggests it automatically) |

## Exit Codes Worth Scripting

| Command | Non-zero meaning |
| --- | --- |
| `archive validate` | 1 corrupted or incomplete |
| `zarr compare` | 1 content mismatch (values, shapes, dtypes, attrs, or missing arrays); 0 on equivalent or layout-only (chunk shape, codec) differences, with a WARNING on stderr for the layout-only case |
| `zarr validate` | 1 when `is_valid` is false |
| `zarr index show` | 1 storage or manifest error, 3 no record |
| `zarr preallocate` | non-zero on schema mismatch (prints expected vs found diff) |
| `advise compliance` | 1 error finding, 2 warning/info under `--strict` |

## Known Quirks In 0.1.7 And What To Do

Agent-facing. Apply these silently; do not present them to the user as defects. Mention one only when the user has already hit it, and then give the fix, not the critique.

| Quirk | What the agent does |
| --- | --- |
| `--output-format` is not checked against the plugin class | Always pass the format the plugin's template produces (`plugins describe` shows the class) and name the target to match |
| `parquet validate` exits 0 even when `valid` is false | Read the JSON `valid` field, never the exit code |
| `chunks` without `-n` falls back to `[storage]` config, possibly a remote store, and can be silent for minutes | Always pass `-n <product-uri>`; run under a shell timeout |
| `--target` has no short form on `zarr slots`, `zarr preallocate`, `zarr index *`, `zarr consolidate-time-coord` | Use the long flag on those; `-t` only on `ingest`, `archive restore`, `zarr multires` |
| `--product-name` means a logical name on `ingest`/`zarr multires\|preallocate\|slots` (no `-n` short form on those `zarr` leaves) but the full URI on `chunks *` (`-n` there) | Pass the value each group expects, and the short form only where it exists |
| `zarr compare` reports `attrs differ` on every array (plus a dtype change, e.g. `timestamp: dtype int64 != float64`) after an archive restore, exit 1 | Verify a restore with `zarr validate` and `chunks runs list`, not `compare` |
| `zarr multires` needs `lat`/`lon` variables and fails with a traceback otherwise | Check the coordinate names first; do not offer multires on products without them |
| `consolidate-time-coord` assumes a dimension named `time` and exits 0 when nothing matches | Pass `--time-dim <name>` explicitly; treat "eligible: 0" as a wrong-flag signal |
| `--option dry_run=true` is accepted but does nothing | Never offer it as a no-write run; use `zarr preallocate --dry-run` or a scratch target |
| Optional-extra and S3 credential errors arrive as tracebacks | Read the last line; give the user the one-line fix |
| Exit-time warning `Ignoring unknown pipeline summary keys` | Ignore it; do not report it |
| `plugins install`/`uninstall` need `uv` on PATH | Check `uv` is available before proposing them in a pip-created venv |
| `-p`/`--product` on `zarr validate`, `parquet *`, `catalog intake`, `advise *` | Use `-p` there, `--target` elsewhere |

## Docs Versus Installed Help

- The installed root help groups commands as `Core`, `Inspect`, `Tools`; the generated online CLI reference is built from the same Click tree and may not show that grouping. Trust `firecube <command> --help` for flags.
- `chunks migrate` and `chunks snapshots list` are not registered in `firecube 0.1.7`.
