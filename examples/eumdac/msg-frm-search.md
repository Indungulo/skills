# MSG Fire Risk Map Search

## Prompt

```text
Search MSG FRM data.
```

## Expected Agent Behavior

- Verify EUMDAC version/help.
- Use `describe`, not `discover`, for `eumdac 3.1.1` collection discovery.
- Do not read, print, or overwrite existing credentials.
- Discover MSG-related collections with a wildcard filter.
- Identify the MSG Fire Risk Map collection.

## Collection

```text
EO:EUM:DAT:0398 - Fire Risk Map - Released Energy Based - MSG
```

Known filters from the observed collection description:

```text
Satellite: MSG
Product type: FRMv2
```

## Commands

```bash
eumdac --version
timeout 60 eumdac describe --filter '*MSG*'
timeout 60 eumdac describe --collection EO:EUM:DAT:0398
```

Search latest products by ingestion time:

```bash
timeout 120 eumdac search \
  --collection EO:EUM:DAT:0398 \
  --product-type FRMv2 \
  --satellite MSG \
  --sort ingestion \
  --desc \
  --limit 5
```

## Bbox Variant

Turkey bbox in EUMDAC order `W S E N`:

```bash
--bbox 26.0433512713 35.8215347357 44.7939896991 42.1414848903
```

```bash
timeout 120 eumdac search \
  --collection EO:EUM:DAT:0398 \
  --product-type FRMv2 \
  --satellite MSG \
  --bbox 26.0433512713 35.8215347357 44.7939896991 42.1414848903 \
  --limit 5
```

## Important Note

`--bbox` is an intersection filter. It selects products whose spatial extent overlaps the bbox. It does not crop regional products to the bbox.
