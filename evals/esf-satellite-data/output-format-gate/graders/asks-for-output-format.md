---
type: llm
criteria: "The response asks what output format the dataset should use, or presents source format as an explicit user choice, before choosing a transfer route. It does not silently pick Zarr, NetCDF, native source files, or a download path."
---

Mechanism: output format is an access-route gate; the skill must not choose streaming, conversion or download until the format is explicit.
