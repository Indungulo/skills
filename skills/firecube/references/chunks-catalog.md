# Firecube Chunk Control Plane And Intake Catalogs

Use this reference when inspecting or repairing a product's `.firecube/` control plane (chunk records, runs, claims, snapshots), recovering after a crash, deleting and reingesting a range, or generating an Intake catalog for a finished product.

Flags below are verified against `firecube 0.1.7` leaf `--help` output. Run `firecube chunks <command> --help` before finalizing exact flags. For Zarr/Parquet/archive product commands see zarr-parquet-archive.md; for storage flags and credentials see configuration-storage.md; for error messages see troubleshooting.md.

## What The Control Plane Records

Every Zarr or Parquet product root contains a `.firecube/` directory beside the data. In `firecube chunks`, "chunk" means a control-plane record about run and span coverage, not a physical Zarr array chunk.

| Record | Location | Meaning | Managed by |
| --- | --- | --- | --- |
| Runs | `.firecube/runs/<run_id>/run.json` + WAL `events-NNNNN.jsonl` | One ingestion or maintenance execution: `started`, `complete`, `failed`, `abandoned` | `chunks runs list|abandon` |
| Spans | WAL events, projected into snapshots | What one batch wrote: group, batch id, time or index coverage | `chunks list --include-span`, `chunks delete-span` |
| Claims | `.firecube/claims/<sha256>.json` | Exclusive write lock on a `product:category:name` domain with a heartbeat; stale after `stale_threshold_s` (default 120 s) | `chunks claims list|clear` |
| Snapshots | `.firecube/snapshots/snapshot-<generation>.jsonl` + `LATEST.json` | Derived read model for fast listing; safe to delete and rebuild | `chunks snapshots status|rebuild` |
| Resolved index | `.firecube/index/current.json` | Identity hash of the declared `IndexSpec` | `zarr index` (see zarr-parquet-archive.md) |

Rules:

- The WAL under `.firecube/runs/` is authoritative; snapshots are cache.
- Never edit `.firecube/` files by hand. Keep the directory with the product when moving or copying it.
- Pass the full product URI through `-n, --product-name` (`file:///<abs-path>/<product>.zarr` or `s3://<bucket>/<prefix>/<product>.zarr`). This binds the command to the product without extra storage configuration, except for storage-deleting commands (see below).
- `--workspace PATH` overrides the local workspace; `--quiet` on the `chunks` group suppresses the storage banner (it is a group-level flag, so place it before the subcommand: `firecube chunks --quiet list ...`, not after).
- Without `-n`, every `chunks` command falls back to `[storage]` in `~/.config/firecube/config.toml`, which may point at a remote production store. It then replays every run there, which can take minutes with no output on S3 (verified). Always pass `-n`, and run under a shell timeout.

Docs: https://eumetsat.github.io/firecube/latest/concepts/chunk-management/ and https://eumetsat.github.io/firecube/latest/reference/control-plane-spec/

## Safety Labels

| Label | Commands |
| --- | --- |
| Read-only | `chunks list`, `chunks runs list`, `chunks claims list`, `chunks snapshots status`, any command with `--dry-run` |
| Mutating | `chunks snapshots rebuild`, `catalog intake` |
| Mutating control-plane state | `chunks claims clear`, `chunks runs abandon` (records only; `--force` escalates) |
| Destructive | `chunks delete`, `chunks delete-span` (storage objects removed) |

For control-plane and destructive commands: run `--dry-run` first, show the output, confirm the exact product URI and scope with the user, then rerun with `--yes-i-really-mean-it`. Interactive shells prompt; non-TTY contexts require the flag.

## Inspect (Read-only)

```bash
firecube chunks list -n file:///<abs-path>/<product>.zarr
firecube chunks list -n file:///<abs-path>/<product>.zarr --include-span -f json
firecube chunks runs list -n file:///<abs-path>/<product>.zarr --status started
firecube chunks claims list -n file:///<abs-path>/<product>.zarr
firecube chunks snapshots status -n file:///<abs-path>/<product>.zarr -f json
```

`chunks list` filters: `--start-date` / `--end-date` (record creation, `YYYY-MM-DD`), `--time-range START:END` (ISO 8601, overlap semantics on span coverage), `--type chunk|meta`, `--pattern <glob>` (repeatable), `--meta key=value`, `--limit N`, `-f table|json|csv`. `--include-replaced` lists every recorded span, including spans already marked replaced and spans left by failed runs; the default projects only the current state from completed runs. Omitting `-n` does not scope to a safe local default: it falls back to `[storage]` in the user's config file (rule above), which may be a remote store; always pass `-n`.

`chunks runs list` requires `-n`; filter with `--status started|complete|failed|abandoned`. JSON rows include `stale` and `error`.

`chunks claims list` prints `No claims found.` when clean; otherwise the `Domain` column is the exact `--domain` value for `claims clear`.

`chunks snapshots status` reports `exists`, age, `completed_before`, `generation`, and `records`. A freshly ingested product has no snapshot until `snapshots rebuild` runs; `status` then says `No snapshot found` (verified). `firecube 0.1.7` has no `chunks snapshots list`; use `status`.

`chunks runs list` columns are `Run ID`, `Status` (`started`, `complete`, `failed`, `abandoned`), `State`, `Parts`, `Events`. A failed batch leaves a `failed` run in the history; it does not block later runs.

## Recover Runs And Claims (Mutating Control-Plane State)

Symptoms: ingestion refuses to start because a run is stuck in `started`, or a claim from a crashed writer blocks the write domain.

Confirm the original process is gone (scheduler, `ps`, `kubectl`) before any of these.

### `chunks runs abandon`

```bash
firecube chunks runs abandon -n file:///<abs-path>/<product>.zarr \
  --run-id <run-id> --reason "<why>" --dry-run
firecube chunks runs abandon -n file:///<abs-path>/<product>.zarr \
  --run-id <run-id> --reason "<why>" --yes-i-really-mean-it
```

`--reason` is required and recorded with the run. `--run-id` and `--all-stale` are mutually exclusive.

### `chunks claims clear`

```bash
firecube chunks claims clear -n file:///<abs-path>/<product>.zarr \
  --domain <product>:zarr_region:<group> --dry-run
firecube chunks claims clear -n file:///<abs-path>/<product>.zarr \
  --domain <product>:zarr_region:<group> --yes-i-really-mean-it
```

`--force` bypasses the staleness check for a single claim whose heartbeat still looks fresh. Use it only after proving the writer is dead; it is an operational bypass, not a confirmation flag.

Docs: https://eumetsat.github.io/firecube/latest/operations/chunk-manager/recover/

## Post-Crash Bulk Sweep (Mutating Control-Plane State)

After a cluster crash, pod eviction, or SIGKILL that left several runs and claims behind, use `--all-stale`. Bulk mode never prompts: without `--yes-i-really-mean-it` it only lists stale entries; with the flag it applies. Fresh heartbeats are never touched.

```bash
firecube chunks claims clear -n file:///<abs-path>/<product>.zarr --all-stale --dry-run
firecube chunks runs abandon -n file:///<abs-path>/<product>.zarr --all-stale --reason "cluster crash" --dry-run
```

If the preview lists fewer entries than `claims list` or `runs list --status started`, the missing ones are not yet stale: wait for the threshold or handle them individually with `--domain --force` / `--run-id`.

Docs: https://eumetsat.github.io/firecube/latest/operations/chunk-manager/post-crash-recovery/

## Crash Sequence

A kill signal during ingestion leaves one run with status `started`, and, for a serial append plugin, no claims or span records (claims appear only for parallel direct-Zarr writers). A retry exits 1 with `ResumeConflictError: Non-terminal run(s) [<run-id>] exist for product '<product>'. Abandon them first`. `chunks runs abandon -n <uri> --run-id <run-id> --reason "<why>" --yes-i-really-mean-it` prints `Abandoned run <run-id>`; `firecube ingest ... --option resume_existing=true` can then complete, and `zarr validate` confirms the result. `--option force_reingest=true` skips the non-terminal-run scan entirely instead of abandoning first (no warning is printed; the resume-guard log line shows `runs_enumerated=0`); offer it only when the operator has confirmed overwriting the stuck run's output is acceptable.

A `chunks claims clear` for a store whose filename differs from the product name it was ingested under no longer fails with a domain-mismatch error; the fix does not change the command's flags or safety class.

## Safe Recovery Order

1. Stop every writer for the product and verify none is running.
2. Inspect: `chunks runs list --status started`, `chunks claims list`, `chunks snapshots status`. If runs and claims are both empty, skip to step 7.
3. Preview the claim sweep: `chunks claims clear --all-stale --dry-run` (or `--domain <domain> --dry-run` per claim).
4. Preview the run sweep: `chunks runs abandon --all-stale --reason "<why>" --dry-run` (or `--run-id <run-id>`).
5. Confirm both previews with the user, then clear claims first, then abandon runs, each with `--yes-i-really-mean-it`. Clearing claims first avoids a window where an abandoned run still blocks the next ingest.
6. Re-check `runs list --status started` and `claims list`; both must be empty. If a new claim appeared, a writer restarted: stop it and repeat from step 3.
7. Rebuild the snapshot: `chunks snapshots rebuild -n <uri> --dry-run`, then without `--dry-run`.
8. Decide whether partial data must go: `chunks list --include-span` and, if so, follow the delete workflow below.
9. Resume ingestion with `firecube ingest ... --option resume_existing=true` (see ingestion.md), then verify with `chunks runs list` and `zarr validate` or `parquet validate`.

## Delete And Reingest (Destructive)

Preflight for storage deletion: the URI locates the product, but deleting storage objects also needs a storage type and driver:

```bash
export FIRECUBE_STORAGE_TYPE=local
export FIRECUBE_STORAGE_DRIVER=fsspec
```

Without them `chunks delete` fails with `Storage configuration not available`. `--manifest-only` does not need them. For S3 products also configure credentials (configuration-storage.md). Clear active claims first; an active claim blocks deletion.

### `chunks delete`

Removes tracked records and the underlying storage files. Irreversible.

```bash
firecube chunks delete -n file:///<abs-path>/<product>.zarr --dry-run
firecube chunks delete -n file:///<abs-path>/<product>.zarr --range 2024-03-01,2024-03-02 --dry-run
firecube chunks delete -n file:///<abs-path>/<product>.zarr --range 2024-03-01,2024-03-02 --yes-i-really-mean-it
```

| Flag | Notes |
| --- | --- |
| `-n` or `--all-products` | Mutually exclusive scope; `--all-products` needs explicit confirmation of every product |
| `--pattern`, `--type`, `--meta`, `--start-date`, `--end-date`, `--range A,B` | Filters on record keys and record time, not on data coverage; confirm coverage with `chunks list --include-span` first |
| `--time-range START:END` (ISO 8601) | Filters by data time (spans overlapping the window), distinct from `--range`'s record time |
| `--manifest-only` | Forget records, keep storage |
| `--storage-only` | Delete storage, keep records |
| `--include-metadata` | Also deletes `zarr.json` and similar; flagged DANGEROUS in help, avoid unless recreating the store |

### `chunks delete-span`

Deletes the storage chunks described by specific span records (a run or batch). Requires `-n`.

```bash
firecube chunks delete-span -n file:///<abs-path>/<product>.zarr --run-id <run-id> --dry-run
firecube chunks delete-span -n file:///<abs-path>/<product>.zarr --run-id <run-id> --yes-i-really-mean-it
```

Filters: `--run-id`, `--batch-id`, `-g, --group`, `--meta key=value`, `--include-replaced` (retry after a partial failure). `--force` allows deletion of spans that are not chunk-aligned, which expands the deleted area; only with explicit user approval. When force-deleting an unaligned span would also destroy chunks shared with other active spans, the command additionally requires `--yes-i-really-mean-it` to acknowledge the collateral destruction (without it, it errors listing the affected spans instead of deleting). `--time-dim <name>` is needed only for cubes with a custom time dimension whose span records predate dimension recording.

An unaligned span can be filled with NaN in place instead of removed (`write_strategy=region_nan_fill`) rather than deleting its chunk keys; the result reports `region_filled_spans`, `warnings`, and `collateral_spans` counts. Re-running against a span already filled this way is a no-op unless `--force` is passed again.

### Reingest

After deletion, rerun ingestion for the affected input with `--option force_reingest=true`, then `chunks snapshots rebuild`. Docs: https://eumetsat.github.io/firecube/latest/operations/chunk-manager/delete/

## Snapshots Rebuild (Mutating)

Rebuild the derived snapshot from the WAL when it is missing, stale, or after a sweep, large deletion, or reingest.

```bash
firecube chunks snapshots rebuild -n file:///<abs-path>/<product>.zarr --dry-run
firecube chunks snapshots rebuild -n file:///<abs-path>/<product>.zarr -f json
```

JSON output includes `generation`, `records`, `snapshot_path`, `locked`, `remote`. A failing rebuild means the WAL is corrupt or missing; do not hand-edit it, report at https://github.com/eumetsat/firecube/issues. Docs: https://eumetsat.github.io/firecube/latest/operations/chunk-manager/snapshots/

## Migration

`firecube 0.1.7` has no `chunks migrate` command (`firecube chunks --help` lists only `claims`, `delete`, `delete-span`, `list`, `runs`, `snapshots`). The concept pages mention "migrate a product" as an operation, but the only migration path in 0.1.7 is the resolved-index one for cubes written by `0.1.4.post1` or earlier: `zarr index verify --plugin <plugin-name>` then `zarr index rebuild` (see zarr-parquet-archive.md). Do not invent a migrate command.

## Intake Catalog (`catalog intake`, Mutating)

Generate an Intake YAML catalog that exposes each discovered dataset group as a source. Supported products: a URI ending in `.zarr` (all Zarr plugins) or `.parquet` (Parquet plugins); any other suffix is rejected with `Unsupported catalog product format`. Any installed plugin can be named; the plugin may optionally annotate or hide groups through a `catalog_group_info` hook, otherwise Firecube uses generic discovery.

```bash
firecube catalog intake <plugin-name> \
  -p file:///<abs-path>/<product>.zarr \
  -o file:///<abs-path>/<catalog>.yaml \
  --collection-id <collection-id> \
  --no-storage-options
```

| Flag | Notes |
| --- | --- |
| `PLUGIN` (positional) | Must be in `firecube plugins list`, else `Unknown plugin` |
| `-p, --product` | Full product URI; `--storage-type` / `--storage-driver` inferred from scheme |
| `-o, --output` | Must be `file://` in 0.1.7; `s3://` fails with `Remote artifact output not yet supported` |
| `--collection-id` | Required; stored in catalog metadata |
| `--include-storage-options` (default) / `--no-storage-options` | For `s3://` products the catalog carries `${FIRECUBE_ENDPOINT_URL}`, `${FIRECUBE_ACCESS_KEY}`, `${FIRECUBE_SECRET_KEY}` placeholders, never literal secrets; local products get no block, so `--no-storage-options` is the clean choice for local or public stores |
| `--storage-anonymous` | Public `s3://` bucket, no credentials; the generated `storage_options` block carries `anon: true` instead of the credential placeholders |

Zarr source entries in the generated catalog carry `chunks: {}` (not `auto`). Discovery read errors surface directly instead of a generic "no catalogable dataset groups found" message: an unreadable store fails the command, and an unreadable group is reported as a WARNING naming its URI while the rest of the catalog is still written. Output writes only the catalog file (JSON fallback with `.json` suffix if PyYAML is missing). Readers need `intake intake-xarray jinja2` for Zarr and additionally `intake-parquet` for Parquet. Verify:

```bash
python -c "import intake; c = intake.open_catalog('<catalog>.yaml'); print(list(c))"
```

Docs: https://eumetsat.github.io/firecube/latest/operations/intake-catalog/

## Notes And Discrepancies

- Docs pages use `uv run firecube ...`; plain `firecube` works once the environment is activated.
- `chunks delete --all-products` appears only in installed help; the documentation pages show per-product deletion only. Treat `--all-products` as a last resort and name every affected product before running it.
