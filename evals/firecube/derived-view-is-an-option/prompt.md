---
name: derived-view-is-an-option
description: Derived views belong to the same plugin — a daily composite on a regular grid wanted beside a native swath cube is an opt-in plugin option (native default, own store), ported from the owner's routine, not a deferred separate product and not per-granule slices. Fixture: an existing swath plugin and a notebook routine described in prose, no product files.
tags: [firecube, cube-design, plugin-options, derived-views]
runs: 3
max_turns: 8
timeout_seconds: 300
---

I already have a working Firecube plugin for a polar-orbiter swath product (2-D lat/lon per pixel, one Zarr group per half-orbit, appended along track, no pixel value changed). Workshop participants now need to open the data in a cube viewer and subset it by bounding box and date, so I also need a daily composite on a regular lat/lon grid. The training team's notebook already has a composite_day(files, res, varname) routine for that. How should I provide it with Firecube?
