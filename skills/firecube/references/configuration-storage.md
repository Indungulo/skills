# Configuration And Storage

Use this reference when choosing where a Firecube setting belongs (CLI flag, environment variable, or `config.toml`), writing product URIs, selecting a storage type or driver, or setting up S3 access safely.

Verified against installed `firecube 0.1.7` help and public docs. Official pages: [Configuration Model](https://eumetsat.github.io/firecube/latest/concepts/configuration/), [Configuration Reference](https://eumetsat.github.io/firecube/latest/reference/config/), [Product Storage](https://eumetsat.github.io/firecube/latest/concepts/storage/), [Storage Drivers](https://eumetsat.github.io/firecube/latest/reference/storage-drivers/), [Configure S3 Access](https://eumetsat.github.io/firecube/latest/operations/s3-access/).

## Configuration Surfaces

| Surface | Use it for | Example |
| --- | --- | --- |
| CLI flags | Run identity and storage choices for one command | `--target`, `--product-name`, `--storage-type`, `--storage-driver`, `--write-mode` |
| `--option key=value` | Engine, output-format, or plugin options for one run; a list-typed option takes a JSON array, quoted for the shell (`--option 'bands=["Oa09","Oa12"]'`), never `[Oa09,Oa12]` or `Oa09,Oa12`; a single bare token is accepted for `list[str]` only | `--option pipeline_workers=4` |
| Environment variables | S3 credentials, endpoint, region, deployment-wide storage defaults | `FIRECUBE_ENDPOINT_URL`, `FIRECUBE_STORAGE_DRIVER` |
| `config.toml` | Reusable settings kept between runs | `[storage]`, `[metrics]`, `[plugins.<plugin-name>]` |
| Plugin defaults | Product defaults declared by the installed plugin | `PRODUCT_NAME` on the plugin class |

Precedence for storage settings (highest first):

1. CLI flags
2. Environment variables
3. `config.toml`
4. Built-in defaults

Product name resolution order: `--product-name`, then `default_product_name` under `[plugins.<plugin-name>]`, then the plugin's `PRODUCT_NAME`, then fail. The docs note that `default_product_name` is currently rejected by option validation, so pass `--product-name` or rely on `PRODUCT_NAME`.

## Config File

| Item | Value |
| --- | --- |
| Default path | `~/.config/firecube/config.toml` |
| Override flag | `firecube --config-file <path> <command> ...` (root option; place it before the subcommand) |
| Override env var | `FIRECUBE_CONFIG=<path>` (source-verified in 0.1.7; not listed in the public docs) |
| Format | TOML; Python 3.12+ `tomllib` |
| Known top-level sections | `storage`, `database`, `plugins`, `archive`, `metrics` |

Strictness in `firecube 0.1.7`: only `firecube ingest` validates an explicit `--config-file` strictly (missing file, parse error, or unknown top-level section fails the run). Other commands and the default path treat a missing or unparseable file as an empty config, so a typo in the path is silent for `chunks`, `zarr`, `plugins`, and similar commands.

`${VAR}` placeholders inside string values are expanded from the environment, for example `endpoint_url = "${MY_S3_ENDPOINT}"`.

## Minimal config.toml Template

```toml
# ~/.config/firecube/config.toml  (keep private: mode 0600 if it holds credentials)

[storage]
# Optional S3 connection settings. Omit endpoint_url for standard AWS S3.
endpoint_url = "<endpoint-url>"
region = "<region>"
# Prefer environment variables for credentials; see "S3 Access" below.
# access_key = "${FIRECUBE_ACCESS_KEY}"
# secret_key = "${FIRECUBE_SECRET_KEY}"
path_style = true          # default true; set false for virtual-hosted-style buckets
driver = "fsspec"          # or "obstore" (requires firecube[obstore])
# type and target_path/bucket matter only for commands without a product URI (chunks/*):
# type = "local"
# target_path = "/<abs-path>/products"

[metrics]
# pushgateway_url = "https://<pushgateway-host>"

[plugins.<plugin-name>]
pipeline_workers = 4
pipeline_batch_size = 40
# zarr_chunk_shape = '{"time":1,"y":550,"x":475}'
```

Confirm the plugin section name with `firecube plugins describe <plugin-name>` and the accepted keys with `firecube ingest <plugin-name> --show-options`. Unknown keys fail validation; only `x_`-prefixed keys bypass it (experimental namespace).

## Environment Variables

| Variable | Maps to | Notes |
| --- | --- | --- |
| `FIRECUBE_ENDPOINT_URL` | `[storage].endpoint_url` | S3-compatible endpoint; omit for AWS |
| `FIRECUBE_REGION` | `[storage].region` | Only when the provider requires it |
| `FIRECUBE_ACCESS_KEY` | `[storage].access_key` | Must be set together with the secret |
| `FIRECUBE_SECRET_KEY` | `[storage].secret_key` | Must be set together with the key |
| `FIRECUBE_PATH_STYLE` | `[storage].path_style` | `1/true/yes/on` or anything else for false |
| `FIRECUBE_STORAGE_DRIVER` | `[storage].driver` | `fsspec` (default) or `obstore` |
| `FIRECUBE_STORAGE_TYPE` | `[storage].type` | Only for commands without a product URI (`chunks/*`) |
| `FIRECUBE_TARGET_PATH` / `FIRECUBE_BUCKET` | `[storage].target_path` / `[storage].bucket` | Product root for `chunks/*` when no `--product-name` URI is given |
| `FIRECUBE_CONFIG` | config file path | Alternative to `--config-file` |
| `FIRECUBE_LOG_LEVEL`, `FIRECUBE_LOG_FORMAT`, `FIRECUBE_DEBUG` | logging | See troubleshooting.md |

Firecube reads only `FIRECUBE_*` names. Generic `AWS_*` variables are not consulted by Firecube's config loader, although the underlying `fsspec`/`s3fs` stack may still pick up ambient AWS credentials (instance role, IRSA) when no explicit key pair is configured.

## Product And Target URI Rules

Product-locating options (`--target`, `--product`, `--source` on `archive create`, `--archive`, and `--product-name` on `chunks/*`) require a full URI in `firecube 0.1.7`.

| Input | Result (verified) |
| --- | --- |
| `file:///<abs-path>/<product>.zarr` | Accepted; storage type `local` |
| `s3://<bucket>/<prefix>/<product>.zarr` | Accepted; storage type `s3` |
| `/<abs-path>/<product>.zarr` (bare path) | Rejected: `URI scheme required (file:// or s3://). Did you mean file:///<abs-path>/<product>.zarr?` |
| `file://<host>/<path>` (two slashes plus host) | Rejected: `Use file:///path (three slashes, no host)` |
| `file:///` (empty path) | Rejected: `file:// URI requires a non-empty path` |
| `s3:///<prefix>` (no bucket) | Rejected: `authority bucket is required for s3 URIs` |
| Any other scheme (`ftp://`, `gs://`, `https://`) | Rejected: `URI scheme '<scheme>' not supported.` |
| Query string or fragment | Rejected |

Exceptions:

- `--input-data` on `ingest` is plugin input, not a product URI. It accepts a local path, `file:///...`, or an `s3://` prefix.
- `chunks list --product-name` does not validate a bare value; it is treated as a product-name filter and the command falls back to the `[storage]` configuration. Always pass the full product URI so the command binds directly to that product.

## Storage Type, Driver, And Write Mode

| Option | Values | Default in 0.1.7 | Meaning |
| --- | --- | --- | --- |
| `--storage-type` | `local`, `s3` | Inferred from the URI scheme | Storage locality. An explicit value that contradicts the scheme is rejected. |
| `--storage-driver` | `fsspec`, `obstore` | `fsspec` (env `FIRECUBE_STORAGE_DRIVER` or `[storage].driver` override) | Filesystem implementation for product data and the `.firecube/` control plane. |
| `--write-mode` (`ingest`) | `staged`, `direct` | None; required, no local inference | `direct` streams to the target; `staged` writes to a local workspace first, then uploads. |

Docs-vs-help note: `docs/concepts/configuration.md` presents `--storage-type` and `--storage-driver` as values to "always pass explicitly"; installed help for `ingest` states both are inferred or defaulted when omitted. Follow the help, but pass them explicitly in scripts to keep the backend unambiguous.

### Coherence Table

| URI scheme | `--storage-type` | `--storage-driver` | Notes |
| --- | --- | --- | --- |
| `file://` | `local` (inferred) | `fsspec` (default) | Simplest setup for development and inspection |
| `file://` | `local` | `obstore` | Needs `firecube[obstore]`; verify support for your workload first |
| `s3://` | `s3` (inferred) | `fsspec` (default) | Broad support including Parquet and DuckDB against S3 |
| `s3://` | `s3` | `obstore` | Optional Rust-backed path for supported Zarr workloads |
| `file://` | `s3` | any | Rejected: `--storage-type 's3' is incompatible with URI scheme 'file'` |
| `s3://` | `local` | any | Rejected with the mirrored message |

One driver applies to the whole run: product writes, control-plane records, and staged uploads never mix `fsspec` and `obstore`.

Install the optional driver with `uv pip install 'firecube[obstore]==0.1.7'`. Selecting `obstore` without it fails with `obstore is required for --storage-driver obstore. Install it with: uv pip install 'firecube[obstore]'` (in 0.1.7 this surfaces as a Python traceback, not a one-line CLI error).

### Staged Write Workspace

`--write-mode staged` uses a local workspace. Control it with plugin options such as `--option workspace=/<fast-local-disk>/firecube-work` and `--option cleanup_workspace=true`. Check the accepted keys with `--show-options`.

### Anonymous S3 Access

`--storage-anonymous` reads a public `s3://` bucket without configured or ambient credentials; it is a presence-only flag with no opt-out counterpart. Also settable as `FIRECUBE_S3_ANONYMOUS` or `[storage].anonymous` in `config.toml`; precedence is CLI flag, then env var, then config file, then the built-in default `false`. It applies only to `s3://` URIs and is silently irrelevant on `file://` targets.

Present on `ingest`, `archive create|restore`, `zarr validate|slots|multires|preallocate|consolidate-time-coord|compare`, `parquet validate|consolidate`, `advise batch-size|compliance`, and `catalog intake` (where it also makes the generated catalog carry `anon: true`; see chunks-catalog.md). Not present on any `chunks/*` command.

```bash
firecube zarr validate -p s3://<public-bucket>/<prefix>/<product>.zarr -g <group> --storage-anonymous
```

## S3 Access Setup

Set connection settings and credentials in the shell that runs Firecube:

```bash
export FIRECUBE_ENDPOINT_URL="<endpoint-url>"     # omit for standard AWS S3
export FIRECUBE_REGION="<region>"                 # only if the provider requires it
export FIRECUBE_ACCESS_KEY="<access-key>"
export FIRECUBE_SECRET_KEY="<secret-key>"
export FIRECUBE_STORAGE_DRIVER="fsspec"
```

Then run against an `s3://` target (mutating: writes the product to the bucket):

```bash
firecube ingest <plugin-name> \
  --input-data /<abs-path>/<source-dir> \
  --target s3://<bucket>/<prefix>/<product>.zarr \
  --product-name <product> \
  --storage-type s3 \
  --storage-driver fsspec \
  --output-format zarr \
  --write-mode staged
```

Verify read access without writing:

```bash
firecube chunks list --product-name s3://<bucket>/<prefix>/<product>.zarr
firecube zarr validate -p s3://<bucket>/<prefix>/<product>.zarr -g <group>
```

Credential safety rules:

- Prefer environment variables or a secrets manager over `config.toml`; if the file holds credentials, restrict permissions to the owner and keep it out of version control.
- Set `FIRECUBE_ACCESS_KEY` and `FIRECUBE_SECRET_KEY` together. Setting only one fails with `StorageConfig requires both --access-key and --secret-key when using explicit credentials` (the message names flags that do not exist on the CLI; use the env vars or `[storage]` keys).
- Leave both unset to use ambient AWS authentication (instance role, IRSA).
- Never paste credentials into prompts, tickets, or generated catalogs; `catalog intake` emits `${FIRECUBE_*}` placeholders instead of values for this reason.
- Do not print `env` output containing `FIRECUBE_SECRET_KEY` when sharing logs.

## Commands Without A Product URI

`firecube chunks list` (and other `chunks/*` commands) with no `--product-name` URI resolve a product root from `[storage]` or `FIRECUBE_STORAGE_TYPE` plus `FIRECUBE_TARGET_PATH` / `FIRECUBE_BUCKET`. When neither exists the command fails with `Chunk operations require a full product URI or a [storage] configuration in config.toml`. The command prints a `[chunks] storage: type=... base_uri=... (from config|env)` banner to stderr; silence it with `firecube chunks --quiet <command>`.

## Related References

- install.md for extras (`obstore`, `tensogram`) and environment setup.
- cli-surface.md for the full option list per command.
- ingestion.md for `--write-mode`, `--option`, and slot flags.
- chunks-catalog.md for `chunks/*` and `catalog intake` usage.
- troubleshooting.md for error text and fixes.
