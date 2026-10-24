# FCI HRFI Turkey Download

## Prompt

```text
Download 2 days of FCI high resolution data starting from 20.04.2026. Need only Turkey, but if that does not exist, a bigger bbox is acceptable.
```

## Expected Agent Behavior

- Interpret dates explicitly.
- Discover/describe the FCI HRFI collection.
- Explain bbox filtering vs output cropping.
- Estimate product count/size before download when possible.
- Do not run the full download without explicit storage/quota confirmation.

## Collection

```text
EO:EUM:DAT:0665 - FCI Level 1c High Resolution Image Data - MTG - 0 degree
```

Known filters from the observed collection description:

```text
Satellite: MTI1
Product type: MTIFCI1CRRADHRFI
Coverage: FD
```

## Date Interpretation

```text
Start: 2026-04-20T00:00:00 UTC
End:   2026-04-22T00:00:00 UTC
```

## Turkey Bbox

EUMDAC order is `W S E N`:

```bash
--bbox 26.0433512713 35.8215347357 44.7939896991 42.1414848903
```

## Search Before Download

```bash
timeout 120 eumdac search \
  --collection EO:EUM:DAT:0665 \
  --product-type MTIFCI1CRRADHRFI \
  --satellite MTI1 \
  --bbox 26.0433512713 35.8215347357 44.7939896991 42.1414848903 \
  --start 2026-04-20T00:00:00 \
  --end 2026-04-22T00:00:00 \
  --limit 5
```

## Count Before Bulk Download

Keep the same narrow time window and drop `--sort`; a bbox search combined with `--sort` is the documented hang case (see [datastore-filtering.md](../../skills/eumdac/references/datastore-filtering.md)):

```bash
timeout 120 eumdac search \
  --collection EO:EUM:DAT:0665 \
  --product-type MTIFCI1CRRADHRFI \
  --satellite MTI1 \
  --bbox 26.0433512713 35.8215347357 44.7939896991 42.1414848903 \
  --start 2026-04-20T00:00:00 \
  --end 2026-04-22T00:00:00 \
  --limit 1000 | wc -l
```

## Important Behavior

- Bbox selects products whose full-disc footprint overlaps Turkey.
- It does not crop FCI HRFI files to Turkey.
- If only `FD` coverage is available, the practical fallback from "Turkey only" is full-disc HRFI products.
- A two-day HRFI selection can be very large. In the observed test, `288` products at about `579199 KB` each was roughly `160 GiB` before filesystem overhead.

## Bulk Download Template

Run only after explicit confirmation. Size the `timeout` to the expected transfer time for a ~160 GiB download, not to the short timeouts used for a single-product check:

```bash
timeout 21600 eumdac download \
  --collection EO:EUM:DAT:0665 \
  --product-type MTIFCI1CRRADHRFI \
  --satellite MTI1 \
  --bbox 26.0433512713 35.8215347357 44.7939896991 42.1414848903 \
  --start 2026-04-20T00:00:00 \
  --end 2026-04-22T00:00:00 \
  --output-dir ./data/fci-hrfi-turkey-20260420-20260422 \
  --dirs \
  --integrity
```
