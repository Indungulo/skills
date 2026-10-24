# Firecube Ingestion Workflow

Use this reference when a user with an installed Firecube plugin wants to run `firecube ingest`, choose an output format and write mode, run it in parallel or from an orchestrator, or understand what happens on re-run and retry.

Flags below are verified against `firecube 0.1.7` (`firecube ingest --help`). `firecube ingest` is a mutating command: it writes product data and `.firecube/` control-plane records to `--target`.

## Source Data Rule

- The user supplies the source files or storage prefix. Firecube does not fetch data.
- The installed plugin decides which formats, filenames, and directory layout it accepts. Nothing about that is generic; read the plugin's own documentation or `firecube plugins describe <plugin-name>`.
- Never invent source files, product IDs, or paths. If `--input-data` does not exist or is empty, stop and ask.
- If the user only has an EUMETSAT collection ID or product name and no files, hand off to the `eumdac` skill, which owns search, size/space checks, authorisation, and download into a local directory; that directory becomes `--input-data` once the user names it. This skill never downloads.

Official page: https://eumetsat.github.io/firecube/latest/quickstart/source-data/

## Required Inputs

| Flag | Required | Meaning |
| --- | --- | --- |
| `PLUGIN` (positional) | yes | Registered plugin name from `firecube plugins list` |
| `-i, --input-data TEXT` | when the plugin reads command input | Local path, `file:///<abs-path>`, or `s3://<bucket>/<prefix>`; interpreted by the plugin |
| `-t, --target TEXT` | yes | Full product URI: `file:///<abs-path>/<product>.zarr` or `s3://<bucket>/<prefix>/<product>.zarr` |
| `-n, --product-name TEXT` | when the plugin has no `PRODUCT_NAME` default | Logical product name; overrides plugin and config defaults |
| `--output-format TEXT` | recommended | `zarr` (default), `parquet`, or `tensogram` |
| `-w, --write-mode [staged\|direct]` | yes | No inference from the target; always pass it |
| `--storage-type [local\|s3]` | optional | Inferred from the URI scheme; an explicit mismatch is rejected |
| `--storage-driver [fsspec\|obstore]` | optional | Default `fsspec`; `obstore` needs `firecube[obstore]`; covers both the source-side discovery read and the write-domain store |
| `--storage-anonymous` | optional | Unsigned S3 access for public buckets; overrides any credentials in the environment or config file; `s3://` only, ignored on `file://`; no opt-out flag once set by env or config |
| `--input-filters JSON` | optional | One JSON list of filename globs; positive entries add to built-in discovery, `!`-prefixed entries exclude and always win, `[]` clears a configured list; also on `zarr slots` and `zarr preallocate` |

Other flags: `--in-memory` (in-memory DuckDB), `--option KEY=VALUE` (repeatable), `--show-options`, `--slot-start`, `--slot-end`, `--slot-size`, `--slot-group`, `--suppress-static-emission-for-non-owner`, `--static-owner-slot-start`. Root option `--config-file PATH` selects a non-default `config.toml` (see configuration-storage.md).

## Step 1: Inspect The Plugin

```bash
firecube plugins list
firecube plugins describe <plugin-name>
firecube ingest <plugin-name> --show-options
```

`--show-options` exits without writing. It lists engine, template, and plugin option keys accepted by `--option key=value`. Unknown keys are rejected at startup. Plugin-specific keys (for example a horizon, region, or variable filter) come only from this output.

## Step 2: Choose The Output Format

| Product shape | `--output-format` | Plugin class | Write model |
| --- | --- | --- | --- |
| Rows, detections, point observations | `parquet` | `GenericParquetIngestor` | Each batch writes an independent part file under the dataset root |
| Multidimensional cube, complete `xarray.Dataset` batches | `zarr` | `GenericZarrIngestor` | Serialized append along the declared dimension of one group |
| Cube with declared schema and explicit indexed writes | `zarr` | `DirectZarrIngestor` | Indexed placement; optional slot-range parallelism |
| Portable single-file package of a Zarr product | `tensogram` | Dataset-producing plugin | Writes a `.tgm` file; also available post hoc via `firecube archive create` |

The plugin class fixes what is written. `--output-format` is not validated against the plugin class: passing a format the plugin's template does not produce writes that template's actual layout into the mismatched target path anyway, and reports the requested format in the summary regardless of what was written. Always pass the format the plugin's template produces (`firecube plugins describe <plugin-name>` shows the class) and name the target to match. `--output-format tensogram` is rejected for plugins that do not implement `build_dataset` and `get_batch_groups`. Details: zarr-parquet-archive.md and https://eumetsat.github.io/firecube/latest/concepts/output-formats/.

## Step 3: Choose Write Mode And Storage

| Choice | Use when |
| --- | --- |
| `--write-mode direct` | Local targets; final storage is the right commit point; required for slot-range parallel Zarr |
| `--write-mode staged` | Writes go to a local workspace first, then upload; better when S3 direct writes are dominated by per-chunk round trips and scratch disk is available |
| `--storage-driver fsspec` | Default; broad local and S3 support including Parquet and DuckDB |
| `--storage-driver obstore` | Optional Rust-backed S3 path; covers both source-side discovery/materialization and supported Zarr write workloads |

Staged mode options: `--option workspace=<scratch-dir>` and `--option cleanup_workspace=true`. Size the workspace for the full product before uploading. S3 credentials come from `FIRECUBE_ENDPOINT_URL`, `FIRECUBE_REGION`, `FIRECUBE_ACCESS_KEY`, `FIRECUBE_SECRET_KEY`, or `[storage]` in `config.toml`; never put them on the command line (configuration-storage.md).

## Step 4: Common Engine Options

Pass as `--option key=value`; all are listed by `--show-options`.

| Option | Default | Purpose |
| --- | --- | --- |
| `pipeline_batch_size` | 10 | Source items per batch; align with the Zarr time chunk (see `firecube advise batch-size` in performance.md) |
| `pipeline_workers` | 1 | 2 or more runs the parallel pipeline inside one process (worker threads) |
| `pipeline_parallel` | false | Same switch as `pipeline_workers > 1`; either enables the worker pool |
| `extract_workers` | 4 | Parallel archive (ZIP) extraction inside a batch |
| `upload_workers` | 4 | Staged upload concurrency after the pipeline |
| `resume_existing` | false | Continue a compatible incomplete or overlapping run |
| `force_reingest` | false | Re-process spans already recorded; recovery action, not a default |
| `run_id` | generated | Stable ID to correlate with an external job |
| `no_progress` | false | Suppress coarse progress logs |
| `zarr_chunk_shape`, `zarr_sharding`, `zarr_shard_shape`, `zarr_compression`, `dask_scheduler` | template defaults | Zarr layout knobs (performance.md); `zarr_sharding=true` with `zarr_chunk_shape` requires `zarr_shard_shape`; any non-empty `zarr_time_encoding` is a configuration error, set encoding on the dataset instead (plugin-traps.md) |
| `validate_zarr`, `validate_zarr_group`, `validate_zarr_timeout_s`, `validate_zarr_max_chunks`, `validate_zarr_on_timeout` | false | Run `zarr validate` inside the ingest run after writing |
| `incremental` | false | Incremental mode; see `plugins explain <plugin>.engine.incremental` |
| `skip_preflight` | false | Skip the pre-run checks; leave off unless debugging |
| `duckdb_persist_batches` | false | Persist DuckDB batches instead of in-memory tables |
| `workspace`, `cleanup_workspace` | none / false | Staged-mode scratch directory and its cleanup |

`include_patterns` is removed: passing `--option include_patterns=...` raises `ValueError: include_patterns has been removed; use --input-filters`. Use `--input-filters '["*.nc4","!*_quicklook.nc"]'` on the command line, or an `input_filters = [...]` key under `[plugins.<plugin_name>]` in `config.toml`.

Dry run: `EngineConfig` accepts `dry_run=true` but no write path in `firecube 0.1.7` consumes it (ingestion always writes), so do not promise a no-write ingest. For `DirectZarrIngestor` plugins, `firecube zarr preallocate <plugin-name> ... --dry-run` prints the resolved index manifest with zero mutations. For other plugins, run against a small source window into a scratch target instead.

## Minimal Local Example

```bash
firecube ingest <plugin-name> \
  --input-data <input-dir-or-prefix> \
  --target file:///<abs-path>/<product>.zarr \
  --product-name <product> \
  --output-format zarr \
  --write-mode direct
```

Verify:

```bash
firecube chunks list --product-name file:///<abs-path>/<product>.zarr
firecube zarr validate --product file:///<abs-path>/<product>.zarr --group default
```

The final JSON summary goes to stdout and reports the plugin, product, `files_processed`, `stored_at`, `run_id`, and the span coverage written. Logs are JSON lines on stderr; set `FIRECUBE_LOG_LEVEL=WARNING` to keep only warnings. Two warnings are usually benign: `Ignoring unknown pipeline summary keys: coverage, rows_ingested` at exit, and xarray's consolidated-metadata `RuntimeWarning` when opening the store. Generic Zarr plugins write into group `default` unless the plugin declares groups.

## S3 Example

```bash
export FIRECUBE_ENDPOINT_URL="https://<s3-endpoint>"
export FIRECUBE_ACCESS_KEY="<access-key>"
export FIRECUBE_SECRET_KEY="<secret-key>"

firecube ingest <plugin-name> \
  --input-data <input-dir-or-prefix> \
  --target s3://<bucket>/<prefix>/<product>.zarr \
  --product-name <product> \
  --storage-type s3 \
  --storage-driver fsspec \
  --output-format zarr \
  --write-mode staged \
  --option workspace=<scratch-dir> \
  --option cleanup_workspace=true
```

`--input-data` may also be an `s3://<bucket>/<prefix>` when the plugin supports remote sources (it must use `ctx.materialize(item)`; see plugin-development.md).

For a public bucket with no credentials, drop the access-key/secret-key exports and add `--storage-anonymous` (or `FIRECUBE_S3_ANONYMOUS=true`, or `anonymous = true` under `[storage]`); it applies to `s3://` sources and targets only, and there is no opt-out flag once set.

## Execution Shapes

| Shape | Firecube role | Orchestrator role |
| --- | --- | --- |
| One shell command | Whole run | None |
| Cron, CI job, container step | Same command | Scheduling, secrets, logs, retries |
| Multi-step workflow | `ingest` step only | Order: discover, ingest, validate, catalog, notify |
| Fan-out | One process per product, group, partition, or slot range | Deciding what runs concurrently |

Rule: one `firecube ingest` per product target. Keep the command explicit and portable; inject credentials through the environment. Firecube ships no scheduler integration. Docs: https://eumetsat.github.io/firecube/latest/concepts/orchestration/.

## Parallelism And Write Safety

Choose the parallelism model from the plugin's template and the write domain each writer owns, never from CPU count; `pipeline_workers` never makes appends to one Zarr group concurrent. The five models, the safe and unsafe write domains, the slot-range procedure for `DirectZarrIngestor`, and the staged versus direct interplay are in [parallelism.md](parallelism.md). Rule of thumb: safe to run concurrently are different product roots, different Parquet part files, different Zarr groups (separate jobs), and disjoint chunk-aligned slot ranges; never two append writers on one group.

## Re-runs, Retries, Idempotency

| Situation | Behavior | Action |
| --- | --- | --- |
| Same command again after success, no flag | Refused: `ResumeConflictError: Existing entries for product '<product>' (plugin=<plugin>) detected. Rerun with --option resume_existing=true to continue, or --option force_reingest=true to overwrite.` Nothing is written | Decide: continue, redo, or stop |
| Same command again, no flag, after a run that failed but left succeeded spans | Refused: `ResumeConflictError: Pipeline run '<run_id>' left N succeeded span(s) in the store (batches: ...). A plain re-run is refused while spans from a failed run exist. Re-run with --option resume_existing=true to keep the succeeded batches, or --option force_reingest=true to redo them.` | `resume_existing=true` to keep the succeeded batches and retry the rest, or `force_reingest=true` to redo them |
| `resume_existing=true`, same or wider window (append Zarr) | Timestamps already present are skipped, failed or deleted slots are refilled, later timestamps are appended | Extend a store by rerunning a wider window |
| `force_reingest=true` (append Zarr) | Present timestamps are overwritten in place, failed or deleted slots are refilled, new tail timestamps are appended; the non-terminal-run scan is skipped (`runs_enumerated=0`) | Deliberate redo only |
| Either flag, `GenericParquetIngestor` target already has output | Refused unconditionally: a Parquet target accepts exactly one run; resume and force are not supported | Point every run, including a retry after a failure, at a fresh target |
| Retry after a killed or crashed run | Exits 1 with `ResumeConflictError: Non-terminal run(s) [<run-id>] exist for product '<product>'. Abandon them first` | `chunks runs abandon`, then rerun with `resume_existing=true`; see chunks-catalog.md |
| Direct-Zarr re-run with same input | Matching values are no-ops, missing values are filled; a differing value raises schema drift | Fix input or index mapping; nothing is overwritten silently |
| A batch fails mid-run | Batches committed before it stay written; the run stops at the first failed batch; later planned batches are reported as not attempted (`batches_not_attempted` metric, performance.md) | Fix the cause, then rerun with `resume_existing=true` to fill the gap |
| Parallel run, one worker failed | Re-run `firecube zarr slots` (resume-aware) and start only the missing ranges | Validate with `firecube zarr validate` afterwards |

Reproducibility: same inputs, same pinned plugin, same schema give value-identical stores across worker counts and slot splits, including `pipeline_workers > 1` on an append plugin (the ordered write gate keeps batch order); verify with `firecube zarr compare <uri-a> <uri-b>` (exit 0 equal or layout-only differences, exit 1 on a content mismatch). Byte identity needs a pinned environment as well.

## Before You Run Checklist

- Plugin appears in `firecube plugins list` and `--show-options` runs cleanly.
- `--input-data` exists, is non-empty, and matches the plugin's accepted format.
- `--target` is a full URI with the right scheme; `--write-mode` is explicit; `--output-format` is one the plugin supports.
- No other writer targets the same product, group, file, or slot range.
- Storage credentials are in the environment or `config.toml`, not the command.
- Staged mode has enough scratch disk; direct S3 mode has stable network.
- Expected output size and runtime are estimated from a small window first (performance.md).
- `FIRECUBE_LOG_FORMAT`, Pushgateway, and OTLP settings are set if the run must be observed.

## Related

- install.md, cli-surface.md, configuration-storage.md, parallelism.md, zarr-parquet-archive.md, chunks-catalog.md, performance.md, benchmarks.md, troubleshooting.md
- https://eumetsat.github.io/firecube/latest/quickstart/ingestion/
- https://eumetsat.github.io/firecube/latest/concepts/orchestration/retries/
- https://eumetsat.github.io/firecube/latest/concepts/reproducibility/
