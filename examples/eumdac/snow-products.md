# Snow-Related Product Discovery

## Prompt

```text
Get snow-related products from the EUMETSAT Data Store.
```

## Expected Agent Behavior

- Use wildcard discovery before choosing a collection.
- Describe candidate collections before giving search/download commands.
- Provide bbox and latest-product templates.

## Discovery Commands

```bash
timeout 60 eumdac describe --filter '*Snow*'
timeout 60 eumdac describe --filter '*snow*'
timeout 60 eumdac describe --filter '*SWE*'
timeout 60 eumdac describe --filter '*Cryo*'
```

## Candidate Collection From Observed Notes

```text
EO:EUM:DAT:1091 - FCI Snow detection (snow mask) by VIS/NIR radiometry - MTG
```

Observed collection filters:

```text
Satellite: MTI
Product type: SE-D-FCI
Supports bbox filtering: yes
```

## Describe And Search

```bash
timeout 60 eumdac describe --collection EO:EUM:DAT:1091
```

Latest products:

```bash
timeout 120 eumdac search \
  --collection EO:EUM:DAT:1091 \
  --sort ingestion \
  --desc \
  --limit 5
```

Bbox template:

```bash
timeout 120 eumdac search \
  --collection EO:EUM:DAT:1091 \
  --product-type SE-D-FCI \
  --satellite MTI \
  --bbox W S E N \
  --limit 5
```
