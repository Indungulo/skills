---
type: llm
criteria: "The response does not propose one time slice per granule on a global grid (it may explicitly reject it as extremely sparse). For the composite it states that every file of one time step (a day) must reach the plugin in one batch because the engine forms batches by file count, and it proposes making the bundle the item (discover_source_files returns one object per day or orbit) or direct-write slots, not forcing one batch per run; it also states that the composite output needs its own store because one run has one append dimension."
---

Mechanism: batch boundaries are the engine's, not the plugin's; a composite time step must not straddle them, and per-granule slices are not a composite. Pass only if the response makes the bundle the item (or uses slots) rather than forcing the batch size, separates the stores, and does not slice per granule.
