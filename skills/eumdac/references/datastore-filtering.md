# Data Store Filtering

Use this reference for `search` filters and the shared filtering options used by `download`, `subscribe add`, and `livefeed`.

## Search Basics

Search requires either an OpenSearch query or a collection ID:

```bash
eumdac search --collection "<collection-id>" --start "2024-01-01" --end "2024-01-02" --limit 5
```

Common filters from `eumdac 3.1.1`:

```text
--start / --end
--time-range <start> <end>
--publication-after / --publication-before
--daily-window <start-time> <end-time>
--bbox W S E N
--geometry "<WKT geometry>"
--cycle
--orbit
--relorbit
--filename
--timeliness {NT,NR,ST}
--product-type / --acronym
--satellite
--sort {ingestion,sensing}
--asc / --desc
--limit
```

Date/time values are UTC and use `YYYY-MM-DD[THH[:MM[:SS]]]`.

## Advanced Collection Filtering

Use a collection ID plus focused filters whenever possible:

```bash
eumdac search \
  --collection "<collection-id>" \
  --start "2024-01-01T00:00:00" \
  --end "2024-01-02T00:00:00" \
  --satellite "<satellite>" \
  --product-type "<product-type>" \
  --limit 10
```

### Time Filters

Use sensing time filters for the product observation/acquisition interval:

```bash
eumdac search --collection "<collection-id>" --start "2024-01-01" --end "2024-01-02"
eumdac search --collection "<collection-id>" --time-range "2024-01-01" "2024-01-02"
```

If only a date is provided, EUMDAC applies day-bound defaults. Use explicit times when the boundary matters.

Use publication filters for ingestion/publication time:

```bash
eumdac search --collection "<collection-id>" --publication-after "2024-01-01T12:00:00"
eumdac search --collection "<collection-id>" --publication-before "2024-01-02T12:00:00"
```

Use `--daily-window` to restrict results to a repeated daily time window:

```bash
eumdac search --collection "<collection-id>" --start "2024-01-01" --end "2024-01-31" --daily-window "10:00:00" "12:30:00"
```

### Product Identity Filters

Filter by filename/product identifier pattern:

```bash
eumdac search --collection "<collection-id>" --filename "*MSG*"
```

Filter by product type/acronym:

```bash
eumdac search --collection "<collection-id>" --product-type "<product-type>"
```

`--acronym` is an alias for `--product-type` in the validated CLI.

Filter by satellite:

```bash
eumdac search --collection "<collection-id>" --satellite "<satellite>"
```

Filter by timeliness:

```bash
eumdac search --collection "<collection-id>" --timeliness NT
```

Valid timeliness choices in `eumdac 3.1.1` are `NT`, `NR`, and `ST`.

### Orbit And Cycle Filters

For collections that expose orbit metadata:

```bash
eumdac search --collection "<collection-id>" --cycle 123
eumdac search --collection "<collection-id>" --orbit 45678
eumdac search --collection "<collection-id>" --relorbit 22
```

These values must be positive integers.

### Sorting And Limits

Sort by sensing or ingestion time:

```bash
eumdac search --collection "<collection-id>" --sort sensing --asc --limit 10
eumdac search --collection "<collection-id>" --sort ingestion --desc --limit 10
```

Always use `--limit` during exploratory searches and downloads.

In `eumdac 3.1.1`, `search` combining `--sort` with `--bbox`/`--geometry` and a wide `--time-range` pages through the whole result set before applying `--limit`, so it can take minutes to return or appear to hang; the same filters without `--sort` return in a few seconds. Prefer a narrow `--time-range` plus `--limit` and let the default order stand; add `--sort` only on small result sets, or once a spatial filter is dropped. Wrap every live search or download in a shell timeout so a hang cannot block the session:

```bash
timeout 120 eumdac search --collection "<collection-id>" --time-range <start> <end> --bbox W S E N --limit 5
```

## Filter By Area

Use `--bbox` or `--geometry` with `search`, `download`, `subscribe add`, and `livefeed`-style workflows. Coordinates are EPSG:4326 decimal degrees.

Bounding box syntax:

```bash
eumdac search --collection "<collection-id>" --bbox W S E N --limit 5
```

The order is:

```text
W S E N
west longitude, south latitude, east longitude, north latitude
```

Example for a small area:

```bash
eumdac search --collection "<collection-id>" --bbox -5.0 45.0 5.0 55.0 --limit 5
```

Use `--geometry` for custom EPSG:4326 WKT geometries:

```bash
eumdac search --collection "<collection-id>" --geometry "POLYGON ((10.09 56.09, 10.34 56.09, 10.34 56.19, 10.09 56.09))" --limit 5
```

Area filtering limits search/download candidates. It is not the same as cutting the output data to that area. For output subsetting/customisation, use Data Tailor or mission-specific `--download-coverage` where supported.

Pitfalls:

- Do not reverse latitude/longitude order. `--bbox` is `W S E N`, not `N W S E`.
- Quote WKT geometries so the shell does not split parentheses or commas incorrectly.
- Keep using a time filter and `--limit` for exploratory area searches.
- Confirm the collection supports the spatial filtering expected by the user; collection-specific behavior can vary.

## Validation

Credential-free validation:

```bash
eumdac search --help
```

Live search validation requires credentials, network access, and real collection IDs.
