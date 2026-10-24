# Data Store Download

Use this reference for `download` workflows, product package entries, integrity checks, coverage downloads, Data Tailor-on-download, and output layout.

## Basic Download

Download by search criteria:

```bash
eumdac download --collection "<collection-id>" --start "2024-01-01" --end "2024-01-02" --limit 1 --output-dir ./data
```

Download with an area filter:

```bash
eumdac download --collection "<collection-id>" --bbox -5.0 45.0 5.0 55.0 --start "2024-01-01" --end "2024-01-02" --limit 1 --output-dir ./data
```

Download explicit product IDs:

```bash
eumdac download --collection "<collection-id>" --product "<product-id>" --output-dir ./data
```

`<product-id>` is the exact string `eumdac search` prints, suffix included; a product ID is an opaque identifier, not a filename to normalise. A `Not found (404)` on a product that search just listed means the ID was altered, not that the product is gone.

Useful download options:

```text
--integrity                  verify md5 when available
--entry "<pattern>"          filter product files by shell-style wildcard
--download-coverage <code>   mission-specific coverage subset
--tailor / --chain <chain>   customize via chain ID, file, or YAML string
--local-tailor <id>          use configured local Data Tailor instance
--onedir / --dirs            choose output directory layout
--threads <n>                parallel connections
--no-progress-bars           quieter automation output
--yes / -y                   auto-confirm the download prompt
```

Prefer `--limit` for exploratory downloads. Confirm storage/quota expectations before suggesting broad downloads.

Pass `--yes`/`-y` only after the user has authorised that specific download: product count, total size, and destination stated and agreed. It skips the CLI's own confirmation prompt, so it does not replace stating those numbers and getting authorisation first; use it to keep an already-authorised download from stalling on an interactive prompt under `timeout`.

## Advanced Downloading

Download only selected files inside product packages using shell-style entry patterns:

```bash
eumdac download --collection "<collection-id>" --product "<product-id>" --entry "*.nat" --output-dir ./data
```

Verify integrity when MD5 is available:

```bash
eumdac download --collection "<collection-id>" --product "<product-id>" --integrity --output-dir ./data
```

Choose output layout:

```bash
eumdac download --collection "<collection-id>" --product "<product-id>" --onedir --output-dir ./data
eumdac download --collection "<collection-id>" --product "<product-id>" --dirs --output-dir ./data
```

Use parallel connections carefully:

```bash
eumdac download --collection "<collection-id>" --start "2024-01-01" --end "2024-01-02" --limit 10 --threads 4
```

Use mission-specific coverage downloads only where supported:

```bash
eumdac download --collection "<collection-id>" --product "<product-id>" --download-coverage FD
```

Supported coverage values in `eumdac 3.1.1` are:

```text
FD H1 H2 T1 T2 T3 Q1 Q2 Q3 Q4
```

Use Data Tailor customisation during download with a chain ID, file, or YAML string:

```bash
eumdac download --collection "<collection-id>" --product "<product-id>" --chain "<chain-id-or-file>" --output-dir ./tailored
```

Use a configured local Data Tailor instance:

```bash
eumdac download --collection "<collection-id>" --product "<product-id>" --chain "<chain-id-or-file>" --local-tailor "<local-tailor-id>"
```

`--bbox`/`--geometry` filter which products are selected. `--download-coverage` and Data Tailor affect downloaded/customised output where supported.

## Validation

Credential-free validation:

```bash
eumdac download --help
```

Live download validation requires credentials, network access, storage space, and real collection/product IDs.

## Size And Space Before Downloading

The gate (count, total size, free space, destination, single authorisation, `timeout`) and the size command live in [SKILL.md](../SKILL.md) rule 8. Any skill that hands off a download to EUMDAC, including a calling skill such as `firecube`, follows it; the first three checks are read-only, so run them directly, then ask once.

Notes beyond the SKILL.md command:

- Mirror any other CLI filter through `collection.search(...)` keyword arguments (inspect `collection.search_options`) or `datastore.opensearch(...)`; see [python-api.md](python-api.md).
- The catalogue size does not always match the delivered archive. For a decision near a limit, download one authorised product, measure it on disk, and multiply by the count.
- Never reuse a destination path from a project or another tool; use the one the user names.
- After the download, report the destination directory. If another skill or workflow requested the download, report that directory back to it so the calling workflow can continue.
