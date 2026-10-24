# Firecube Plugin Contract And Authoring Traps

Read this before writing or reviewing any plugin hook, and again before calling a plugin done. It holds the public hook contract, the resume and Zarr layout rules the engine enforces, and the traps that real plugins fell into. Design comes first (plugin-development.md); per-template skeletons are in templates.md; what runs on which thread is in parallelism.md.

Checked against `firecube 0.1.7` (PyPI release). A plugin still on `0.1.5` sees different behaviour in a few places; see [Still on 0.1.5](troubleshooting.md#still-on-015) for that list.

## Public APIs Only

A plugin uses only:

- imports from `firecube.ingestor.api`, `firecube.core.api`, and `firecube.ingestor.extensions` (and its public submodules);
- the hooks listed below, and public properties such as `write_lock`, `plugin_config`, `engine_config`, `template_config`;
- class declarations: `PRODUCT_NAME`, `time_dim_name`, `plugin_config_class`.

Never: a method or attribute whose name starts with `_` on a Firecube class (`self._write_gate`, `_alignment`, `_append_order`, `_aggregate_metrics`, `_resolve_time_dim_name`, `_create_batches`, `_chunk_manager`), a deep import (`firecube.core.filesystem.*`, `firecube.core.runtime`, `firecube.ingestor.runtime.*`), writing reserved `firecube_*` attributes or arrays, or rewriting an array core manages (the append coordinate, `firecube_timestamp_state`) after core wrote it. The only underscore hook a plugin implements is `_process_batch`, and only when it subclasses `BaseIngestor` directly.

When the public surface cannot express what the product needs, do not work around it: keep the plugin on core's behaviour, write a short handoff note for the Firecube maintainers (problem, core file and symbol, evidence, proposed public change), and tell the operator what the plugin cannot do yet. A workaround that passes tests today breaks on the next core release: an earlier release exposed `self._write_lock` as a private attribute; it is gone now, replaced by the public `write_lock` property, and a plugin that still reads the private name fails after its first batch.

Check mechanically: `python <skill-dir>/scripts/check_plugin_contract.py <plugin-project>` (static, seconds, no data needed).

## Hook Contract

From `BaseIngestor`'s docstring (`src/firecube/ingestor/runtime/base.py`, "MUST/SHOULD/CAN/DO NOT override") and the public hooks reference (`docs/reference/hooks.md`).

| Class | Hooks |
| --- | --- |
| MUST implement | `GenericZarrIngestor`: `build_dataset(group, items, ctx)`. `GenericParquetIngestor`: `build_dataset(group, batch, ctx)`. `DirectZarrIngestor`: `index_spec`, `inspect_item`, `zarr_schema`, `build_write_intents`. `BaseIngestor` only: `_process_batch` |
| SHOULD override | `discover_source_files(ctx)` when the default file walk does not yield exactly one item per product |
| CAN override | `filter_item`, `item_size_bytes`, `get_batch_groups` (not DirectZarr: derived from `zarr_schema`), `slice_meta_keys`, `slice_meta`, `validation_group`, `catalog_group_info`, `on_pipeline_start`, `on_batch_success`, `on_batch_failure`, `prepare_batch_data`, `cleanup_batch_data`, `batch_setup`/`batch_teardown` (call `super()`), `get_zarr_config` (start from `super()`), `write_parquet`, `output_relpath` |
| DO NOT override or call | `run`, `_create_batches`, `finalize_pipeline`, `_aggregate_metrics`, `_resolve_time_dim_name`, any other `_`-prefixed engine or template method |

Rules that follow from the engine:

- `on_batch_success` and `on_batch_failure` run on the main thread. Call `super()`: the base implementation records the span that resume depends on. An exception raised in `on_batch_success` is logged and counted, and the batch stays a success; do not override `run()` to turn that into a failure.
- There is no public end-of-run hook (`on_pipeline_start` exists, no `on_pipeline_end`). Release run-scoped resources with Python lifecycle (a context manager inside one batch hook, `weakref.finalize`), or do the work per batch; record the gap, do not use `_aggregate_metrics`.
- `time_dim_name` is a class declaration, not a per-run option. Two outputs with different append dimensions are two registered ingestor classes in the same package (each with `@register_ingestor`, its own entry-point key, shared reader code and config), never one class that switches its dimension at run time.
- Read options from `self.plugin_config` inside hooks; validate them in the `PluginConfig` `__post_init__`. Nothing needs `run()`.
- Hooks do not open `ctx.target` to write. Group state goes into the dataset returned by `build_dataset` (first write only, see layout rules); per-slot state goes into arrays along the append dimension. A read-only check of the target (for `filter_item`, below) is allowed; reach it through `ctx.storage.output`, the engine-owned `StorageSession` for the output target (`exists(uri)`, `open(uri, mode)`, `ls`, `isdir`, `info`, `find`, and `.zarr` for Zarr access), which works for `s3://` targets as well as local ones, and never through a path you build from `ctx.target` (local only) or a session you open yourself; `PluginContext` and `StorageContext` are exported from `firecube.ingestor.api`, `StorageSession` is not, so take it from the context and do not replace or close it; wrap any store access from a hook in `with self.write_lock:`.

## Resume, Rerun, Extension

Core owns completeness. The control plane (`.firecube/` runs and spans) and, for append Zarr, the per-slot `firecube_timestamp_state` array say what is written; the plugin does not keep its own receipts.

`ResumeGuard` decision matrix (`src/firecube/ingestor/runtime/resume_guard.py`), evaluated before discovery:

| Non-terminal run exists | `force_reingest` | `resume_existing` | Outcome |
| --- | --- | --- | --- |
| yes | false | any | blocked: `chunks runs abandon` first |
| yes | true | any | continue, overwrite |
| no, spans exist | false | false | `ResumeConflictError` naming both flags |
| no | false | true | continue, resume |
| no | true | any | continue, overwrite |

The `no, spans exist / false / false` row has two messages depending on why the spans exist: see the new row below for a failed run that left succeeded spans.

What each flag does to a `GenericZarrIngestor` store:

| Run | Result |
| --- | --- |
| Same window again, no flag | Refused: `ResumeConflictError: Existing entries for product '<product>' (plugin=<plugin>) detected. Rerun with --option resume_existing=true to continue, or --option force_reingest=true to overwrite.` Nothing is read |
| Same window again, no flag, after a run that failed but left succeeded spans | Refused: `ResumeConflictError: Pipeline run '<run_id>' left N succeeded span(s) in the store (batches: ...). A plain re-run is refused while spans from a failed run exist. Re-run with --option resume_existing=true to keep the succeeded batches, or --option force_reingest=true to redo them.` |
| `resume_existing=true`, same or wider window | Timestamps already present (state 1) are skipped, failed or deleted slots (state 2, 3) are refilled, later timestamps are appended |
| `force_reingest=true` | Present timestamps are overwritten in place, failed or deleted slots refilled, new tail timestamps appended; the non-terminal-run scan is skipped (`runs_enumerated=0`) |
| Any flag, a timestamp earlier than the stored maximum that is absent | Refused: append Zarr cannot insert (no backfill); use DirectZarr for out-of-order days |
| Changed chunk or shard shape, changed static variable | Refused (`SchemaDriftError` or shard-shape mismatch) |
| `GenericParquetIngestor`, any flag | Refused unconditionally: resume and force are not supported; every run, including a retry, needs a fresh target |

A plugin still on `0.1.5` sees `resume_existing=true` refuse overlapping timestamps instead of skipping them; see [Still on 0.1.5](troubleshooting.md#still-on-015).

Plugin rules:

1. `discover_source_files` returns every item for the requested inputs, every time. Never return `[]` (or an empty iterable) to signal "already complete" or "dry run": core then plans nothing, its skip/overwrite/refusal logic never runs, and the store can never be extended. Raise `ConfigurationError` for invalid input instead.
2. Declare the store's invariant recipe through `slice_meta_keys()` and, when validated defaults matter, `slice_meta(ctx)` (the default `slice_meta` only includes keys present on the command line). The recipe holds what must not change for one store (variables, grid, resolution, bbox, product type, epoch, chunking), never the run window (`start`, `end`) or access settings (endpoints, credentials, cache paths). Core records it with every span; a changed slice is treated as a fresh slice, so also write the recipe as a small attribute of the dataset returned by `build_dataset` (first write wins) and, when the target exists, compare it read-only in `on_pipeline_start` and refuse with `ConfigurationError` naming the field that differs.
3. `filter_item(item, ctx)` may drop items whose timestamps are already present under `resume_existing` (read-only check of the append coordinate and `firecube_timestamp_state == 1`) to avoid preparing data core would skip. Under `force_reingest` keep every item. Core's skip stays authoritative.
4. A time unit written partially stays "present" forever under `resume_existing`. Reject windows that cut a time unit (a daily cube with `start=10:00`), or document that the boundary units need `force_reingest`.
5. Core does not detect changed inputs for a present timestamp. Document that revised source products need `force_reingest=true` over the affected window.
6. Test all four: rerun without a flag (refused), rerun with `resume_existing` over the same overlapping window (expect no change: present timestamps are skipped), extension with `resume_existing` over a genuinely new window (equal to a one-shot build), `force_reingest` (equal values). For `GenericParquetIngestor`, skip these four and instead confirm a rerun into the same target is refused regardless of flag. `scripts/check_done.py` runs the Zarr checks; on a large input pass `--quick` (lifecycle on one product), and for a plugin that bins or resamples onto another grid pass `--regridded`.

## Zarr Layout Rules

| Rule | Why | Do |
| --- | --- | --- |
| Never return `""` or `"/"` from `get_batch_groups` | Firecube's helpers treat both as the store root and pass the group to xarray unchanged; a direct-mode write to the root removed the store's `.firecube/` control directory and the run exited 1 (measured on 0.1.7, 2026-10-07); the behaviour is not documented anywhere in core | Keep the default `["default"]` or a non-empty group name, and open the store at that group in notebooks and tests |
| The time chunk and shard length is a store constant | Appends must match the stored chunk and shard shape; a chunk equal to the run's length (days in this run) makes every later append fail | A fixed number (for example 10 days, or `firecube advise batch-size` on a scratch store), independent of the run window; align `pipeline_batch_size` to it |
| The time coordinate has one fixed epoch | xarray encodes datetimes relative to the first value it sees, so each store or run gets its own `units` ("days since <first day>") and merges or appends across runs disagree | Set `ds[time].encoding["units"]` (for example `"days since 1970-01-01"`), `dtype`, and `calendar` on the dataset in `build_dataset`; any non-empty `zarr_time_encoding` option, or a non-empty `time_encoding` returned from `get_zarr_config()`, is a configuration error, encoding lives on the dataset only |
| Sharding needs an explicit shard shape | `zarr_sharding=true` together with a configured `zarr_chunk_shape` and no `zarr_shard_shape` is refused before writing | Pass `zarr_shard_shape` alongside `zarr_chunk_shape`, or leave sharding off |
| Group attributes are written once and kept small | On append core keeps the first-write values and logs "keeping first-write values" for any difference; it also snapshots and rewrites all group attributes on every append, so megabytes of attributes are rewritten per batch | Attributes only for what is constant for the store (conventions, grid, product identity). Anything that grows with data or varies per step (source product lists, per-day provenance, baseline, orbit) is an array or coordinate along the append dimension |
| Chunk-alignment warnings are once per group and chunk length | An unaligned batch (a short final write aside) would otherwise log once per batch | Read the once-per-group warning and the run summary; the final short write of a run is exempt only on the last batch |
| Never keep private receipts or completion ledgers in attributes | They diverge from the control plane after any failed or partial run, and are replaced wholesale per run | Rely on `.firecube/` and `firecube_timestamp_state`; per-slot provenance is a data variable |
| GenericZarr coordinate chunks follow `chunk_shape` | Core forces the append coordinate and `firecube_timestamp_state` onto `chunk_shape[time]` (comment "E5" in `runtime/zarr/write.py`); a plugin's `encoding["chunks"]` on the coordinate is ignored | Accept it. Do not rewrite the coordinate after the write (`consolidate-time-coord` seals the cube); a denser coordinate is a core request |
| DirectZarr coordinates are core-managed | `zarr preallocate` materializes the time coordinate densely; `ZarrArraySpec(chunks=None)` lets core choose its chunks | Declare the coordinate with `chunks=None` and let core write it; never write it yourself |
| Schema checks compare what will be merged | A compatibility check keyed by group name never compares two groups that share one time series | Check every variable (dtype, `_FillValue`, scale and offset, units, dims) across every source variant (processing baseline, platform) written into one group, and against the stored schema |
| Identity fields that vary do not split the time series by default | One group per processing baseline gives two time axes for one product | See plugin-development.md, Plugin Design Procedure step 3: ask the operator which values are in scope; if unanswered, keep each in its own group and never merge silently |

### GenericZarr Or DirectZarr

| Need | `GenericZarrIngestor` (append) | `DirectZarrIngestor` (region) |
| --- | --- | --- |
| Writes | One ordered writer for the whole instance: batches commit in planner order; `pipeline_workers` parallelises `prepare_batch_data` only | Indexed slot writes; several `firecube ingest` processes on disjoint chunk-aligned slot ranges |
| Order | Chronological only; no backfill | Any order; backfill into existing slots |
| Horizon | Open-ended; extension is `resume_existing` with later inputs | Declared extent (`end_date`/`slot_count`) for parallel runs; an array smaller than a new horizon must be recreated, so choose it generously |
| Already-written check | `firecube_timestamp_state` plus spans; identical reruns are skipped | Span coverage; identical reruns rewrite slots |
| Choose when | The whole run finishes in acceptable time with one writer | Parallel writers, out-of-order arrival, or backfill are needed |

## Performance Rules

`pipeline_workers` is a thread pool in one Python process. Threads share one interpreter, so pure-Python or GIL-holding work (JSON parsing, per-object loops, xarray bookkeeping) in `prepare_batch_data` runs on one core no matter the worker count. Details, the process-pool pattern, and how to measure it are in performance.md ("CPU Work In Plugins"). The short version:

- CPU-heavy decoding and reduction runs in worker processes; the parent thread only submits, collects, and assembles.
- No per-batch or per-time-step work may scale with the total number of products in the run or the store (metadata rebuilt over every product of a group for every day is O(days x products)).
- Discovery reads names and sizes, not payloads: parse filename fields, parallelise any unavoidable opens, and use container checksums (ZIP CRC32, object ETag) instead of hashing whole payloads.
- Never reuse `pipeline_workers` to size a plugin's own process pool without saying so in the option docs; it is the engine's batch-thread count.

## Authoring Traps

Each row is a known plugin failure pattern. The fix column is the rule; the reference column is where core states it.

| Trap | Symptom | Why it is wrong | Do this instead | Core reference |
| --- | --- | --- | --- | --- |
| Using a private core attribute (`self._write_lock`, `self._write_gate`) | Every run fails after the first batch that touches it | Private names change without notice; `_write_lock` was removed and replaced by the public `write_lock` property | Public API only; `with self.write_lock:`; better, do not touch the store from hooks | `templates/generic.py` `write_lock`; CHANGELOG Removed |
| Overriding `run()` | Resume, force and extension behave unlike the docs; per-run state leaks | `run` is "DO NOT override"; it orders guard, discovery, planning, recording | `on_pipeline_start` for per-run state, `PluginConfig` for options, separate classes for separate append dimensions | `runtime/base.py` hook categories |
| Returning `[]` from discovery when the target "is complete" | Rerun is a silent no-op; a wider window can never extend the store | Core never sees the items, so its skip, append and overwrite never run | Return all items; let `resume_existing`/`force_reingest` decide; `filter_item` for cheap skips | `runtime/resume_guard.py`; `runtime/zarr/append.py` state-aware skip |
| Run window in the recipe equality check | "Incompatible target recipe" on every extension | The window is a run property, not a store property | Window out of `slice_meta`; recipe holds only invariants | `runtime/base_hooks.py` `slice_meta_keys` |
| Time chunk equal to the run length | `shard_shape [...] does not match requested [...]` on the first append | Chunk and shard shape are validated against the store | Fixed time chunk | `runtime/zarr/append.py`, `append_services.py` chunk validation |
| `zarr_chunk_shape` left unset on the Zarr append template | Two independent from-scratch runs of the same input at different `pipeline_batch_size` values write different on-disk chunk shapes for arrays and the append coordinate alike (values still equal, per `zarr compare`) | With no configured `chunk_shape`, the writer auto-derives the inner chunk from the shape of whichever batch writes first, not from a fixed design choice; leaving it unset is itself a decision | Set `zarr_chunk_shape` (and `zarr_shard_shape` if sharding) explicitly before the first real ingestion, even when accepting a modest default | `runtime/zarr/write.py` (`chunk_shape` handling); `runtime/zarr/append_services.py` chunk-length resolution |
| Time encoded relative to the run's first value | Two stores or runs carry different `units`; merges and appends misread time | xarray picks the epoch from the first write unless told | Fixed `encoding["units"]` on the dataset | `templates/generic.py` `build_dataset` docstring ("Declare datetime encoding") |
| Growing provenance in group attributes | `zarr.json` of megabytes; later updates silently ignored | Attributes are first-write and rewritten on every append | Provenance arrays along the append dimension | `runtime/zarr/write.py` snapshot and restore of group attrs |
| Private receipts in root attributes | Receipts list only the days processed so far; they disagree with the store after a failed run | Replaced wholesale per run; not transactional with writes | Control plane and `firecube_timestamp_state` | `docs/reference/control-plane-spec.md` |
| Own ordered-write condition variable | Second deadlock surface; waits hide in stage timings | Core commits batches in planner order and stops after a failure; `pipeline_workers > 1` on an append plugin is value-identical to `pipeline_workers=1` | Rely on the ordered write gate; do not add your own ordering guard | `templates/generic.py` `OrderedWriteGate`, `stop_on_batch_failure` |
| End-of-run work in `_aggregate_metrics` | Works until core renames it | Private metrics roll-up, not a lifecycle hook | Per-batch work or Python lifecycle; handoff note for `on_pipeline_end` | `docs/reference/hooks.md` (not listed) |
| Rewriting a core-managed array after the write (densifying `time`) | Readers can briefly see no coordinate; core alignment and staged comparisons assume its layout | The array belongs to core's writer | Accept core's layout; handoff note | `runtime/zarr/write.py` "E5" |
| Overriding `_resolve_time_dim_name` to switch the append dimension per option | Works until core changes the private hook | `time_dim_name` is a class declaration | One registered class per append dimension | `runtime/base.py` `time_dim_name` docstring |
| CPU work in batch threads | More workers barely improve wall time; parent process near 100% CPU, workers idle | GIL | Worker processes; parent only assembles | performance.md |
| Per-day metadata over all products | Run time grows with days x products | O(total) inside a per-step loop | Compute group metadata once, or per step from that step's products | performance.md |
| Serial discovery that opens and hashes every payload | Discovery is a third of the run | Reads the full input before the first batch | Filename fields, container checksums, parallel opens | performance.md |
| Plugin-only source access (`file://` only) | Remote inputs must be downloaded by hand first | Core discovery lists `s3://`; items can be any object | Core discovery or `discover_input_files(storage_config=...)`; for many small objects, a bounded parallel fetch in the plugin, cached under `ctx.temp_root` | `docs/guides/plugins/source-discovery.md` |
| Overriding `discover_source_files` without forwarding the operator's filters | An operator's `--input-filters` value has no effect on a plugin with a custom discovery hook | Overriding the hook does not inherit `input_filters`; `discover_input_files` only applies it when passed explicitly | Forward `self.engine_config.input_filters` to `discover_input_files(..., preferred_globs=self.engine_config.input_filters)` inside the override | `core/formats/discovery.py` `preferred_globs`; plugin-development.md, Source Discovery |
| A directory holds more than one product type or cadence sharing the same variable schema | Discovery selects every matching file; a file from the wrong cadence or type lands in a batch meant for one product | Default discovery selects by suffix only; an identical schema does not mean an identical product | Exclude by pattern inside `discover_source_files` (a smaller suffix set, `exclude=`, or `filter_item`) and still forward `--input-filters` for the operator's own ad-hoc use | `core/formats/discovery.py`; plugin-development.md, Source Discovery |
| A paired-source item (a tuple or object holding several files) returned from `discover_source_files` | Feasibility byte counts read zero, or `ctx.materialize` fails on the whole item | The default `item_size_bytes` calls `Path(item).stat().st_size` and falls back to `None` on a non-path item; `ctx.materialize` resolves one item at a time, not a tuple | Follow the paired-source-files guide: call `ctx.materialize` once per element inside `build_dataset`, and override `item_size_bytes` if accurate feasibility numbers matter | `runtime/base.py`, `runtime/batching.py` `item_size_bytes` default; `docs/guides/plugins/paired-source-files.md` |
| Tests that need data outside the repository | Fresh checkout: dozens of errors, unnoticed | A fixture guard that checks only that a directory exists lets tests run against the wrong or empty data | Small fixtures in the repository, or skip when the fixture is absent or incomplete; zero errors on a fresh checkout | plugin-development.md, Definition Of Done |
| Docs or notebooks naming files that do not exist, or numbers never measured at scale | Users follow a runner script that is not there; an extrapolated throughput claim is off by an order of magnitude | Claims without evidence | Every referenced path exists; every performance number cites a full-scale benchmark record | benchmarks.md, Reporting |
| Stale contributor guidance ("keep `pipeline_workers=1`") contradicting code and docs | Contributors and agents follow the wrong rule | Docs drift from the plugin | Update CONTRIBUTING with the code change; grep for the option name before release | - |
| No explicit time encoding in `read_dataset` | First ingestion at the default batch size passes | xarray infers `units` per batch from the values it sees; single-item batches (a split-batch check with `pipeline_batch_size=1`, or a genuinely small batch) can infer clashing units and write inconsistent encodings across batches | Declare a fixed `encoding["units"]` and `calendar` on the time coordinate in `read_dataset`, not left to inference; run once with `pipeline_batch_size=1` and compare against a normal-batch-size run with `firecube zarr compare` | `templates/generic.py` `build_dataset` docstring; `check_plugin_contract.py` `time-encoding` WARN |

A plugin still pinned to `firecube==0.1.5` sees several of the facts above differently (write coordination, `resume_existing` on overlap, `zarr compare` exit codes, discovery filters, Parquet reruns, the generated scaffold's `time_dim_name`): see [Still on 0.1.5](troubleshooting.md#still-on-015) for the full list.

Pin the Firecube version in the plugin (`firecube==<version>`), run the Definition Of Done against that version, and re-run it before moving the pin.
