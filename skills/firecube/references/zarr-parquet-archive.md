# Firecube Zarr, Parquet, And Archive Operations

Use this reference when operating an existing Firecube product: planning or preallocating parallel Zarr writes, validating Zarr or Parquet output, building multi-resolution layers, comparing two stores, inspecting the resolved index, consolidating Parquet parts, or packaging a Zarr product as a Tensogram `.tgm` archive.

Flags below are verified against `firecube 0.1.7` leaf `--help` output. Run `firecube <group> <command> --help` before finalizing exact flags. For running ingestion itself see ingestion.md; for control-plane records, recovery, and Intake catalogs see chunks-catalog.md; for storage flags and S3 credentials see configuration-storage.md.

## Choose The Output Format

Pick the format from the product shape first; storage (`file://` vs `s3://`) is a separate runtime choice.

| Product shape | Format | Write model | Operate with |
| --- | --- | --- | --- |
| Rows, detections, point observations, feature records | Parquet dataset root of independent part files | Each group/batch writes its own part; parts write concurrently | `firecube parquet validate`, `firecube parquet consolidate` |
| Multidimensional array, complete ordered `xarray.Dataset` batches | Zarr, append model (`GenericZarrIngestor`) | One serialized writer per group; appends along the declared dimension | `firecube zarr validate`, `zarr multires`, `zarr compare` |
| Multidimensional array, declared schema and exact indexed placement | Zarr, direct/region model (`DirectZarrIngestor`) | Plugin emits write intents at absolute indexes; serial unless slot-capable | Above plus `zarr index`, `zarr preallocate`, `zarr slots`, `zarr consolidate-time-coord` |
| Finished Zarr product that must move as one file | Tensogram `.tgm` archive | Packaged from an existing Zarr store; restore recreates Zarr | `firecube archive create|info|list|validate|restore` |

Rules:

- A Parquet target is a dataset root, not one file. Open it as a dataset; use `parquet consolidate` only when a single file is required downstream.
- Parallel Zarr writes are an optional extension of the direct model, not a third class. They need a fixed extent, deterministic indexes, and chunk-aligned slot ranges.
- Zarr and Parquet products carry a `.firecube/` control-plane directory beside the data. Keep it with the product when copying or moving; archives include it.

Docs: https://eumetsat.github.io/firecube/latest/concepts/output-formats/ and https://eumetsat.github.io/firecube/latest/concepts/output-formats/zarr/parallel-writes/

## Safety Labels

| Label | Meaning | Agent behavior |
| --- | --- | --- |
| Read-only | No storage or control-plane mutation | Run when the user asks for a check |
| Mutating | Creates or rewrites product data or control-plane records | Confirm target URI with the user; dry-run first when the flag exists |
| Destructive | Overwrites or irreversibly changes existing data | Dry-run first, show the plan, then get explicit confirmation before running |

Every command below takes a full URI. `--storage-type` is inferred from the scheme (`file://` means `local`, `s3://` means `s3`) where the help says so; only `zarr consolidate-time-coord` requires it explicitly (`zarr compare` also accepts it but infers it when omitted). `--storage-anonymous` is available wherever storage flags are, for a public `s3://` bucket (see configuration-storage.md). Short flags differ per command (verified): `zarr slots`, `zarr preallocate`, and `zarr index *` accept only the long `--target` and `--product-name`; `zarr multires` accepts `-t`; `zarr validate` and `parquet *` use `-p/--product`. `No such option '-t'` means use `--target`.

## Zarr Commands

### `zarr slots` (Read-only)

Emit chunk-aligned, half-open slot ranges for orchestrated parallel ingestion. Resume-aware by default: ranges already recorded complete are excluded.

```bash
firecube zarr slots <plugin-name> \
  --target file:///<abs-path>/<product>.zarr \
  --product-name <product-name> \
  --write-mode direct \
  -f table
```

| Flag | Notes |
| --- | --- |
| `-w, --write-mode [staged\|direct]` | Required |
| `--slot-size INTEGER` | Default: `chunk_shape[0]` of the first array of the first group; must align with the indexed chunk size |
| `--no-resume` | Emit the full `[0, total_slots)` range; not a recovery shortcut |
| `-f, --format [table\|json\|csv]` | Default `json`; JSON is Argo `withItems` / Kubeflow `ParallelFor` compatible and names a `static_owner` range per group |
| `--input-data`, `--input-filters JSON`, `--option KEY=VALUE` | Only when the plugin needs discovery input; `--input-filters` overrides discovery globs (see cli-surface.md Shared Options) |

Feed each planned range to one `firecube ingest ... --slot-start N --slot-end M` worker (see ingestion.md). On a plugin without slot support the command exits 1 with `Plugin '<plugin>' does not support slot-range planning`; `zarr preallocate` says `does not support slot-range parallelism` (verified on a `GenericZarrIngestor` plugin).

### `zarr preallocate` (Mutating; `--dry-run` available)

Create or validate the shared Zarr schema before starting parallel workers. Idempotent: matching arrays are a no-op; a mismatched shape, dtype, or chunk layout exits non-zero with a diff.

```bash
firecube zarr preallocate <plugin-name> \
  --target file:///<abs-path>/<product>.zarr \
  --product-name <product-name> \
  --write-mode direct \
  --dry-run
```

| Flag | Notes |
| --- | --- |
| `--dry-run / --no-dry-run` | Discovery and manifest only; prints the resolved-index manifest as JSON, zero filesystem mutations |
| `-i, --input-data` with `--slot-start` / `--slot-end` | Materialize `TimeAxis.observed` coordinate values for a slot window from source data; `grid` and `explicit` axes skip this |
| `--input-filters JSON` | Overrides discovery globs; see cli-surface.md Shared Options |
| `--option KEY=VALUE` | Plugin or engine option |

Run the dry-run, review the manifest, then rerun without `--dry-run` after confirmation.

### `zarr validate` (Read-only)

Check dimension shapes, dtypes, chunk boundaries, and required metadata for one group. Emits a structured JSON summary and exits 1 when `is_valid` is false; check the exit code, not only the JSON. It does not check whether a group's attributes still describe the whole store: they are frozen at first write and kept on every later append (plugin-traps.md, Zarr Layout Rules, "Group attributes are written once and kept small"; plugin-development.md, Cube design step 5).

```bash
firecube zarr validate \
  -p file:///<abs-path>/<product>.zarr \
  -g <group>
```

Budget flags: `--timeout FLOAT`, `--max-chunks INTEGER`, `--on-timeout [warn|fail]` (default `warn` returns a partial report). `--time-dim <name>` names the time dimension for the static-marker check when it cannot be auto-detected from the stored `firecube_timestamp_state` array. Use `firecube --config-file <path> zarr validate ...` for a non-default config; the root option precedes the subcommand.

### `zarr multires` (Mutating)

Build downsampled resolution layers inside an existing product. Default levels are `1.0` and `0.5`; repeat `-r` to override.

```bash
firecube zarr multires \
  --target file:///<abs-path>/<product>.zarr \
  --product-name <product-name> \
  -r 1.0 -r 0.5
```

No dry-run flag exists. Confirm the target URI and levels with the user, and run `zarr validate` afterwards. The product must carry `lat` and `lon` variables; on a product without them the command fails with a traceback ending in `KeyError: "No variable named 'lat'"` (verified).

### `zarr compare` (Read-only)

Strict equivalence check of two stores: array paths, shape, dtype, chunks, dimension names, public attrs, the `firecube_static_written` marker, and values. Runtime trace attrs are ignored. Exit `0` means equivalent, including when only layout differs (chunk shape, codecs); that case also emits a WARNING to stderr. Exit `1` means a content mismatch (different values, shapes, dtypes, attrs, or a missing array); any other non-zero exit means the command could not run.

```bash
firecube zarr compare \
  file:///<abs-path>/<before>.zarr \
  file:///<abs-path>/<after>.zarr
```

`--storage-type` and `--storage-driver` are optional on both URIs; each is inferred from its own URI scheme (`file://` -> `local`, `s3://` -> `s3`) and the driver defaults to `fsspec` when omitted. `--storage-anonymous` reads a public `s3://` bucket without credentials. Use `compare` to gate promotion after migration, re-ingestion, or a driver change; it is not a tolerant diff tool. Verified: the same input ingested with `--write-mode staged` and `--write-mode direct` compares identical (exit 0); a store restored from a Tensogram archive compares `attrs differ` on every array plus a dtype change (e.g. `timestamp: dtype int64 != float64`), exit 1, so do not use `compare` to verify a restore; use `zarr validate` and `chunks runs list` instead. Docs: https://eumetsat.github.io/firecube/latest/operations/zarr-compare/

### `zarr index show|verify|rebuild`

The resolved-index record at `.firecube/index/current.json` stores the `identity_hash` of the resolved `IndexSpec`; later runs refuse to write if the plugin declaration hashes differently.

| Command | Label | Invocation | Exit codes |
| --- | --- | --- | --- |
| `show` | Read-only | `firecube zarr index show --target file:///<abs-path>/<product>.zarr --product-name <product-name> [--json] [--derived]` | `0` found, `1` storage/manifest error, `3` no record |
| `verify` | Read-only | `firecube zarr index verify --target ... --product-name <product-name> [--plugin <plugin-name>]` | `0` verified, `1` legacy or unreadable, `3` no record |
| `rebuild` | Mutating | `firecube zarr index rebuild --target ... --plugin <plugin-name> --product-name <product-name>` | `0` rebuilt or unchanged, `1` plugin failed or hash conflict |

- On a product written by a `GenericZarrIngestor` plugin, `show` and `verify` exit 3 with `No index record found`; the record exists only for `DirectZarrIngestor` products (verified).
- `show --derived` computes coordinates for regular time-axis groups at read time and never persists.
- `verify --plugin` detects legacy slot-index records from `firecube 0.1.4.post1` and earlier; follow with `rebuild`, then `show` to confirm the hash. No dry-run exists for `rebuild`; it refuses to overwrite a record with a different hash.
- `preallocate --dry-run` prints the same JSON as `index show --json`.

Docs: https://eumetsat.github.io/firecube/latest/operations/firecube-index/

### `zarr consolidate-time-coord` (Destructive; `--dry-run` available)

Rewrite a per-slot `chunks=(1,)` time coordinate into dense chunks so object storage opens the cube with less metadata work. Consolidation seals the cube: it becomes read-only for further ingest, and the change is irreversible without a backup. Always dry-run first and confirm with the user.

```bash
firecube zarr consolidate-time-coord \
  --target file:///<abs-path>/<product>.zarr \
  --product-name <product-name> \
  --storage-type local \
  --storage-driver fsspec \
  --dry-run
```

`--storage-type` and `--storage-driver` are required. Optional: `--storage-anonymous` for a public `s3://` bucket, `--chunk-size INTEGER`, `--time-dim TEXT` for cubes written with a custom `time_dim_name`. Without `--time-dim` a cube whose dimension is not named `time` reports `no time coord, skipping` for every group; the coordinate must also be a datetime dtype, otherwise `Group <group>/<dim> has non-datetime dtype int64. Cannot consolidate` (exit 1, verified). An interrupted local run can be re-run; it detects the `time.consolidating` sibling and repairs it. Consider `archive create` before consolidating a production cube.

## Parquet Commands

### `parquet validate` (Read-only)

Scan every `.parquet` file under the product root for PAR1 magic bytes at head and tail; report missing or corrupt parts. Read the JSON `valid` field: the exit code is 0 even when `valid` is false, for example on a missing product (verified). A Firecube Parquet product is a directory of `part-<product>_batch_NNNN.parquet` files plus `.firecube/`.

```bash
firecube parquet validate -p file:///<abs-path>/<dataset>.parquet
```

### `parquet consolidate` (Mutating)

Merge all parts into one file with DuckDB. The source dataset is not modified; the output is a new artifact.

```bash
firecube parquet consolidate \
  -p file:///<abs-path>/<dataset>.parquet \
  -o file:///<abs-path>/<consolidated>.parquet \
  --codec zstd
```

`-o` must be `file://` in 0.1.7 (`s3://` is accepted by the parser but runtime support is not implemented). Default codec `zstd`. No dry-run; confirm the output path does not clobber an existing file. Prints a JSON `status: success` summary; a missing source exits 1 with `Consolidation failed: IO Error: No files found` (verified). Both `validate` and `consolidate` accept `--storage-anonymous` for a public `s3://` source bucket.

## Tensogram Archive Commands

Install the extra first, pinned to the covered release: `uv pip install 'firecube[tensogram]==0.1.7'` (or the same specifier with `pip install`). Missing extra fails with `requires the tensogram extras`. Archives include the product's ChunkManager records as the final message, so a restored product keeps its run history. Docs: https://eumetsat.github.io/firecube/latest/operations/archive/

| Command | Label | Minimal invocation |
| --- | --- | --- |
| `archive create` | Mutating; Destructive with `--overwrite` | `firecube archive create -s file:///<abs-path>/<product>.zarr -a file:///<abs-path>/<archive>.tgm` |
| `archive info` | Read-only | `firecube archive info -a file:///<abs-path>/<archive>.tgm [-f json]` |
| `archive list` | Read-only | `firecube archive list -a file:///<abs-path>/<archive>.tgm` |
| `archive validate` | Read-only | `firecube archive validate -a file:///<abs-path>/<archive>.tgm [--quick]` |
| `archive restore` | Mutating; Destructive with `--overwrite` | `firecube archive restore -a file:///<abs-path>/<archive>.tgm -t file:///<abs-path>/<restored>.zarr` |

`archive create` flags: `--start-date` / `--end-date` (ISO 8601 window), `-g, --group <group>`, `--variables a,b,c`, `--compression [blosc2|szip|zstd|lz4|zfp|sz3]` (default `zstd`), `--allow-nan/--no-allow-nan`, `--allow-inf/--no-allow-inf`, `--overwrite`, `--dry-run`, `--yes-i-really-mean-it`. Both `create` and `restore` also accept `--storage-anonymous` for a public `s3://` source or target bucket.

`archive validate` exits `0` when valid and `1` when corrupt or incomplete; `--quick` skips hash verification. `archive info -f json` reports `has_controlplane`.

Verified round trip: `create --dry-run` prints the plan; `create` on an existing archive without `--overwrite` exits 1 with `Target file already exists`; `info -f json` reports `has_controlplane: true`; `validate` prints `VALID`; `restore` recreates the groups and records an `archive-restore-<uuid>` run in the restored product.

Overwrite workflow for `create` or `restore`: run with `--overwrite --dry-run`, show the plan, get confirmation, then run with `--overwrite --yes-i-really-mean-it` (required in non-TTY shells). Never add `--yes-i-really-mean-it` on the first attempt.

After `restore`, verify with `firecube chunks runs list --product-name file:///<abs-path>/<restored>.zarr` (an `archive-restore-...` run appears) and `zarr validate`.

## Recommended Sequences

| Goal | Order |
| --- | --- |
| Parallel Zarr ingestion | `preallocate --dry-run` -> `preallocate` -> `slots -f table` -> N x `ingest --slot-start/--slot-end` -> `chunks runs list` -> `zarr validate` |
| Verify a migrated or re-ingested cube | `zarr validate` on each group -> `zarr compare` old vs new -> `zarr index verify` |
| Ship a finished cube | `archive create` -> `archive validate` -> transfer -> `archive restore` -> `chunks runs list` |
| Reduce open-time metadata on S3 | back up (`archive create`) -> `consolidate-time-coord --dry-run` -> confirm -> run -> `zarr validate` |
| Single-file table for downstream tools | `parquet validate` -> `parquet consolidate -o <new file>` |

## Notes And Discrepancies

- Docs pages use `uv run firecube ...`; plain `firecube` works once the environment is activated.
- The archive docs list `--storage-type local --storage-driver fsspec` as prerequisites; in `firecube 0.1.7` those flags are optional on all archive commands and inferred from the URI.
- Report bugs at https://github.com/eumetsat/firecube/issues.
