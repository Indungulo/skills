# Firecube Performance And Benchmarking

Use this reference when a Firecube run is slow, memory-bound, or needs a reproducible benchmark; when choosing batch size, workers, chunking, or write mode; or when enabling metrics, logs, and traces to measure a run.

Flags are verified against `firecube 0.1.7`. `firecube advise` commands are read-only. Tuning knobs are `--option key=value` settings on `firecube ingest` (ingestion.md).

## Measure First

Find the dominant phase before changing anything; more workers only help when they target the bottleneck. The reproducible procedure, what to hold constant, what to record, and the per-template expectations are in [benchmarks.md](benchmarks.md), "Measure First".

## `firecube advise batch-size`

Recommends `pipeline_batch_size` from the Zarr store's time chunk shape so batches do not produce partial chunks. Run it on an existing (or preallocated) product before a long job.

| Flag | Required | Meaning |
| --- | --- | --- |
| `-p, --product TEXT` | yes | Product URI (`file:///<abs-path>/<product>.zarr` or `s3://<bucket>/<prefix>/<product>.zarr`); storage flags inferred from scheme |
| `-g, --group TEXT` | yes | Group path inside the product, e.g. `default` or `F024/FWI` |
| `--storage-type [local\|s3]` | no | Override inferred locality |
| `--storage-driver [fsspec\|obstore]` | no | Storage backend |
| `--storage-anonymous` | no | Unsigned S3 access for public buckets |

```bash
firecube advise batch-size -p file:///<abs-path>/<product>.zarr -g default
# then
firecube ingest <plugin-name> ... --option pipeline_batch_size=<N>
```

Output shape (verified): `Recommended: --option pipeline_batch_size=<N>` followed by a one-line `Rationale:` naming the time chunk size.

## `firecube advise compliance`

Runs structural CF checks on a Zarr cube. Exit codes: 0 clean (warnings and info allowed), 1 any error finding, 2 warnings or info under `--strict`.

| Flag | Required | Meaning |
| --- | --- | --- |
| `--profile [cf-18]` | yes | Only `cf-18` exists currently |
| `-p, --product TEXT` | yes | Product URI |
| `-g, --group TEXT` | yes | `.` or `/` for root, otherwise e.g. `F024/FWI` |
| `--format [text\|json]` | no | Default `text`; use `json` for CI |
| `--strict` | no | Exit 2 on any warning or info |
| `--storage-type`, `--storage-driver`, `--storage-anonymous` | no | As above |

```bash
firecube advise compliance --profile cf-18 -p file:///<abs-path>/<product>.zarr -g . --format json --strict
```

Use it as a post-ingest gate together with `firecube zarr validate`. Findings print as `[error] CF001 ...`, `[warning] CF003 ...`, `[info] CF007 ...` lines with a one-line fix each; a product with no `Conventions` attribute exits 1 on CF001 (verified). Plugins set these attributes in `build_dataset`.

## Tuning Knobs

| Option | Default | Stage | Raise when | Lower when |
| --- | --- | --- | --- | --- |
| `pipeline_batch_size` | 10 | Items per batch | Too many tiny Parquet parts; append read-modify-write overhead; batch smaller than time chunk | Memory pressure |
| `pipeline_workers` | 1 | Batch preprocessing threads in one process (2+ = parallel; `pipeline_parallel=true` is the same switch); threads share the GIL | Preprocessing releases the GIL (NumPy, I/O) and CPU is idle | CPU already saturated; memory grows; slot-range workers (keep 1) |
| `extract_workers` | 4 | Archive extraction inside a batch | Many ZIP sources on fast disk | Disk-bound; multiplies with `pipeline_workers` |
| `upload_workers` | 4 | Staged upload after pipeline | Upload phase dominates and bandwidth is free | Object-store throttling |
| `zarr_chunk_shape` | template default | Chunk layout, e.g. `{"timestamp":1,"y":550,"x":475}` | Readers need smaller subsets | Too many small objects |
| `zarr_sharding` (+ `zarr_shard_shape`) | false | Groups chunks into shards | Large grids create too many objects; chatty uploads | Not needed locally |
| `zarr_compression` (+ `zarr_codecs`) | true | Codec pipeline | Upload size is the bottleneck | CPU is the bottleneck |
| `dask_scheduler` | none | Dask thread pool | - | Set `synchronous` when `pipeline_workers` is active to avoid competing pools |
| `zarr_write_empty_chunks` | false | Whether all-fill chunks are written | Byte-identical stores needed | Default is smaller |
| `--write-mode staged` | - | Local workspace then upload | S3 direct writes dominated by per-chunk round trips and scratch disk exists | No scratch disk; local target |
| `--storage-driver obstore` | `fsspec` | Rust-backed S3 path | Supported Zarr S3 workloads after measuring | Parquet/DuckDB remote operations |

`pipeline_workers` never makes same-group Zarr appends concurrent; appends to one group are serialized, and with the append template `build_dataset` itself runs under the write lock, so only work done in `prepare_batch_data` runs in parallel. Parquet batches write independent parts, so workers help both preparation and writes. Only `DirectZarrIngestor` with slot-range support scales one group across processes (ingestion.md).

## CPU Work In Plugins

`pipeline_workers` threads share one Python interpreter. Pure-Python or GIL-holding work in `prepare_batch_data` (JSON parsing, per-product loops, building xarray objects, metadata assembly) runs on one core whatever the worker count; only work that releases the GIL (NumPy kernels, decompression, I/O) scales with threads.

Diagnose before changing code:

| Check | Command | Reading |
| --- | --- | --- |
| Parent versus workers | `pidstat -u -p <parent-pid>,<worker-pids> 5` (or `top -H -p <parent-pid>`) during a batch | Parent near 100% of one core, workers and the machine mostly idle: the bottleneck is plugin code in the parent; more workers will not help |
| Where the parent spends time | `py-spy dump --pid <parent-pid>` a few times, or `py-spy record --subprocesses -o profile.svg --pid <parent-pid>` | Stacks in plugin functions under batch threads name the code to move |
| What a stage timer measures | Read the timer's start and end | A timer that spans a wait (a lock, a write turn, a pool result) measures queueing; sums over parallel batches are neither CPU nor wall time |

Rules:

- CPU-heavy decoding, binning and reduction run in worker processes: a pool created once per run (`on_pipeline_start`, `spawn` context), module-level functions, small picklable arguments (paths, option values), reduced arrays returned rather than whole datasets. The parent thread submits, collects, and assembles. Size the pool with its own plugin option or the CPU count and document how it multiplies with `pipeline_workers`.
- No per-batch or per-time-step work may scale with the total number of products in the run or store. Compute group-level metadata once (one sample per source variant), parse each product's schema once, and build a step's attributes from that step's products only.
- Discovery reads names and sizes, not payloads: take platform and time window from the filename (with a safety margin), identify products by container checksum (ZIP CRC32, object ETag) and size instead of hashing whole payloads, and parallelise any unavoidable opens. Never decompress or hash one product twice.
- Remote fetches are I/O-bound: bounded concurrency (async or threads), results cached under `ctx.temp_root`, disk writes off the event loop.
- Measure the change at full scale before claiming it (benchmarks.md).

## Bottleneck To Action

| Symptom | Try first |
| --- | --- |
| High pipeline time, low CPU utilization estimate, local source | `pipeline_workers=2..4`, then re-measure |
| More workers, no speedup; parent process near one full core, workers idle | GIL-bound plugin code in the parent: profile it (CPU Work In Plugins) and move it to worker processes |
| Discovery is a large share of the run | Plugin discovery reads or hashes payloads serially: filename fields, container checksums, parallel opens |
| Slow Zarr appends on S3 | Align `pipeline_batch_size` with the time chunk; `--write-mode staged`; `zarr_sharding=true`; `dask_scheduler=synchronous` |
| Upload dominates total | `upload_workers=8`, sharding to cut object count, faster workspace disk |
| Thousands of tiny Parquet parts | Larger `pipeline_batch_size` |
| `firecube zarr validate` too slow | `--max-chunks <N> --on-timeout warn` (or `fail` in CI) |
| Out of memory | Lower `pipeline_batch_size`, then `pipeline_workers`; disable compression if CPU and memory are both tight |
| Many `firecube_storage_client_retryable_errors_total` | Endpoint throttling; reduce `upload_workers` or concurrency, check S3 settings |

Common starting points from the docs: large gridded Zarr on S3 with scratch space `--write-mode staged --option dask_scheduler=synchronous --option zarr_sharding=true --option pipeline_batch_size=10 --option upload_workers=4`; CPU-heavy parsing `--option pipeline_workers=4 --option pipeline_batch_size=40`; tabular Parquet `--output-format parquet --option pipeline_workers=4 --option pipeline_batch_size=50`. Treat these as first guesses, then measure.

## Memory And Throughput

- In-flight memory is roughly batch size times worker count times decoded item size, plus compression buffers. Scale one factor at a time on a small window.
- Staged mode needs workspace disk for the whole product plus temporary files; set `workspace=<scratch-dir>` explicitly in containers.
- Throughput comparisons are only meaningful for similar source work; compare per-file or per-timestamp time across products of different sizes.
- The telemetry sink may emit `firecube_process_memory_peak_rss_bytes` on a best-effort basis; use it to size containers.

## Benchmark Workflow

See [benchmarks.md](benchmarks.md).

## Observability For Measurement

Firecube is a batch CLI: no `/metrics` endpoint. Metrics are buffered and pushed once at exit to a Prometheus Pushgateway; logs go to stderr; command output (JSON manifests, tables) goes to stdout; traces flush before exit.

### Enable

| Signal | Setting | Notes |
| --- | --- | --- |
| Metrics | `FIRECUBE_PUSHGATEWAY_URL=https://<pushgateway-host>` or `[metrics] pushgateway_url` in `config.toml` | Absent URL: run proceeds, nothing pushed. Use `http://` only for loopback or an operator-selected local test service. `FIRECUBE_METRICS_DISABLED=true` disables |
| Metric grouping | `FIRECUBE_PUSHGATEWAY_GROUPING_KEYS=instance,plugin,product,<key>` plus `FIRECUBE_PUSHGATEWAY_GROUP_<KEY>=<value>` | Default grouping `instance,plugin,product`; prefer grouping keys over a `run_id` label |
| Extra labels | `FIRECUBE_METRICS_LABEL_ALLOWLIST=<a>,<b>` or `[metrics] label_allowlist` | Base labels: `plugin`, `product`, `output_format`, `write_mode` |
| Logs | `FIRECUBE_LOG_FORMAT=json\|plain`, `FIRECUBE_LOG_LEVEL=INFO`, `FIRECUBE_DEBUG=true`, `FIRECUBE_LOG_STRUCTURED_FIELDS=...` | Generic `LOG_LEVEL`/`LOG_FORMAT` are ignored; JSON lines carry `trace_id` and `span_id` |
| Traces | `OTEL_EXPORTER_OTLP_ENDPOINT=https://<collector>/v1/traces`, optional `OTEL_EXPORTER_OTLP_HEADERS`, `OTEL_DEBUG=true` for console | Service name `firecube-ingestor-<plugin-name>`; `KFP_RUN_ID` is attached as `kfp_run_id`. Use `http://` only for loopback or an operator-selected local test service |
| Correlation | `--option run_id=<external-job-id>` | Carried into ChunkManager records and manifests |

### Key Metric Names

| Metric | Use |
| --- | --- |
| `firecube_run_duration_seconds`, `firecube_pipeline_duration_seconds`, `firecube_pipeline_upload_duration_seconds` | Total, pipeline, and staged upload split |
| `firecube_pipeline_batch_duration_seconds`, `firecube_pipeline_batch_creation_duration_seconds` | Per-batch cost |
| `firecube_pipeline_cpu_duration_seconds`, `firecube_pipeline_non_cpu_wait_seconds`, `firecube_pipeline_cpu_utilization_estimate` | CPU-bound versus I/O-bound |
| `firecube_pipeline_batches_total`, `firecube_pipeline_batches_failed_total`, `firecube_pipeline_batches_not_attempted_total`, `firecube_files_processed_total`, `firecube_bytes_ingested_total`, `firecube_rows_processed_total` | Volume, failures, and batches planned but never attempted after an earlier batch failed |
| `firecube_pipeline_workers`, `firecube_pipeline_batch_size` | Settings actually used |
| `firecube_storage_client_requests_total`, `firecube_storage_client_errors_total`, `firecube_storage_client_retryable_errors_total`, `firecube_storage_client_latency_seconds`, `firecube_storage_client_bytes_written_total` | Storage behavior and throttling |
| `firecube_resume_guard_enforce_duration_seconds` | Cost of resume checks on large histories |

Plugin metrics emitted via `ctx.telemetry.emit(...)` get a `firecube_` prefix and `_total` for counters (plugin-development.md). The generated full table is at https://eumetsat.github.io/firecube/latest/reference/observability/.

### Key Spans

`firecube.cli.ingest` > `firecube.ingest` > `firecube.batch` (per batch), `firecube.finalize`, `firecube.upload_s3`; `GenericZarrIngestor` adds `firecube.batch.prepare` and `firecube.batch.zarr_write`. Batch spans stay under the run trace when `pipeline_workers` is 2 or more.

The ingest JSON manifest also carries `metrics.storage` (`path`, `bytes`, `files`, `duration_s`, `storage_type`) for quick comparisons without a Pushgateway.

## Production Checklist

- One product URI per `firecube ingest`; all required flags explicit.
- Batch size from `firecube advise batch-size` for existing Zarr products.
- Parallelism chosen from plugin class: Parquet workers, Zarr prep-only workers, direct-Zarr slot ranges.
- Staged mode: `workspace` on fast disk, `cleanup_workspace=true`, sized for the product.
- Credentials via environment or `config.toml`; `.firecube/` kept with the product.
- `FIRECUBE_LOG_FORMAT=json`, Pushgateway, and OTLP configured before the first run; `run_id` passed from the orchestrator.
- Post-run gates: `firecube zarr validate` (with a chunk budget), `firecube advise compliance --profile cf-18`, `firecube zarr compare` for reruns.
- Retry policy uses `resume_existing=true` deliberately; recovery via chunks-catalog.md, not `force_reingest` by default.

## Related

- benchmarks.md, parallelism.md, ingestion.md, configuration-storage.md, zarr-parquet-archive.md, chunks-catalog.md, plugin-development.md, troubleshooting.md
- https://eumetsat.github.io/firecube/latest/concepts/performance/
- https://eumetsat.github.io/firecube/latest/concepts/parallelism/
- https://eumetsat.github.io/firecube/latest/concepts/production-guide/
- https://eumetsat.github.io/firecube/latest/concepts/observability/
