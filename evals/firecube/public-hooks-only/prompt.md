---
name: public-hooks-only
description: Plugin code uses only the public Firecube surface — rerun skipping, store extension, run-end cleanup and a second append dimension are solved with core's resume contract and public hooks, not by overriding run(), returning an empty discovery, or calling underscore methods. Fixture: a daily GenericZarr plugin described in prose, no product files.
tags: [firecube, plugin-contract, resume, public-api]
runs: 3
max_turns: 8
timeout_seconds: 300
---

I maintain a Firecube GenericZarrIngestor plugin that writes one daily mean per day. I want three things: when I rerun it over the same dates it should skip the days that are already in the store instead of failing; I want to extend the store later with new days; and at the end of each run I need to close a process pool and delete a download cache. I was going to override run() to check the store first and return an empty list from discover_source_files when all days are present, and put the cleanup in _aggregate_metrics. The plugin also has a native swath output appended along a different dimension, which I switch by overriding _resolve_time_dim_name. Is that the right approach? What should the code look like?
