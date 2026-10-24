# Firecube Parallelism

Use this reference to choose how a Firecube run scales, to judge whether a worker or write-mode guard in a plugin is justified, and to plan concurrent jobs safely. Every statement is verified against `firecube 0.1.7` source or docs; when in doubt, read `firecube/ingestor/runtime/engine.py`, `templates/generic.py`, and `runtime/zarr/write_context.py` in the installed package before claiming Firecube forbids or allows something.

## Choose The Model From The Template

| Template | Parallel inside one job | Parallel across jobs | Write domain of one writer |
| --- | --- | --- | --- |
| `GenericZarrIngestor` (append) | `prepare_batch_data` only; `build_dataset` and the append run under one lock | separate jobs on disjoint groups or products (group fan-out) | one Zarr group |
| `GenericParquetIngestor` | preparation and writes, one part file per batch | separate jobs on disjoint output paths | one part file |
| `DirectZarrIngestor` (region) | preparation; writes are indexed regions | slot workers on disjoint chunk-aligned slot ranges of one group, when the plugin opts in | one slot range |
| `BaseIngestor` (last resort, templates.md) | whatever `_process_batch` does; the plugin owns coordination | plugin-defined | plugin-defined; no engine-provided model applies |
| Tensogram packaging | preparation | separate jobs per `.tgm` output | one `.tgm` file |

## The Five Models

Five models, not interchangeable; each owns a different write domain. Pick from the template and the part of the product each writer owns, never from CPU count. Docs: https://eumetsat.github.io/firecube/latest/concepts/parallelism/ .

| Model | Scope | Template | What runs in parallel | Write domain |
| --- | --- | --- | --- | --- |
| Pipeline workers (`pipeline_workers=N` or `pipeline_parallel=true`) | threads in one `firecube ingest` process | all | source parsing and batch preparation: `prepare_batch_data`; with the append template `build_dataset` runs under the write lock and is serialized | none added: appends to a group stay serialized |
| Parquet file parallelism | same threads | `GenericParquetIngestor` | preparation and writes, one independent part file per batch | one writer per output file |
| Append-Zarr group fan-out | separate `firecube ingest` jobs | `GenericZarrIngestor` | whole jobs, each on disjoint groups or products of a store | one append writer per Zarr group; never two on one group, splitting sources by date does not help |
| Direct-Zarr slot parallelism | separate jobs on one group | `DirectZarrIngestor` with a regular time axis and a declared extent, preallocated | disjoint chunk-aligned slot ranges (procedure in this file) | one writer per slot range |
| Staged upload workers (`upload_workers`) | after the pipeline, `--write-mode staged` | all | upload of staged files to the final target | n/a |

`extract_workers` parallelises archive extraction inside one batch and belongs to none of the models. A plugin that keeps state on its instance from worker-thread hooks must make it thread-safe or keep it on the batch (What The Engine Does, below).

## Slot-Range Parallel Zarr (DirectZarrIngestor Only)

1. `firecube zarr preallocate <plugin-name> --target <uri> --product-name <product> --write-mode direct [--input-data ... --slot-start N --slot-end M]` (idempotent; fails on schema mismatch).
2. `firecube zarr slots <plugin-name> --target <uri> --product-name <product> --write-mode direct [--slot-size N] --format table` (read-only, resume-aware plan; `--format json` is Argo/Kubeflow compatible and names a `static_owner` per group).
3. Start one `firecube ingest ... --write-mode direct --option pipeline_workers=1 --slot-start A --slot-end B [--slot-group <group>]` per planned range. Add `--suppress-static-emission-for-non-owner --static-owner-slot-start <owner-start>` to every worker so only one writes static arrays.
4. `firecube chunks runs list --product-name <uri>` to confirm every range completed.

Indexed schedulers can set `JOB_COMPLETION_INDEX` plus `FIRECUBE_SLOT_SIZE` (or `FIRECUBE_SLOT_START`/`FIRECUBE_SLOT_END`) instead of slot flags; explicit flags win. Never use slot flags with `GenericZarrIngestor` or `GenericParquetIngestor`. Full procedure: https://eumetsat.github.io/firecube/latest/operations/parallel-zarr-writes/.

## Write Safety

Safe to run concurrently: different product roots, different Parquet part files, different Zarr groups (when the plugin allows), disjoint chunk-aligned direct-Zarr slot ranges.

Serialize: two append-Zarr writers on the same group (splitting sources by date does not help), overlapping slot ranges, two jobs writing one output file, and any cleanup or claim clearing while a writer is active.

Firecube fails closed: it blocks conflicting active runs, rejects misaligned or overlapping slot ranges, and stops on stale claims until they are handled (chunks-catalog.md).

Remote input materialization uses a per-URI lock, not one process-wide lock: distinct source URIs materialize in parallel, an identical URI is deduplicated to one download shared with waiters, and a failed download releases its lock so a retry can proceed. This affects fetch concurrency only, not the write domain.

## What The Engine Does

What the engine does with the plugin's code, verified in the 0.1.7 source; design state and guards from these facts, not from caution. The hook contract (what a plugin may override or call) is in [plugin-traps.md](plugin-traps.md).

| Fact | Consequence for the plugin |
| --- | --- |
| `pipeline_workers` is a `ThreadPoolExecutor` inside one process. Worker threads run `prepare_batch_data`, `build_dataset` and `cleanup_batch_data`; the engine calls `on_batch_success` and `on_batch_failure` on the main thread as batches complete | Instance attributes touched from `prepare_batch_data` or `build_dataset` are shared across threads: keep per-batch state on the batch or in the returned dataset, or make it thread-safe. State touched only from `on_batch_success` is not racing. A `pipeline_workers != 1` guard is a shortcut, not a fix: it must name the shared state it protects and what would lift it. Threads share one interpreter: pure-Python work (JSON, per-object loops, xarray bookkeeping) in these hooks holds the GIL and runs on one core however many workers there are; CPU-heavy work goes to worker processes (performance.md, CPU Work In Plugins) |
| The append template serialises writes per ingestor instance and calls `build_dataset` inside that section; `prepare_batch_data` runs before it. An `OrderedWriteGate` commits batches in planner order and stops after the first failed batch; a `pipeline_workers > 1` run produces a store value-identical to a one-worker run, since only preparation runs concurrently | Under the append template only `prepare_batch_data` runs in parallel. Decoding, binning or concatenation placed in `build_dataset` is serialized with the writes, so workers gain nothing until that work moves to `prepare_batch_data` (results kept on the batch) and `build_dataset` only assembles. Parallel group writes exist only as separate `firecube ingest` jobs on disjoint groups or products (group fan-out); two append writers on one group are never safe. Never touch the private gate; a hook that must open the store from the main thread uses the public `write_lock` property, and a plugin does not add its own ordering machinery |
| Only `DirectZarrIngestor` lets several processes write one group, on disjoint chunk-aligned slot ranges | `index_spec` from constants (`zarr slots` and `zarr preallocate` call it before any source data is read), deterministic `inspect_item` coordinates, arrays sized from `resolved_index(ctx).size(group)`, chunks aligned to the slot size, a regular time axis with a declared extent, and `zarr preallocate` before the workers start. Never slot flags with the Generic templates |
| Under `--write-mode staged` the batches write to a scratch store and the target appears only at completion; under `direct` the target is written in place | A hook that opens `ctx.target` itself (to stamp attributes, read receipts) fails or is overwritten under `staged`. Group state belongs in the dataset returned by `build_dataset`: constant values as attributes (written once, first write wins), anything that grows or varies per step as arrays along the append dimension; the root of the store is not the plugin's. Read the target only for read-only checks at discovery. If one mode cannot be supported, reject it in `discover_source_files` with the reason, before any write |
| Items returned by `discover_source_files` may be any object: `str(item)` is its URI in manifests, `item_size_bytes(item)` its size, `ctx.materialize` is optional | A bundle of files (an orbit, a day) can be one item, which keeps a time step atomic under any batch size. That is the clean way to stop the engine's count-based batching from splitting a composite |
| The engine reads the append dimension from the class declaration `time_dim_name` before the first batch | A plugin with two outputs on different axes registers two ingestor classes (one per axis, shared code). Never override `run()` or the private `_resolve_time_dim_name` to switch it per option |
| Reruns: the engine tracks spans and claims itself (`chunks runs`, `chunks claims`) | Plugin-side completion markers duplicate that and drift after failed runs, staged writes and fan-out. Do not keep them; never return `[]` from discovery to skip work (plugin-traps.md, Resume) |

## Write Mode Interplay

| Mode | Where batches write | Consequences |
| --- | --- | --- |
| `--write-mode direct` | the target, in place | required for slot-range parallel Zarr; plugin hooks may read the target for read-only checks; local targets and stable S3 |
| `--write-mode staged` | a scratch workspace, then upload to the target with `upload_workers` | the target does not exist during batches: hooks that open `ctx.target` fail or are overwritten at completion; needs scratch disk for the whole product; the upload phase is a separate parallelism model |

A plugin that supports only one mode must say so and reject the other in `discover_source_files`, before any write, with the reason.

## Verify Parallel Runs

- Same inputs, same pinned plugin, same schema give value-identical stores across worker counts and slot splits: `firecube zarr compare <uri-a> <uri-b>` (exit 0 equal or layout-only differences; exit 1 on a content mismatch; `--storage-type`/`--storage-driver` are optional, inferred from the URI). Run it whenever a parallelism change should not alter values.
- `firecube chunks runs list --product-name <uri>` confirms every slot range or job completed; `chunks claims list` shows who holds a write domain.
- Firecube fails closed: it blocks conflicting active runs, rejects misaligned or overlapping slot ranges, and stops on stale claims until they are handled (chunks-catalog.md).

## Common Mistakes

- Expecting `pipeline_workers` to make append-Zarr writes concurrent, or to speed up work done inside `build_dataset` under the append template.
- Running two `GenericZarrIngestor` jobs against the same group, or splitting sources by date and thinking that makes it safe.
- Using slot flags with `GenericZarrIngestor` or `GenericParquetIngestor`.
- Adding a one-worker or one-write-mode guard to a plugin without naming the shared state or hook it protects; that is an implementation limit and must be documented as one.
- Increasing worker count before checking whether upload or storage is the bottleneck (benchmarks.md).
- Raising `pipeline_workers` for pure-Python work in `prepare_batch_data` and reading "no speedup" as a write bottleneck: check parent versus worker CPU first (performance.md).
- Clearing runs or claims before verifying no writer is still active.

## Related

- ingestion.md (running a job), templates.md (contracts per template), benchmarks.md (measuring the effect), chunks-catalog.md (claims and runs), performance.md (tuning knobs)
- https://eumetsat.github.io/firecube/latest/concepts/parallelism/
- https://eumetsat.github.io/firecube/latest/concepts/output-formats/zarr/parallel-writes/
