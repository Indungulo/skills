# Firecube Benchmarks

Use this reference to measure a Firecube run reproducibly: before tuning, when comparing parallelism or write modes, when a plugin claims a limit ("needs one worker"), and when recording production expectations. Tuning knobs and bottleneck triage are in performance.md; the parallelism models are in parallelism.md.

## Measure First

Find the dominant phase before changing anything: discovery and preprocessing, writes, staged upload, validation, or memory pressure. More workers only help when they target the bottleneck.

Hold constant between runs:

- source window (same file list and total bytes), plugin version, Firecube version;
- target storage type, driver, and endpoint;
- output format, write mode, chunk shape, sharding, compression;
- machine class, and whether staged workspace is local SSD or network disk.

Record per run: `pipeline_batch_size`, `pipeline_workers`, `upload_workers`, pipeline duration, upload duration, total duration, non-CPU wait, files processed, failed batches, storage errors. Change one setting per run. The published numbers at https://eumetsat.github.io/firecube/latest/concepts/benchmarks/ are workload examples, not guarantees.

## What A Benchmark Can Show, Per Template

| Template | Knobs that can change throughput | Knobs that cannot | Equivalence check |
| --- | --- | --- | --- |
| `GenericZarrIngestor` (append) | `pipeline_batch_size` aligned to the time chunk; `pipeline_workers` only for work in `prepare_batch_data`; chunk shape, sharding, compression; `--write-mode staged` on S3; separate jobs per group | `pipeline_workers` for work in `build_dataset` (runs under the write lock); slot flags (rejected) | `firecube zarr compare` between stores from different worker counts or batch sizes: values must be identical |
| `GenericParquetIngestor` | `pipeline_workers` (preparation and part-file writes), `pipeline_batch_size` (part count and size) | - | `parquet validate`; row counts and checksums per part set |
| `DirectZarrIngestor` | number of slot workers, slot size, chunk alignment, `--write-mode direct`; `pipeline_batch_size` | `pipeline_workers` above 1 inside a slot worker (keep 1) | `firecube zarr compare` between a 1-worker and an N-worker store; `chunks runs list` shows all ranges complete |
| Any | `extract_workers` for ZIP sources on fast disk; `upload_workers` in staged mode | - | manifest `metrics.storage` bytes and files equal |

A plugin that restricts a knob (one worker, one write mode) must show the measurement or the mechanism behind the restriction; "untested" is a limitation to state, not a benchmark result.

## Record Per Run

| Field | Source |
| --- | --- |
| Settings actually used: `pipeline_batch_size`, `pipeline_workers`, `extract_workers`, `upload_workers`, write mode, chunk shape, sharding, compression | command line, `firecube_pipeline_workers`, `firecube_pipeline_batch_size` |
| Pipeline, upload, and total duration; non-CPU wait; CPU utilization estimate | `firecube_pipeline_duration_seconds`, `firecube_pipeline_upload_duration_seconds`, `firecube_run_duration_seconds`, `firecube_pipeline_non_cpu_wait_seconds`, `firecube_pipeline_cpu_utilization_estimate` |
| Files processed, bytes ingested, failed batches, storage errors | `firecube_files_processed_total`, `firecube_bytes_ingested_total`, `firecube_pipeline_batches_failed_total`, `firecube_storage_client_*` |
| Peak memory | `firecube_process_memory_peak_rss_bytes` (best effort) or `/usr/bin/time -v` |
| Output size and object count | ingest JSON manifest `metrics.storage` (`bytes`, `files`) |
| Source window identity | file list and total bytes, or a checksum of the list |

Without a Pushgateway the ingest JSON manifest and `/usr/bin/time -v` give durations, sizes, and peak RSS; that is enough for a comparison table.

## Benchmark Workflow

1. Pick one representative day or bounded source window and a scratch target.
2. Run once with defaults; record the fields listed under Measure First.
3. Change exactly one knob; re-run against a fresh target (or `force_reingest=true` deliberately).
4. Compare pipeline versus upload split before comparing totals.
5. Confirm output equivalence with `firecube zarr compare <uri-a> <uri-b>` (exit 0 equal) when the change should not alter values.

Published workload summaries (examples only): a large-grid append workload where staged writes plus sharding beat direct writes and upload could still dominate; a CPU-bound small-file workload where workers plus aligned batches gave a large speedup; and a 12-process direct-Zarr slot run reaching roughly 97% parallel efficiency on one host. None compares plugin classes against each other. Details: https://eumetsat.github.io/firecube/latest/concepts/benchmarks/.

## Protocol For Long Runs

- Measure the baseline first, then cap every later run with a timeout near the baseline (or the budget). Abort a run that is already slower than the baseline instead of waiting for it.
- Start each run in its own session (`setsid <command>`) and stop it by process group (`kill -TERM -- -<pgid>`, then `-KILL`). Killing only the parent leaves `spawn` workers running as orphans that distort the next run; check with `ps -eo pid,ppid,pgid,cmd | grep <plugin-or-python>` after every run.
- Sample parent and worker CPU during the run (`pidstat -u -p <pids> 5`) and take a few `py-spy dump`s of the parent; keep them with the run record. The attribution of a bottleneck cites these, not stage-timer sums.
- Treat plugin stage timings as wall intervals: if a stage includes waiting for a lock, the write turn, or a pool result, its duration is queueing. Report compute and wait separately, or use `firecube_pipeline_cpu_duration_seconds` and `firecube_pipeline_non_cpu_wait_seconds`.
- Before reporting a speedup, show value equality with the previous version and with a one-worker run (`firecube zarr compare`).
- A sample window (one day, a few hundred products) mostly measures startup. A number that goes into documentation comes from a run at the stated scale, with the machine, versions, command, and log kept; say what "end to end" includes (download, fetch, ingest) and measure each part.

## Reporting

Report a table with one row per run and the fields above, the source window, the machine class, the Firecube and plugin versions, and the equivalence check result. Two runs of one setting are the minimum before reading a difference; report ranges, not single numbers, when runs disagree. Never compare across different source windows or storage backends in one table. A claim in a README, guide, or talk ("N months in M minutes") names its benchmark record; without one it is removed or marked unmeasured.

## Related

- performance.md (advise commands, tuning knobs, bottleneck-to-action, observability), parallelism.md, ingestion.md, zarr-parquet-archive.md (`zarr compare`, `parquet validate`)
- https://eumetsat.github.io/firecube/latest/concepts/benchmarks/
- https://eumetsat.github.io/firecube/latest/concepts/performance/
