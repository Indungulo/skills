# Troubleshooting

Use this reference when a `firecube` command fails, prints an unexpected error, or behaves differently from older documentation, and you need the likely cause, the fix, and how to gather diagnostics.

Error text below was captured from installed `firecube 0.1.7` unless marked "from source". Paths in captured output are replaced with placeholders.

## First Checks

Run these before debugging anything else:

```bash
firecube --version                      # expect: Firecube 0.1.7
python --version                        # expect: 3.12 or later
firecube plugins list                   # expect your plugin; "No plugins registered." otherwise
firecube <group> <command> --help       # leaf help is authoritative for flags
firecube ingest <plugin-name> --show-options
```

Rules that resolve most errors:

- Every product-locating option needs a full URI: `file:///<abs-path>/<product>.zarr` or `s3://<bucket>/<prefix>/<product>.zarr`.
- `--config-file` is a root option: `firecube --config-file <path> <group> <command>`.
- Plugins, Firecube, and optional extras must live in the same Python environment.

## Symptom, Cause, Fix

| Symptom (stderr) | Cause | Fix |
| --- | --- | --- |
| `No such option '--source'. Hint: Use --input-data (-i) instead (...)` on `ingest` | Flag renamed in the strict-URI refactor | Use `--input-data` (`-i`) for plugin input; `--source` now belongs to `archive create` only |
| `No such option '--source'. Hint: Use --archive (-a) instead` on `archive restore` | Renamed | Pass the `.tgm` path as `--archive` (`-a`) |
| `No such option '--target'. Hint: Use --archive (-a) instead` on `archive create` | Renamed | Output archive is `--archive`; `--target` is reserved for product URIs (`ingest`, `archive restore`) |
| `No such option '--product'. Did you mean '--product-name'?` on `ingest` | Close-match rename | `ingest` uses `--product-name` (`-n`); inspect commands (`zarr`, `parquet`, `catalog`) use `--product` (`-p`) |
| `URI scheme required (file:// or s3://). Did you mean file:///<abs-path>?` | Bare path passed to `--target`, `--product`, `--source`, or `--archive` | Use the suggested `file:///...` form (three slashes) or an `s3://` URI |
| `URI scheme 'file' with non-local host '<host>' not supported.` | `file://<path>` with two slashes | Write `file:///<abs-path>` |
| `URI scheme '<scheme>' not supported.` | `ftp://`, `gs://`, `https://`, or similar | Only `file://` and `s3://` are accepted |
| `authority bucket is required for s3 URIs` | `s3:///<prefix>` without a bucket | Use `s3://<bucket>/<prefix>` |
| `--storage-type 's3' is incompatible with URI scheme 'file'. ...` | Explicit storage type contradicts the URI | Drop `--storage-type` (inferred) or match it to the scheme |
| `Missing --write-mode. Required for all targets (no local-default inference).` (from source) | `ingest` without `--write-mode` | Add `--write-mode direct` or `--write-mode staged` |
| `Missing product name for plugin '<plugin-name>'. Provide one of: ...` (from source) | No `--product-name` and plugin has no `PRODUCT_NAME` | Pass `--product-name <product>` |
| `Unknown option '<key>' for plugin '<plugin-name>'. Valid keys (...)` (from source) | `--option` or `[plugins.<plugin-name>]` key not in any active tier | Run `--show-options`; use `x_` prefix only for experimental keys |
| `Error: Plugin '<plugin-name>' not found.` (`plugins describe`) or `Error: Unknown plugin: <plugin-name>` (`ingest`) | Plugin not installed in this environment, entry point missing, or wrong name | `firecube plugins list`; reinstall with `firecube plugins install [--editable] <path-or-package>` (mutating) into the same environment; confirm the `firecube.plugins` entry point in the plugin's `pyproject.toml` |
| `Failed to load plugin entry point '<plugin>': <SyntaxError or ImportError>` followed by `Error: Unknown plugin: <plugin>` | The plugin package is installed but its module fails to import (a syntax error in `ingestor.py` after an editable install, for example) | Fix the module; editable installs pick up the change without reinstalling (verified) |
| `ResumeConflictError: Existing entries for product ... detected` | Same product re-ingested after success, no resume flag | Choose `--option resume_existing=true` (skip already-present timestamps, refill failed/deleted slots, append the tail) or `--option force_reingest=true` (redo); see ingestion.md |
| `ResumeConflictError: Non-terminal run(s) [...] exist for product ... Abandon them first` | A previous run was killed and is still `started` | `chunks runs abandon`, then rerun with `resume_existing=true`; see chunks-catalog.md |
| `ResumeConflictError: Pipeline run '<run_id>' left N succeeded span(s) in the store (batches: ...). A plain re-run is refused while spans from a failed run exist.` | A prior run failed but had already written some succeeded spans; a plain re-run (no resume flag) is refused | `--option resume_existing=true` to keep the succeeded batches, or `--option force_reingest=true` to redo them |
| `resume_existing=true` does nothing observable, or ingest silently refuses on `GenericParquetIngestor` | Parquet's `GenericParquetIngestor` requires a fresh target unconditionally; resume and force are both refused | Delete the existing output (or pick a new target) before re-running a Parquet plugin; there is no resume path for Parquet |
| `AttributeError: ... has no attribute '_write_lock'` (or another `_` name) after the first batch | The plugin uses a private Firecube attribute (`_write_lock`, `_write_gate`, `_alignment`, `_append_order`) that the core no longer exposes | Use the public `write_lock` property (`with self.write_lock:`) only; run `scripts/check_plugin_contract.py` (plugin-traps.md) |
| `shard_shape=[...] does not match requested shard_shape [...]` or a chunk-shape mismatch on append | The plugin derives the time chunk or shard from the run (for example the number of days in the window) | Fix the time chunk as a store constant; existing stores keep their layout (plugin-traps.md, Zarr Layout Rules) |
| `Group attributes differ from stored; keeping first-write values` on every append | Per-batch values (provenance, counts, run window) in group attributes | Keep attributes constant; move growing or per-step values into arrays along the append dimension |
| `No such option '-t'` on `zarr slots`, `zarr preallocate`, or `zarr index *` | Those commands take only the long flags | Use `--target` and `--product-name` |
| `Plugin '<plugin>' does not support slot-range planning` / `parallelism` | `zarr slots` or `zarr preallocate` on a non-`DirectZarrIngestor` plugin | Expected; parallel slots are only for direct-Zarr plugins |
| `zarr multires` traceback ending in `KeyError: "No variable named 'lat'"` | Product has no `lat`/`lon` variables | Multires needs those variables; not applicable to this product |
| `Group <group>/<dim> has non-datetime dtype int64. Cannot consolidate` or `no time coord, skipping` | `consolidate-time-coord` needs a datetime time coordinate, named via `--time-dim` if not `time` | Pass `--time-dim <name>`; if the dtype is not datetime the cube cannot be consolidated |
| Output written in the wrong format, for example Zarr inside a `.parquet` path | `--output-format` is not validated against the plugin class | Pass the format the plugin's template produces; check with `plugins describe` |
| `chunks list` (or any `chunks` command) silent for minutes | No `-n` given, so it fell back to `[storage]` in `config.toml`, possibly a remote store, and is replaying its runs | Kill it, pass `-n <product-uri>`, run under `timeout` |
| `No plugins registered.` | The plugin is not installed into the environment `firecube` resolves from (an editable install run under one environment, then `firecube` invoked from another) | Run `command -v firecube` and `python -c "import <plugin-module>"` with that same interpreter; reinstall into the environment `firecube` actually resolves from rather than switching how it is invoked |
| `Input data not found: <path>` | `--input-data` path does not exist locally | Fix the path; use an absolute path or `file:///...` |
| Discovery log `"message":"Found 0 files"`, run finishes with nothing written | Source directory empty or no file matched default discovery patterns | Check the directory contents; add `--input-filters '["*.<ext>"]'` or customize discovery in the plugin (plugin-development.md) |
| `ValueError: include_patterns has been removed; use --input-filters` | Plugin or command line still passes `--option include_patterns=...` | Pass `--input-filters '["*.nc4","!*_quicklook.nc"]'` instead (positive globs add to the built-in formats, `!glob` excludes and wins, `\!` escapes a literal `!`, `[]` clears configured filters) |
| `--input-data is required when using default source discovery.` (from source) | Plugin relies on default discovery and no input was given | Pass `--input-data`, or override `discover_source_files()` in the plugin |
| `<command> requires the tensogram extras. Install with: uv pip install 'firecube[tensogram]'` (from source) | `archive create/restore/info/list/validate` without the `tensogram` extra | `uv pip install 'firecube[tensogram]==0.1.7'` in the same environment (the CLI's hint omits the pin; keep it) |
| `Archive not found: file:///<abs-path>/<archive>.tgm` | Wrong archive path | Check the path; use a full `file://` URI |
| `ImportError: obstore is required for --storage-driver obstore. Install it with: uv pip install 'firecube[obstore]'` (traceback) | `--storage-driver obstore` without the extra | Install the extra or use `--storage-driver fsspec` |
| `botocore.exceptions.NoCredentialsError: Unable to locate credentials` (traceback) | `s3://` target with no `FIRECUBE_ACCESS_KEY`/`FIRECUBE_SECRET_KEY` and no ambient AWS auth | Export both variables in the same shell, or set `[storage]` keys; see configuration-storage.md |
| `Failed to resolve storage configuration: StorageConfig requires both --access-key and --secret-key ...` | Only one of key/secret set | Set both or neither (the flags named in the message do not exist; use env vars or `config.toml`) |
| `botocore.exceptions.EndpointConnectionError: Could not connect to the endpoint URL: "<endpoint-url>/..."` (traceback) | Wrong `FIRECUBE_ENDPOINT_URL`, network block, or missing scheme | Check the URL includes `https://`, is reachable, and matches the provider; use `http://` only for loopback or an operator-selected local test service; unset it for AWS |
| `Error: Forbidden` | Credentials valid but not authorized for the bucket/prefix, or wrong bucket | Verify bucket policy, prefix, and `FIRECUBE_PATH_STYLE`; try `path_style = false` for virtual-hosted buckets |
| `Config file not found: <path>` / `Failed to parse config file <path>: ...` / `Unknown config section(s) [...]` (from source) | Explicit `--config-file` is missing, invalid TOML, or has an unknown top-level section | Only `ingest` reports these; fix the path or TOML. Valid sections: `archive`, `database`, `metrics`, `plugins`, `storage` |
| Settings from `config.toml` silently ignored | Wrong path (non-`ingest` commands treat a missing file as empty), wrong `[plugins.<name>]` section name, or CLI/env override winning | Check `firecube plugins describe <plugin-name>` for the exact name; review precedence (CLI > env > file) |
| `Chunk operations require a full product URI or a [storage] configuration in config.toml` | `chunks/*` without `--product-name <uri>` and no `[storage]` config | Pass `--product-name file:///<abs-path>/<product>.zarr` (or `s3://...`) |
| `chunks list --product-name /bare/path` returns `No chunks found` | Bare value treated as a name filter; command fell back to `[storage]` config | Pass the full product URI |
| `Group '<group>' not found in Zarr product.` | Wrong `-g/--group`, wrong product path, or product not yet written | List groups with `firecube chunks list --product-name <uri>` or inspect the store; check the URI |
| `Write-domain claim conflict for <domain> (owner=<run-id>:<group>, stale=true|false)` (from source) | Another writer holds the claim, or a crashed writer left it | If `stale=true` and no writer is alive, clear it; see chunks-catalog.md recovery section |
| `Refusing to clear active claim <domain>; rerun with --force to override.` (from source) | Claim heartbeat is still fresh | Confirm no process is writing, preview with `chunks claims clear --force --dry-run`, then with explicit user confirmation `chunks claims clear --force --yes-i-really-mean-it` (mutating control-plane state; `--force` bypasses only the staleness check, not the confirmation step) |
| `Cannot rebuild snapshot for <product>: blocking claims exist: ...` (from source) | Snapshot rebuild blocked by claims or non-terminal runs | Abandon stale runs and clear claims first; see chunks-catalog.md |
| Run stuck in `started` blocks resume | Firecube cannot prove the old process died | `chunks runs abandon --product-name <uri> --run-id <run-id> --reason "<why>" --dry-run`, then without `--dry-run` plus `--yes-i-really-mean-it` (mutating control-plane state, records only; see cli-surface.md and chunks-catalog.md) |
| `pip`/`uv` refuses to install: `Requires-Python >=3.12` or no matching distribution | Interpreter older than 3.12 | `uv venv --python 3.12` and reinstall; TOML config loading also needs 3.12+ |
| Command prompts for confirmation and hangs in CI | Destructive `chunks`/`archive` command in a non-TTY without the skip flag | Preview with `--dry-run`; execute with `--yes-i-really-mean-it` only after verification |

## Verbose And Debug Output

The CLI has no `--verbose` or `--debug` flag in 0.1.7. Control logging with environment variables (logs go to stderr; command output goes to stdout):

| Variable | Effect |
| --- | --- |
| `FIRECUBE_LOG_FORMAT=plain` | Human-readable lines instead of the default JSON |
| `FIRECUBE_LOG_LEVEL=DEBUG` | Root level; also shows the resolved `StorageConfig` (type, bucket, endpoint, target) |
| `FIRECUBE_DEBUG=true` | DEBUG for Firecube namespaces only, without third-party noise |
| `FIRECUBE_LOG_STRUCTURED_FIELDS=...` | Comma-separated JSON fields |
| `OTEL_DEBUG=true` | Print trace spans to the console when no OTLP endpoint is set |

Example:

```bash
FIRECUBE_LOG_FORMAT=plain FIRECUBE_LOG_LEVEL=DEBUG \
  firecube chunks --quiet list --product-name file:///<abs-path>/<product>.zarr
```

Generic `LOG_LEVEL` and `LOG_FORMAT` are ignored. `FIRECUBE_LOG_LEVEL=WARNING` removes the JSON `INFO` lines that `ingest` and `plugins` commands print by default (neither has a `--quiet` flag). The exit-time warning `Ignoring unknown pipeline summary keys: coverage, rows_ingested` is benign. Suppress ingest progress messages with `--option no_progress=true`. Suppress the `[chunks] storage: ...` banner with `firecube chunks --quiet <command>` (`--quiet` is a `chunks`-group flag: place it before the subcommand, `firecube chunks --quiet list ...`, not after; it no longer leaves a JSON `INFO` line ahead of the table on `chunks`).

Some failures (missing `obstore`, S3 credential and endpoint errors) still surface as full Python tracebacks rather than one-line `Error:` messages; read the last line for the actionable message.

## Reporting A Bug

File issues at https://github.com/eumetsat/firecube/issues. Before posting:

1. Reproduce with the smallest command and confirm with `firecube --version` and `python --version`.
2. Re-run with `FIRECUBE_LOG_FORMAT=plain FIRECUBE_LOG_LEVEL=DEBUG` and capture stderr.
3. Sanitize: replace bucket names, endpoints, local paths, hostnames, and product names with placeholders; remove every `FIRECUBE_ACCESS_KEY`/`FIRECUBE_SECRET_KEY` value and any `[storage]` credential line; drop `hostname` and `process` fields from JSON logs.
4. Include: OS, install method (`uv pip install 'firecube==0.1.7'` or source), extras installed, plugin name and version, the sanitized command, full sanitized output, and expected behavior.
5. Attach `firecube plugins list -f json` and `firecube ingest <plugin-name> --show-options` output when the issue involves options or plugin discovery.

Template:

```text
Firecube: 0.1.7 (Python 3.12.x, Linux)
Plugin: <plugin-name> <version>, installed with `firecube plugins install --editable <path>`
Command:
  firecube ingest <plugin-name> --input-data /<abs-path>/<source-dir> \
    --target file:///<abs-path>/<product>.zarr --product-name <product> \
    --storage-type local --storage-driver fsspec --output-format zarr --write-mode direct
Output (sanitized, FIRECUBE_LOG_LEVEL=DEBUG):
  <paste>
Expected: <what should have happened>
```

## Still On 0.1.5

Everything above describes `firecube 0.1.7`. If `firecube --version` reports `0.1.5`, these differ; install the pinned `firecube==0.1.7` instead of working around them:

- A plain re-run after a same-window ingest fails with `Refusing overlapping resume append for group ...` instead of the 0.1.7 state-aware skip.
- `zarr compare` exits `3` on any difference instead of `0` (equivalent or layout-only) / `1` (content mismatch).
- There is no `--storage-anonymous` flag, `FIRECUBE_S3_ANONYMOUS` env var, or `[storage].anonymous` config key.
- There is no `--input-filters` flag; discovery is controlled only through `--option include_patterns=...`.
- `--option include_patterns=...` is still accepted (0.1.7 rejects it with `include_patterns has been removed; use --input-filters`).
- A plugin's `self._write_lock` is a real private attribute, not an `AttributeError`; there is no public `write_lock` property yet.
- `chunks --quiet <command>` still leaves a JSON `INFO` log line ahead of the table.

## Related References

- configuration-storage.md for URI rules, precedence, and S3 setup.
- cli-surface.md for current flag names per command.
- chunks-catalog.md for run and claim recovery procedures.
- install.md for extras and environment isolation.
- plugin-development.md for entry-point registration and discovery hooks.
