# Tool reference

Fifteen tools, all read-only. Every output carries `warnings`; read it.

## Feature database

### `list_feature_types`
Start here. Reads cached counters, so it is effectively free.

```json
{"minFeatureCount": 1000, "nameContains": "cyclone", "includeAll": false}
```

Returns id, name, description, tags, feature count and observation extent. The default floor hides test artifacts; the warning says how many were hidden.

### `list_reference_data`
`kind` is one of `satellites`, `usage_rights`, `labellers`, `tags`.

### `describe_feature_type`
The most important tool. Profiles a bounded sample.

```json
{"featureType": "<name from list_feature_types>", "timeStart": "2005-01-01T00:00:00Z", "timeEnd": "2006-01-01T00:00:00Z", "sampleSize": 1000}
```

Cost: a fraction of a second for 1000 rows, regardless of the type's size, because of the sample limit. Raising `sampleSize` above 5000 is clamped.

Without a window it profiles the last 30 days of available data and says so. Property availability changes over time, so profile the period you care about.

**Pitfall:** `hints.identityKeyCandidates` and `hints.perObservationIds` are the difference between counting events and counting observations. Check both, for every type: they are discovered per type, not fixed.

### `query_features`
A page of individual features. Not for counting.

```json
{"featureType": "<name from list_feature_types>", "timeStart": "...", "timeEnd": "...", "limit": 50,
 "fields": ["<identity property>", "<name property>", "<region property>"],
 "properties": "[{\"key\":\"<region property>\",\"op\":\"eq\",\"value\":\"<value from the profile>\"}]"}
```

Property filter operators: `eq`, `ne`, `in`, `lt`, `lte`, `gt`, `gte`, `exists`, `missing`. At most 20 filters, 100 values in an `in`.

**Pitfall:** always pass `fields`. Without it, properties over 8 kB are dropped entirely, and a densely profiled type can carry dozens of them.

**Pitfall:** property filters run against an unindexed column, so they narrow the result but not the scan. Keep the window tight regardless.

### `get_features`
By id, at most 1000.

### `aggregate_features`
Counts events and observations per class, deduplicated.

```json
{"featureType": "<name from list_feature_types>", "timeStart": "...", "timeEnd": "...",
 "identityKey": "<from describe_feature_type's identityKeyCandidates>",
 "classes": {"property": "<categorical property from the profile>", "categorical": true,
             "values": [{"label": "severe", "values": ["<value>", "<value>"]}]}}
```

For numeric classes use `bins` with `min` and `max`, half-open `[min, max)` so adjacent bins tile without double counting.

`identityAgg` picks how an event's many observations reduce to one value: `max` (default), `min`, `first`, `last`.

Cost scales with rows scanned, not with time span: a sparse type takes years in one call, a dense one is refused for a single year. Size the window by the row count `describe_feature_type` and the budget check imply, not by the calendar.

**Pitfall:** omitting `identityKey` counts every observation as an event. The tool warns, but the number still looks plausible.

**Pitfall:** read the `unclassified` class. A large share means the property name or the bounds are wrong.

### `select_balanced_events`
A deduplicated, reproducible sample. **`classes` is optional and omitting it is the default**: without
it every event lands in one class and `perClass` is simply how many events to return, which needs no
profiling, classification or aggregate first. Supply `classes` only when the user asked for a class
split or a balanced set.

```json
{"...same as aggregate...", "perClass": 20, "seed": "run-1",
 "referenceTime": "peak", "preMinutes": 180, "postMinutes": 180}
```

`referenceTime` is `peak` (the observation carrying the event's aggregate value), `first`, `last` or `middle`.

**Record the seed.** The same seed over the same data returns the same events; it is what makes a dataset reproducible. Without one a fixed default is used and the response says so.

**`perClass` is per class when classes are given, and the plain total when they are not.** If the user
asked for a balanced split, use the same value for every class; to hit a target total, divide it by the
number of classes rather than passing the total.

Read `classes[].shortfall` and `available`.

## Satellite discovery

### `list_satellite_collections`
Federated across the EUMETSAT Data Store, AWS Open Data and the embedded catalogue. A truncated page is taken evenly across sources, so narrow with `keyword`, `platform`, `instrument` or `source` rather than raising the limit.

`extentKnown: false` means the source publishes no extent, so the collection matches every time filter. Treat it as "might cover this", not "does".

### `get_satellite_collection`
For EUMETSAT collections this fetches the description document, which is the only place the real temporal extent, platform list and product types are published.

### `search_satellite_products`
Individual acquisitions with real sizes and download links. **At most 99 days per call**; split longer requests. Only the EUMETSAT Data Store has a product inventory; the bucket collections return their key layout instead.

### `check_event_coverage`
One upstream search per event, at most 200. Run it before promising a dataset.

**Pitfall:** a match means the product's footprint contains the event, not that the imagery is usable there. A geostationary full disc nominally covers everything it can see, so events near the limb match but are heavily foreshortened.

### `recommend_collections`
Ranked candidates with reasoning, caveats and coverage gaps. `preference` is `climate_record`, `operational`, `highest_resolution` or `cheapest`.

The ranking already encodes the global-view rule: GeoRing outranks coarse global composites such as GridSat, and under `highest_resolution` native discs (MTG FCI, GOES) outrank GeoRing. Pass `highest_resolution` whenever the study needs pixel-scale detail or rapid cadence, otherwise the merged ring wins by design.

Those preferences are configuration on the server, not compiled-in rules. The server holds **no list of feature types at all**: what ties a type to imagery is the tags on its own database record. Two things follow:

- If the response notes that the feature type carries no tags, the ranking saw only coverage and access. Say so, and filter `list_satellite_collections` yourself by the instrument the type was detected from.
- The `notes` describe each instrument behind the ranked collections once - orbit, position, cadence, resolution - and the `caveats` flag anything pre-operational or planned. Report those rather than assuming fixed behaviour.

### `estimate_download_volume`
Files and bytes per collection. Takes either `events` from `select_balanced_events`, or `eventCount` plus `windowMinutes`.

Read the `assumptions`. Where a collection publishes no typical size the tool measures one real product and says so, but cadence and coverage may still be assumed.

`accessMode` and `accessNote` say whether those bytes have to move. For an open bucket the mode comes back `unknown` with a pointer to the two tools below: a large total here is a size, not an instruction to start copying.

### `get_throughput_probe`
Returns commands to measure read speed, one recipe per bucket-backed collection. **The server never runs them.** These buckets are reachable only from certain networks and speed belongs to the reading host, so a figure measured on the server would describe the wrong machine.

Three steps come back: list the bucket to find a real object, time one read, time several at once. Ask the user to run them on the machine that will read the data and report the **aggregate** figure from the last step.

**Pitfall:** reporting the single-read number. It measures round-trip latency as much as bandwidth on a small object, and understates a parallel workload badly enough to send a fast bucket down the download path.

A collection with no open bucket comes back as a warning rather than a probe; there is nothing to time.

### `plan_data_access`
Decides, per collection, whether to read in place or copy, and returns the artefact for whichever it is.

```json
{"collections": ["<id>"], "events": [...], "outputFormat": "source",
 "throughput": [{"collection": "<id>", "megabytesPerSecond": 420, "measuredFrom": "EWC VM"}]}
```

**`outputFormat` is the first gate, and you have to ask the user for it.** Data wanted in the format
it is already stored in can be read where it lies; anything else means every file is read and
rewritten, which is a download however fast the bucket. `source` keeps whatever the data is in.
Aliases are understood (`nc4` against a NetCDF collection is not a conversion), from a table the server
maintains. What the tool decides is whether bytes have to move, not whether the
conversion can happen here at all - that is rule 13, and for anything but a Zarr input the answer is
usually that it cannot.

**Pitfall:** filling `outputFormat` in from the collection id to make the call succeed. The field is
optional in the schema precisely so that omitting it returns "ask the user" rather than a validation
error; inventing a value turns a question for the user into a silent decision. A collection that does
not record its stored format gets a caveat instead of a verdict, so check that too.

- `stream` — `catalog` is a STAC Catalog pointing into the buckets. That **is** the dataset; save it and write no download script.
- `download` — go to the download template, quoting the numbers it decided on.
- `unknown` — something is missing. `needs` and `nextStep` say which: `outputFormat` means go and ask
  the user, `measuredThroughput` means run the `probes` that come back with it. The format is asked
  for first, since its answer can make the measurement irrelevant.

Items are one per event window, not one per file. `esf:prefixResolved: false` on an item's asset means the href is a key prefix rather than a file and needs listing; the documented layouts elide filenames, so the tool marks what is owed instead of generating dead links.

A collection with `esf:storeFormat` comes back `stream` when its own format is what was asked for — a chunked array store has no per-timestep objects to download. In another format it is a conversion you write by slicing the store, not a download script.

Thresholds live in server configuration, not in code. `preferDownload` forces copies when the user asked for files on disk.

See [streaming-and-stac.md](streaming-and-stac.md).

## Resources

`esf://docs/workflow`, `esf://docs/collection-heuristics` and `esf://catalogue/static` carry the server's own guidance. Worth reading once at the start of a complex task.
