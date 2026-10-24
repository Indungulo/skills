# FCI HRFI Subscription

## Prompt

```text
Subscribe to FCI High resolution data.
```

## Expected Agent Behavior

- Inspect subscription help before proposing commands.
- Check whether subscriptions/downloaders already exist.
- Use a clear tag.
- Explain continuous download risk before starting a downloader.
- Do not print tokens or subscription credentials.

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

## Help And State Checks

```bash
eumdac subscribe --help
eumdac subscribe add --help
eumdac subscribe download --help
timeout 60 eumdac subscribe list
```

## Add Subscription

```bash
timeout 60 eumdac subscribe add \
  --collection EO:EUM:DAT:0665 \
  --product-type MTIFCI1CRRADHRFI \
  --satellite MTI1 \
  --tag FCI_HRFI_MTI1
```

Optional Turkey bbox:

```bash
--bbox 26.0433512713 35.8215347357 44.7939896991 42.1414848903
```

## Downloader Template

Run only after confirming output directory, disk capacity, filters, and stop criteria:

```bash
eumdac subscribe download \
  --tag FCI_HRFI_MTI1 \
  --output-dir ./data/fci-hrfi-subscription \
  --dirs \
  --only-incoming
```

## Important Behavior

- For FCI HRFI, the collection coverage is `FD` full disc.
- A bbox in the subscription query filters matching full-disc products; it does not crop delivered files.
- Do not start `subscribe download` for high-volume continuous data without explicit confirmation.
