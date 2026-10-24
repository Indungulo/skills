# Search Hangs With Sort And Bounding Box

## Prompt

```text
Find one granule of <collection-id> over <region> from yesterday and download it.
```

## Expected Agent Behavior

- Route to `datastore-filtering.md` and `datastore-download.md`.
- Use a narrow `--time-range` and `--bbox` with `--limit`; do not add `--sort` to a spatially filtered search.
- Run the live search and download under a shell timeout and report the elapsed time if it is unusual.
- If the search produces no output for a minute or more, kill it, drop `--sort`, and retry with a narrower window instead of waiting.
- Download only the selected product with `--product`, `--yes`, and an explicit `--output-dir`, and say where the file landed.

## Observed Behavior This Example Records

With `eumdac 3.1.1` on 2026-09-04, `search -c <collection-id> --time-range <3h window> --bbox W S E N --sort sensing --desc --limit 1` produced no output for more than six minutes and was killed. The same search without `--sort` returned three products in under two seconds, and a plain `--time-range` search returned in under three seconds. A follow-up `download --product <id> --onedir --yes` completed in about two seconds for a 0.6 MB product.

## Safe Command Pattern

```bash
timeout 120 eumdac search -c <collection-id> --time-range <start> <end> --bbox W S E N --limit 3
timeout 300 eumdac download --yes -c <collection-id> -o <output-dir> --onedir -p <product-id>
```
