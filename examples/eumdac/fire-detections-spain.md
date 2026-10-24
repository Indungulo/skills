# Fire Detections In Spain

## Prompt

```text
I am interested the fire detections in ES: ("Spain", (-9.39288367353, 35.946850084, 3.03948408368, 43.7483377142))
```

## Expected Agent Behavior

- Do not assume MSG FRM is the right product.
- Explain that MSG FRM is fire risk / forecast data, not direct active-fire detection.
- Prefer Active Fire Monitoring collections for direct fire detections.
- Use Spain bbox in EUMDAC order `W S E N`.

## Spain Bbox

```bash
--bbox -9.39288367353 35.946850084 3.03948408368 43.7483377142
```

## Candidate Collections

Observed example IDs and titles, not current results. Re-check with `eumdac describe` before use:

```text
EO:EUM:DAT:0801 - Active Fire Monitoring (CAP) - MTG - 0 degree
EO:EUM:DAT:0682 - Active Fire Monitoring (netCDF) - MTG - 0 degree
EO:EUM:DAT:0417 - SLSTR Level 2 Fire Radiative Power - Sentinel-3
EO:EUM:DAT:0398 - Fire Risk Map - Released Energy Based - MSG
```

## MTG Active Fire Monitoring netCDF

```bash
timeout 120 eumdac search \
  --collection EO:EUM:DAT:0682 \
  --product-type MTIFCI2FIR \
  --bbox -9.39288367353 35.946850084 3.03948408368 43.7483377142 \
  --limit 5
```

## MTG Active Fire Monitoring CAP

```bash
timeout 120 eumdac search \
  --collection EO:EUM:DAT:0801 \
  --product-type MTIFCI2FIRC \
  --bbox -9.39288367353 35.946850084 3.03948408368 43.7483377142 \
  --limit 5
```

## Sentinel-3 Fire Radiative Power

```bash
timeout 120 eumdac search \
  --collection EO:EUM:DAT:0417 \
  --product-type SL_2_FRP___ \
  --bbox -9.39288367353 35.946850084 3.03948408368 43.7483377142 \
  --limit 5
```

## Recommendation Pattern

For direct fire detections, prefer MTG Active Fire Monitoring. Use Sentinel-3 FRP when fire radiative power or hotspot characterisation is needed. Use MSG FRM when the request is about fire risk forecasts rather than detections.
