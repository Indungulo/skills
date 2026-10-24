# Firecube Plugin Templates

One section per template: when it fits, its contract, how the engine runs it, and a verified skeleton. Choose the template from the cube design (plugin-development.md, "Design The Cube Before Choosing The Format"), never from the file layout alone. Flags, hooks, and behaviours are verified against `firecube 0.1.7`.

## Batch Lifecycle (All Templates)

`BaseIngestor.run()` validates and merges the configuration tiers, discovers and batches the source items (by count, `pipeline_batch_size`; the plugin cannot align batches, but an item may be any object, so a bundle of files can be one item), opens telemetry and acquires the ChunkManager write claims, then calls `_process_batch` once per batch, aggregates metrics, and records the run so it is idempotent and resumable. `run()` itself is framework-owned: never override it (the hook contract is in [plugin-traps.md](plugin-traps.md)). The templates implement `_process_batch` and delegate to `build_dataset` or `build_write_intents`. Worker threads run `prepare_batch_data`, `build_dataset`, `cleanup_batch_data`; the main thread runs `on_batch_success` and `on_batch_failure` as batches complete (parallelism.md).

## Hook Matrix

| Hook (signature) | Zarr Append | Parquet | Direct Zarr | Base |
| --- | --- | --- | --- | --- |
| `build_dataset(group, items, ctx) -> xr.Dataset \| None` | must | - | - | - |
| `build_dataset(group, batch: PipelineBatch, ctx) -> pa.Table \| DataFrame \| None` | - | must | - | - |
| `index_spec(ctx)`, `inspect_item(item, ctx)`, `zarr_schema(ctx)`, `build_write_intents(batch, ctx)` | - | - | must | - |
| `_process_batch(batch, ctx) -> PipelineResult` | - | - | - | must |
| `discover_source_files(ctx)`, `filter_item(item, ctx)`, `item_size_bytes(item)` | may | may | may | may |
| `get_batch_groups(items, ctx)` | may | may | derived | may |
| `batch_setup(ctx)` / `batch_teardown(ctx)` (call `super()`) | may | may | not wrapped | call manually |

The full MUST/SHOULD/CAN/DO NOT contract, including hooks never to override (`run`, `_create_batches`, `finalize_pipeline`, `_aggregate_metrics`, `_resolve_time_dim_name`), is in [plugin-traps.md](plugin-traps.md). Other optional hooks (`prepare_batch_data`, `cleanup_batch_data`, `on_pipeline_start`, `on_batch_success`, `on_batch_failure`, `output_relpath`, `write_parquet`, `get_zarr_config`, `slice_meta*`, `validation_group`, `catalog_group_info`): https://eumetsat.github.io/firecube/latest/reference/hooks/ and .../reference/templates/ .

## GenericZarrIngestor (Append)

Fits: one array per time step on a native or regular grid, constant shape once files are combined per time unit, appended along time; or per-unit groups of varying extent (a swath strip per orbit) appended along the acquisition axis with `get_batch_groups`. Scaffold: `firecube plugins create <name> --template zarr`.

Contract: `build_dataset(group, items, ctx) -> xr.Dataset | None` (required); optional `discover_source_files`, `filter_item`, `item_size_bytes`, `get_batch_groups`, `batch_setup`, `prepare_batch_data`, `cleanup_batch_data`, `batch_teardown`, `get_zarr_config`, `on_batch_success`, `on_batch_failure`. `time_dim_name: ClassVar[str]` is the append dimension and must be a dimension of every returned dataset with size above zero; the writer skips a group whose dataset lacks it without a log line. The engine reads it from the class before the first batch; it is a class declaration, not an option, so a plugin with two outputs on different axes registers one ingestor class per axis.

Order, read from `runtime/base.py`, `runtime/batching.py`, `runtime/engine.py` and `templates/generic.py` in 0.1.7:

| When | Hooks, in order |
| --- | --- |
| Run setup and planning | `discover_source_files` (every item, every time), `filter_item` per item, `get_batch_groups` per planned batch |
| Once, after planning, before the first batch | `on_pipeline_start(ctx, state)`; there is no `on_pipeline_end` |
| Per batch, outside the ordered write gate, parallel across workers | `batch_setup`, `prepare_batch_data`, `get_batch_groups` again (an empty list becomes `["default"]`) |
| Per batch, inside the ordered write turn | `build_dataset` once per group, then the append |
| Per batch, in a `finally`, on success and on failure | `cleanup_batch_data` (its exceptions are logged and swallowed), `batch_teardown`; then `on_batch_success` or `on_batch_failure` on the main thread |

Runtime: writes are serialised per instance through an `OrderedWriteGate`; `build_dataset` and the append run inside that section, `prepare_batch_data` before it. Batches commit in planner order and the run stops at the first failed batch; later planned batches are reported as not attempted, never written out of order. Appends to one group are serialized; group fan-out is separate jobs. Reruns: same command with no flag is refused with `ResumeConflictError`, including when an earlier failed run left succeeded spans in the store; `resume_existing=true` skips present timestamps and refills failed or deleted slots before appending the tail; `force_reingest=true` overwrites present timestamps in place, refills, and appends the tail. The time chunk and shard shape, static variables, and group attributes are fixed by the first write; appends must match them (plugin-traps.md, Zarr Layout Rules). Every batch must return the same schema for a group; combine files without changing values unless the operator chose an aggregated output (plugin-development.md).

```python
@register_ingestor("<plugin_name>")
class MyIngestor(GenericZarrIngestor):
    PRODUCT_NAME: ClassVar[str] = "<product>"
    time_dim_name: ClassVar[str] = "timestamp"

    def build_dataset(self, group: str, items: list[Any], ctx: PluginContext) -> xr.Dataset | None:
        if not items:
            return None
        datasets = [xr.open_dataset(ctx.materialize(item)).load() for item in items]
        return xr.concat(datasets, dim=self.time_dim_name).sortby(self.time_dim_name)
```

Normalize dimensions, coordinates, and dtypes so every batch has the same schema; keep appends to one group serialized. Coordinates and attributes follow the rules in procedure step 5.

## GenericParquetIngestor

Fits: point or event records with no natural array shape, or per-pixel records wanted for filtering and joins. Scaffold: `--template parquet`.

Contract: `build_dataset(group, batch: PipelineBatch, ctx) -> pa.Table | pandas.DataFrame | None` (required; takes the whole batch, read `batch.items`); optional `write_parquet` (custom writer, GeoParquet metadata), `output_relpath`, `discover_source_files`, `filter_item`, `item_size_bytes`, `get_batch_groups`, `batch_setup`, `prepare_batch_data` (store intermediates in `batch.metadata`), `cleanup_batch_data`, `batch_teardown`, `on_batch_success`, `on_batch_failure`. `DuckDbMixin` adds `setup_duckdb`, `prepare_duckdb_schema`, `teardown_duckdb`; `duckdb_persist_batches=true` requires them.

Runtime: each batch writes an independent part file, so `pipeline_workers` parallelises preparation and writes. The target is a dataset root of part files. `parquet_partition_by` and `parquet_row_group_size` are declared but not applied by the default writer. `GenericParquetIngestor` requires a fresh target for every run: it refuses `resume_existing=true` and `force_reingest=true` outright, including on a retry after a failed run. Point every run at a new, empty target.

```python
@register_ingestor("<plugin_name>")
class MyIngestor(GenericParquetIngestor):
    PRODUCT_NAME: ClassVar[str] = "<product>"

    def build_dataset(self, group: str, batch: PipelineBatch, ctx: PluginContext) -> pa.Table | None:
        if not batch.items:
            return None
        return pa.concat_tables(pyarrow.csv.read_csv(ctx.materialize(i)) for i in batch.items)
```

Read from `batch.items`, not `batch`.

## DirectZarrIngestor (Region, Auto)

Fits: arrays at known positions on a declared time axis with a fixed extent or known shape; out-of-order arrival; sparse slices; parallel writers on one group. Scaffold: `--template zarr --write-strategy zarr-python`; requires `--write-mode direct`.

Contract: `index_spec(ctx) -> IndexSpec` (product constant; `zarr slots` and `zarr preallocate` call it before any source data is read), `inspect_item(item, ctx) -> ItemInfo | None` (real observation time; `None` skips, `coordinate=None` fails loudly), `zarr_schema(ctx) -> list[ZarrGroupSpec]` (size arrays from `resolved_index(ctx).size(group)`, never from the input files), `build_write_intents(batch, ctx) -> list[WriteIntent | IndexedWrite]`. Axes: `RegularTimeAxis` (`TimeAxis.observed`/`grid`), `IrregularTimeAxis` (`explicit`, `discovered` with `AUTO`, which costs a full source pass), `IntegerAxis(slot_count=N)`. `get_batch_groups` is derived; `batch_setup`/`batch_teardown` are not wrapped.

Runtime: writes are indexed regions into a preallocated store; a slot written twice is overwritten, not merged, so the plugin must place each observation once or read-modify-write itself. Reruns: slot writes are rewritten, coordinate values are verified and a differing value raises schema drift. Static arrays (`WriteIntent.static`) are write-once and byte-compared on rerun. Slot-range parallelism needs a regular time axis with a declared extent, deterministic `inspect_item` coordinates, arrays sized from the resolved index, chunk alignment, and `zarr preallocate` first (parallelism.md). Declare the time coordinate with `chunks=None` and let core materialize it; never write it yourself.

```python
@register_ingestor("<plugin_name>")
class MyIngestor(DirectZarrIngestor):
    PRODUCT_NAME: ClassVar[str] = "<product>"

    def index_spec(self, ctx):                        # product constant; must resolve without source data
        axis = TimeAxis.observed(coordinate="timestamp", epoch="<iso-start>", cadence_s=600, end_date="<iso-end>")
        # Auto: axis = TimeAxis.discovered(coordinate="timestamp")   # grid()/explicit() also exist
        return IndexSpec(name="<product>_v1", groups={"data": axis})

    def inspect_item(self, item, ctx):                # real observation time, not a rounded slot time
        ts, _ = read_product_item(ctx.materialize(item))
        return ItemInfo(coordinate=ts)                # None skips; coordinate=None fails loudly

    def zarr_schema(self, ctx):
        n = self.resolved_index(ctx).size("data")     # never size arrays from the input files
        return [ZarrGroupSpec(group="data", coord_names=frozenset({"timestamp"}), arrays=[
            ZarrArraySpec(name="timestamp", shape=(n,), dtype="datetime64[ns]", chunks=(24,), dimension_names=("timestamp",)),
            ZarrArraySpec(name="value", shape=(n, 4), dtype="float32", chunks=(1, 4), dimension_names=("timestamp", "sample")),
        ])]

    def build_write_intents(self, batch: PipelineBatch, ctx: PluginContext):
        out = []
        for item in batch.items:
            ts, values = read_product_item(ctx.materialize(item))
            out.append(IndexedWrite.slot(group="data", array="value", coordinate=ts, data=values))
        return out                                    # add WriteIntent.static(...) for lat/lon grids
```

Write factories: `IndexedWrite.slot` / `.region` (Firecube resolves the slot and emits the coordinate write), `WriteIntent.static` (arrays off the time axis), `WriteIntent.slot` / `.region` / `.coordinate` with a self-resolved `index=` from `self.resolved_index(ctx).position("data", ts)`. `TimeAxis` constructors: `observed`, `grid`, `explicit`, `discovered`; `IntegerAxis(slot_count=N)` for positional products. `inspect_item` runs during discovery and again while writing: keep it pure; duplicate timestamps are refused. Reference: https://eumetsat.github.io/firecube/latest/reference/parallelism/ .

## BaseIngestor (Last Resort)

This is the raw engine contract every template is built on, not a fourth template. Choose it only when a serious limitation of the three templates has been named and verified in their source, and the operator has decided so knowing the cost: no runtime-managed writer, no public storage-writer protocol yet, no format-aware resume or schema drift checks, no `zarr validate`/`compare` guarantees about the layout, and none of the parallelism models; the plugin owns every write and all coordination. Wanting a specialised pipeline, more control, or a hook the template lacks is not a limitation: extend the template first (items as bundles, `get_batch_groups`, `prepare_batch_data`, `get_zarr_config`, `write_parquet`, direct-Zarr write intents). Scaffold: `--template base`.

Contract: `_process_batch(batch, ctx) -> PipelineResult`, the only underscore hook a plugin implements; metrics roll up by default (`default_aggregate_metrics`). Do not override `_aggregate_metrics` for run-end work. The engine still discovers, batches, claims, records, and resumes; the plugin owns every write and all coordination between workers. Call `batch_setup`/`batch_teardown` yourself when a mixin needs them.

```python
@register_ingestor("<plugin_name>")
class MyIngestor(BaseIngestor):
    PRODUCT_NAME: ClassVar[str] = "<product>"

    def _process_batch(self, batch: PipelineBatch, ctx: PluginContext) -> PipelineResult:
        target_dir = local_path_from_target(ctx.target or "")     # from firecube.core.api
        self.batch_setup(ctx)                                     # only when a mixin such as DuckDbMixin is used
        try:
            for item in batch.items:
                write_product_item(ctx.materialize(item), target_dir)   # plugin-owned writer
        finally:
            self.batch_teardown(ctx)
        return PipelineResult(batch=batch, outputs=OutputPaths(primary=target_dir))
```

The removed `output_path=` argument is not accepted; use `outputs=OutputPaths(primary=...)` and declared `ResultMetrics` fields. The plugin owns coordination when several workers touch one output.

## GenericTensogramIngestor

Exists in `firecube.ingestor.api` for `.tgm` archive outputs; one writer per output file. Not documented in this skill beyond the archive commands in zarr-parquet-archive.md; read `firecube.ingestor.api.GenericTensogramIngestor` and the upstream API reference before recommending it.

## Context, Batch, Results, Exceptions

| Object | Members plugin authors use |
| --- | --- |
| `PluginContext` | `source`, `target`, `output_format`, `in_memory`, `storage`, `temp_root`, `force_reingest`, `incremental`, `dry_run`, `run_id`, `telemetry`, `options`, `option(key, default)`, `materialize(item) -> Path` |
| `PipelineBatch` | `batch_id`, `items`, `data_path`, `metadata`, `size_bytes`, `files_count`, `groups` |
| `PipelineResult` | `batch`, `outputs: OutputPaths(primary, zarr)`, `metrics`, `success`, `error`, `output_format` |

Always resolve items through `ctx.materialize(item)` before a local-only reader. Reference: https://eumetsat.github.io/firecube/latest/reference/context/ .

| Exception (from `firecube.ingestor.api`) | When |
| --- | --- |
| `ConfigurationError` (subclass of `IngestorError`) | Options or index declaration invalid for this product |
| `IndexedWriteCompilationError` | Firecube cannot map an `IndexedWrite.coordinate` to a slot |
| `MissingIrregularCoordinateError`, `DuplicateIrregularCoordinateError`, `NoDiscoveredItemsError` | `TimeAxis.discovered` discovery failures |
| `ExtentUnknownError`, `UnboundedAxisError` | Regular axis without a fixed extent |
| `SchemaDriftError`, `SchemaSizeMismatchError` | Existing store disagrees with the declared schema |
| `ResumeConflictError`, `RangeOverlapError`, `WriteIntentRangeError` | Resume or slot-range conflicts |
| `ManifestError`, `StorageError` | Shared control-plane and storage errors |

Reference: https://eumetsat.github.io/firecube/latest/reference/exceptions/ ; plain `ValueError` from a reader is fine for malformed items.

## Related

- plugin-development.md (design procedure, template choice, options, tests, packaging), parallelism.md (what the engine runs where), ingestion.md (running the plugin), benchmarks.md
- https://eumetsat.github.io/firecube/latest/reference/templates/ , .../reference/hooks/ , .../concepts/plugins/
