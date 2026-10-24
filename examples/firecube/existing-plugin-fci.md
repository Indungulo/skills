# Existing Plugin Covers The Collection

## Prompt

```text
How do I create a Firecube plugin for FCI? Which template should I use?
```

## Expected Agent Behavior

- Check `firecube plugins list` and the known public plugins table in `plugin-development.md` before treating this as a scaffolding task.
- MTG FCI Level 1C (FDHSI `EO:EUM:DAT:0662`, HRFI `EO:EUM:DAT:0665`) is covered by `mtg_fci_l1c` at https://github.com/eumetsat/firecube-mtg-fci-l1c. Say so first and do not propose a new plugin for L1C unless the user wants their own.
- Clarify which FCI product the user means. FCI Level 2 products are not covered by that plugin; for those, apply the evidence rule (inspect a product, then recommend).
- For the existing plugin: `firecube plugins install git+https://github.com/eumetsat/firecube-mtg-fci-l1c.git` (no clone needed), `firecube plugins describe mtg_fci_l1c`, `firecube ingest mtg_fci_l1c --show-options`, then follow its README for geolocation grid generation and `zarr preallocate` before slot-range ingestion. Source data comes from `eumdac` downloads the user runs or authorises.
- Mark `plugins install`, geo grid generation, `zarr preallocate`, and `ingest` as mutating; confirm before each.

## Why This Matters

There is no plugin index web page yet; check `firecube plugins list` and the known public plugins table in `plugin-development.md` before treating an FCI request as a scaffolding task, so the existing plugin is named instead of missed.

## Safe Response Shape

```text
Workflow type: ingest with an existing plugin (mtg_fci_l1c), no scaffold needed for L1C
Prerequisites: firecube==0.1.7, the plugin installed from its git URL (no clone needed), FCI L1C chunk files for one repeat cycle, generated geolocation grids
Safety boundary: plugins install and geo generate mutate the environment and filesystem; preallocate and ingest write the target
Validation status: plugins list and --show-options to run after install; nothing run yet
```
