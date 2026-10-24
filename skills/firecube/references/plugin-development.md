# Firecube Plugin Development

Use this reference when a user wants to build, test, install, or package a Firecube plugin for their own dataset: choosing a template, scaffolding with `firecube plugins create`, implementing the hooks, adding typed options, and running a first local ingestion.

Verified against `firecube 0.1.7` (installed CLI help and scaffold output). Guide root: https://eumetsat.github.io/firecube/latest/guides/plugins/ ; API reference root: https://eumetsat.github.io/firecube/latest/reference/. For running an installed plugin see ingestion.md; for the command tree and safety classes see cli-surface.md.

Placeholders: `<plugin-name>` is the name given to `plugins create` (dashes allowed, e.g. `my-plugin`); `<plugin_name>` is the registered ID derived from it (`my_plugin`) used by `plugins describe`, `ingest`, and the entry point; `<workdir>` is the project's parent directory; `<input-dir>` holds user-supplied sample files. Never invent source data; the developer supplies it.

## Known Public Plugins

There is no plugin index web page yet; this table is the list. Check it, and `firecube plugins list` for what is already installed, before scaffolding a new plugin. Both repositories are public on GitHub; neither is on PyPI. `firecube plugins install` accepts a git URL directly, so no clone is needed unless you want the repository's scripts or tests.

| Plugin ID | Repository | Covers | Template | Install |
| --- | --- | --- | --- | --- |
| `mtg_fci_l1c` | https://github.com/eumetsat/firecube-mtg-fci-l1c | MTG FCI Level 1C: FDHSI `EO:EUM:DAT:0662`, HRFI `EO:EUM:DAT:0665` | `DirectZarrIngestor`, slot-based 10-minute time axis (144 slots/day), Zarr groups `data_500m`, `data_1km`, `data_2km` | `firecube plugins install git+https://github.com/eumetsat/firecube-mtg-fci-l1c.git` |
| `quickstart_plugin` | https://github.com/eumetsat/firecube-quickstart-plugin | Example only: small time-indexed NetCDF files from its own generator script | `GenericZarrIngestor` | `firecube plugins install git+https://github.com/eumetsat/firecube-quickstart-plugin.git`; clone it instead only to run its sample-data generator script |

`mtg_fci_l1c` specifics from its README (verify against the repo before quoting): requires Firecube 0.1.4 or newer; key options `channels`, `product_type` (FDHSI or HRFI), `time_epoch`, `time_slots`, `fci_grids_file`; source data is the NetCDF chunk files downloaded with `eumdac`; geolocation grids must be generated first with `firecube plugins mtg_fci_l1c geo generate`, and the store preallocated with `firecube zarr preallocate` before parallel slot-range ingestion. Apache-2.0.

When a known plugin covers the user's collection, route to ingestion.md and the plugin's README instead of scaffolding. Scaffold a new plugin only for a collection no known plugin covers, or when the user explicitly wants their own.

## Plugin Design Procedure

Follow these steps in order. Each "ask" uses the structured question tool when one exists. Each "stop" means: do nothing further until the operator answers.

1. **Existing plugin?** Run `firecube plugins list` and check the known public plugins table above. If a plugin covers the collection, route to ingestion.md and its README; stop designing.
2. **Goals.** Ask what the operator will do with the product, which variables matter, and whether the feed is bounded or continuous. When the operator has already stated a design or its rationale in their own words, at any point, copy it verbatim into the plan's Operator answers and treat it as their answer to the goal and time-unit questions: confirm it in one structured question, do not re-ask it. It does not replace the evidence steps; the files still decide whether the stated design fits, and a mismatch goes back to the operator as a finding. Uses and variables are sets: ask them multi-select. The variables question always offers carrying every variable; that is the lossless default, and a subset is the choice that needs a reason from the operator. Do not ask them to name a format.
3. **Data.** Ask what they already know about the product (variant, meaning of axes and categories, cadence, known gaps), fetch the collection metadata from the public catalogue, then ask whether they have sample products on disk and where (products noticed inside a directory the operator named are offered as an option here, not inspected before they choose). If not, design the sample set from the collection metadata before asking. As soon as files are named, check whether the format on disk matches what built-in discovery and the planned reader can open: the default suffix set and content-sniffing rules are under Source Discovery below, and the archive and paired-file cases have their own guides linked there. When it does not match (the files are a format neither discovery nor any reasonable reader opens, such as a provider-specific binary the operator wants converted first), stop and ask for a conversion the operator owns or a converted sample; do not write a decoder for the format found on disk, and do not invent the fields a conversion would produce. The moment any source (the collection metadata, a search listing, a file) shows an identity field with more than one value (platform, orbit direction, processing baseline, surface type where the retrieval differs, or an identity/provenance attribute that changes across a series such as a reprocessing stream or version bump while the data variables stay the same), stop and ask the operator with the question tool whether the plugin covers all of them or which subset; the answer fixes the sample set, the group key, and the feasibility numbers. If the operator does not answer, keep each in-scope value in its own group; never merge them into one time series silently. The sample set is one consecutive pair (adjacency and continuity) plus one product for each in-scope value of each such field. Consecutive products from one platform repeat the evidence the first pair gave. An in-scope value with no sample blocks the design: this skill never downloads; hand off to the `eumdac` skill, naming the products by variant needed, and stop until the operator names the directory holding the files. It is not carried into the build as an open item. When a search listing shows one value of an identity field, group the listing by that field or widen the window before concluding the collection has only that value. Only if no product can be obtained, fall back to the product format specification, targeted as described under Evidence Required First.
4. **Inspect.** Run the read-only dump on two products. Record dimensions, coordinates, the complete variable list, fill values, valid fraction, whether the shape is constant, and the global attributes (product identity, orbit or cycle counters, start and end times, processing baseline, platform). For any time-like variable record its dimensionality, whether it holds one value per scan line, and whether it is monotonic. Compare the counters in the filename with those in the attributes before using either as a grouping key; they need not be the same quantity. Then list what the files did not answer (index labels, cadence over a day, variants, flag meanings, coverage over time) and resolve each with the operator, the metadata, or a targeted page of the specification when the operator points to it. When a gap goes to the operator, make it concrete: name the variable, show what the file has (for example "a dimension of length 6 with no names"), say what it becomes in the cube (an axis label), and what each answer costs. Never assume the operator knows the product internals; offer "I do not know, check the manual" as an explicit option, and treat that answer as authorisation for a targeted read. Write everything into the plan file (step 9), not into the skill.
5. **Cube design.** Fix the time unit from the acquisition geometry, separate coverage sparsity from retrieval sparsity, and decide how files combine without changing values. Then name the append dimension and its ordering coordinate: it must be 1-D, monotonic, and unable to overlap across batches, and this must be checked on the inspected files (a per-pixel or per-file time variable is not an ordering key until checked; derive one from the file's start and end times if it fails). Decide how a time unit is completed when its files arrive across batches or runs: a unit written once along a length-1 axis can never grow. Decide what one source item is (see Source Discovery): when the unit you combine is the item, it cannot straddle a batch. The group key covers every axis on which the collection varies (platform, instrument, processing baseline), taken from the collection metadata and not only from the sampled files: two files from one platform cannot reveal a collision with another. One ingestor has one append dimension for all of its groups; a secondary product whose natural axis differs (a regular grid derived from a swath) is a separate product or a post-processing step, not a sibling group. The ordering coordinate is promoted to a coordinate of the dataset (`set_coords`); the writer checks order and overlap across batches only through a coordinate on the append dimension. When the time unit is coarser than the acquisition unit (a day of orbit segments), every identity field that varies inside a group (orbit number, direction, baseline) becomes a coordinate along the append dimension; an attribute may hold only what is constant for the whole group. Group attributes are written once: on append Firecube keeps the first-write values, so a whole-group value that changes as data arrives (end, extent, count, the list of source products) is a coordinate or data variable along the append dimension, never an attribute and never recomputed from every product for every batch. Fix the time chunk length and the time encoding epoch as store constants, not from the run window ([plugin-traps.md](plugin-traps.md), Zarr Layout Rules).
6. **Feasibility.** From one measured product estimate: size per product as written by a scratch run (not the source file: decoding packed integers to floats and a different compressor change the size by a factor), products per time unit and per day, cube size for the horizon, and ingest time per product (a scratch run on one product is cheap). State the numbers. The template comes from the design in step 5; feasibility decides horizon, parallelism, and whether the simpler append template is acceptable because the whole run finishes in acceptable time anyway. "Test cube" or "one-off" is not a reason to change the template; it is a reason to shorten the horizon and the product count.
7. **Recommend.** One template with the reasons it fits the data and the goal, the reasons the alternative fits less, and what answer would flip it. Ask with the question tool; the operator decides.
8. **Summary and metadata.** Put the design summary inside a question and get it confirmed. Then ask for plugin name, author, email, licence, and target directory. Never invent them.
9. **Plan file.** Write `firecube-plan-<plugin-name>.md` at a path the operator names (the target directory is a good default) with sections: Operator answers, Evidence, Design, Feasibility, Steps and dependencies, Open items, Next step, Log. Steps and dependencies lists every build step with what it depends on; once the scaffold exists, the ingestor implementation, behaviour tests on the sample files, README and option documentation, and obtaining further authorised samples are independent of each other, while install, first ingestion, and validation depend on all of them. Update the file at every later decision. A future agent, or this one after context compaction, resumes from that file, not from the transcript. Then stop and ask with the question tool whether to execute the plan now, pause here and resume later from the file, or change something. Offer parallel execution only when the current tooling supports delegated agents and the user has authorised parallel agent work. The plan is a deliverable in its own right; the operator may want to review it, share it, or come back tomorrow.
10. **Build.** Only after the operator chose to execute. Scaffold first, serially. Then run the steps the plan marks independent either in sequence or through authorised parallel delegation. Then install, first run, and validation, serially, by the main agent. Each step gets one progress line before and one result line after.

### Progress Lines

Before any step expected to take more than about twenty seconds (extraction, inspection of large files, install, preallocate, ingest, tests), print one line naming the step and the expected duration. After it, print one line with the outcome. Never chain two long steps silently. Nothing else in between; the balance is one line each way, not narration.

## Lifecycle

| Step | Command or action | Mutates |
| --- | --- | --- |
| 1. Choose a template | Decision table below | no |
| 2. Create | `firecube plugins create <plugin-name> --template ... --non-interactive` | filesystem |
| 3. Implement | Edit `src/firecube_<plugin_name>/ingestor.py`; the scaffold leaves one reader function unimplemented | filesystem |
| 4. Test | `uv run pytest` in the project | no |
| 5. Install | `firecube plugins install --editable <workdir>/firecube-<plugin-name>` | Python environment |
| 6. Inspect | `firecube plugins list`, `plugins describe <plugin_name>`, `plugins explain <plugin_name>.<tier>.<field>`, `firecube ingest <plugin_name> --show-options` | no |
| 7. Ingest | `firecube ingest <plugin_name> ... --target file:///<abs-path>/<product>.zarr` | target storage |
| 8. Package/publish | Entry point in `pyproject.toml`, `uv build`, publish to an index or git | filesystem |

## Choose A Template

### Evidence Required First

Do not pick a row from the table below until both of these are known:

1. **What the user will do with the product.** Filter and join records, open arrays over time, serve a regular grid to analysis tools. Ask this in plain terms; do not expect the user to name Parquet or Zarr. The format recommendation is yours to make from the inspected data (step 2 and the mapping table below).
2. **What one real product contains.** Inspect a file the user supplies, or read the official product format specification. Record dimension names and sizes, coordinate variables and whether they are 1-D or 2-D, data variables and dtypes, fill values and flags, and whether the shape is the same across at least two granules.

Not evidence: a Data Store collection ID or title, a catalogue abstract, a product filename or its naming convention, a SIP or manifest listing, the packaging (zip, SEN3, SAFE), the instrument or processing level, or a Firecube tutorial for a different collection from the same mission. Two products of the same instrument and level can have entirely different shapes. If neither the file nor the specification is in the conversation, ask the user whether they have a product on disk and for its path, or hand off to the `eumdac` skill to obtain one or two products; resume once the user names the directory holding the files. Do not search the user's filesystem for data files; the user says where their data is.

When the operator supplies notebooks, tutorials, or scripts for the product, open every one they name, list the claims each makes about the product (file layout, variable names, packaging, cadence, processing steps), and mark each claim in the plan file as verified on an inspected file or unverified. They are a source of claims to check, not evidence, and the operator may already have warned that they are stale.

Evidence comes from four sources that answer different questions. Use them together; none replaces the others.

| Source | Cost | Answers | Does not answer |
| --- | --- | --- | --- |
| The operator | One question | Product variant, what the axes and categories mean, cadence and gaps, what they will do with it, whether to consult the manual | Exact dimension names, dtypes, fill values |
| Data Store collection metadata (the public browse API, one fetch) | Small | Product family, level, timeliness, stated resolution, temporal coverage, packaging hints | File layout, variable names |
| Two or more product files | Minutes | Dimensions, coordinates, variables, dtypes, fill values, valid fraction, shape constancy, adjacency of consecutive granules | Labels for integer indices, cadence over a day, variants and re-issues, coverage over a season, flag semantics |
| Product format specification or user guide | Large if read whole | Labels, flag meanings, variants, cadence, everything the files leave implicit | Whether the files actually look like that today |

Ask the operator first: they usually know the product better than any document, and they can say outright "check the user manual" when they do not. Fetch the collection metadata alongside the files; it is one cheap call. Two files establish layout but not everything, so after inspection list what is still unknown and take each item to the operator, the metadata, or a targeted page of the specification. One complete time unit (every file of one orbit, cycle, or day, whichever the design chose) establishes what two files cannot: whether the identity fields assumed constant per group really are (a polar orbit carries both an ascending and a descending pass), how consecutive files meet (a repeated boundary scanline, a gap, an overlap), and whether the group's attributes and ordering coordinate survive the appends. The group key and the attributes are final only after one complete unit has been ingested and checked. Never convert a whole user guide or specification to text: a 60-page PDF costs tens of thousands of tokens and most of it is irrelevant. Extract the text once, search it for the dimension, variable, and flag tables, read only those pages, and record what was learned in the plan file. The specification never replaces inspection for the recommendation itself.

Inspection of a user-supplied product (read-only): run the skill's script on each product, once, and let the
sidecar carry the detail:

```bash
uv run <skill-dir>/scripts/inspect_product.py <product-file-or-zip-or-dir> --out <plan-dir>/inspect-<n>.json
```

It prints dimensions, coordinates, global attributes, variable counts, every time-like variable with its
dimensionality and monotonicity, and one variable's valid fraction; the full variable table goes to the sidecar,
which the plan file references. The manual equivalent, for a case the script does not cover:

```bash
unzip -l <workdir>/<product>.zip                       # which members exist; note every .nc
python - <<'EOF'
import xarray as xr
ds = xr.open_dataset("<extracted-file>.nc", decode_times=False)
print(ds.dims); print(ds.coords)
print(dict(ds.attrs))                                    # identity, counters, start/end, baseline, platform
for v in ds.variables:                                   # every variable, not a sample
    print(v, ds[v].dims, ds[v].dtype, ds[v].attrs.get("_FillValue"), ds[v].attrs.get("units"))
for v in ds.variables:                                   # time-like variables: shape and ordering
    if "time" in v.lower() and ds[v].ndim:
        print(v, ds[v].dims, "monotonic along first dim:", bool((ds[v].diff(ds[v].dims[0]) >= 0).all()))
EOF
```

Write the complete tables into the plan file; later steps (append coordinate, grouping key, variable handling) read from there. Repeat on a second granule and compare `ds.dims`. Also check the fraction of valid (non-fill) values in the main variables: a granule can be structurally complete and 100% fill when the retrieval conditions were not met. If the first granules are empty, inspect one where the retrieval is expected before judging density.

### Design The Cube Before Choosing The Format

The inspection tells you what one file holds. It does not tell you what one time step of the product should be. Decide that first, or the format choice will be made by accident.

1. **Choose the time unit from the acquisition geometry, not from the file.** A granule is a delivery unit, not a time step. Geostationary imagers: the repeat cycle. Polar orbiters: the orbit or half-orbit (ascending and descending kept apart), or a day when the data owner accepts a daily composite. Point or event data: the event timestamp. If the time step were the granule, a polar-orbiter cube would span the globe with one thin strip of valid data per step, and that sparsity is a design artefact, not a property of the data.
2. **Separate coverage sparsity from retrieval sparsity.** Coverage sparsity (each file covers a small area) is removed by choosing the right time unit and combining the files that belong to it. Retrieval sparsity (fill where the retrieval could not run: cloud, night, quality) is inherent to the product, is present in every format, and is not an argument against a cube.
3. **Choose the output geometry with the operator.** Two families exist and both are normal. Combining without aggregation keeps every pixel value: along-track concatenation of consecutive swath granules does this (a fixed across-track size with a varying along-track length is the signature of granules cut from one continuous swath, and they abut without overlap), and it gives a lossless archive on the sensor's geometry. Regridding is the analysis form: a regular lat/lon grid, HEALPix, a daily or per-pass composite. It changes values as soon as two source pixels share a cell, so state that once, with the binning rule, and let the operator choose; it is a legitimate choice, not a fallback to argue against. Ask which geometry, and which one is the default when both are wanted. Only when the operator has no preference at all keep the geometry of the source data.
4. **Say so when a request does not work.** If the chosen layout makes the implementation disproportionately hard, or the product unusable for the stated goal (a per-granule global grid that is almost all fill, a grid too large for memory, a template that cannot express the layout), say that plainly with the reason and the alternatives, and ask. It is fine to ask, to explain, to search the documentation, or to stop and wait. It is not fine to substitute a different design silently.
5. **Only now map to a template.** Ask the user what they will do with the product; recommend from the design above.

| Design outcome | Points to |
| --- | --- |
| One array per time step on the sensor's native grid, constant shape once files are combined per time unit | `zarr` append along time (`GenericZarrIngestor`), the batch being one orbit, half-orbit, or cycle |
| One array per time unit whose extent differs between units (a swath strip per orbit), combined from files by concatenation along the acquisition axis | `zarr` append along that acquisition axis, one group per time unit (`GenericZarrIngestor` with `get_batch_groups`), ordering coordinate derived per file; a unit can then keep growing as its files arrive |
| Same, with a fixed time axis known in advance and parallel writers wanted | `zarr --write-strategy zarr-python` (`DirectZarrIngestor`) |
| Regular gridded fields with 1-D lat/lon and constant shape per file | `zarr` append along time |
| Point or event records with no natural array shape, one row per detection | `parquet` |
| Per-pixel records wanted for filtering and joining, or the owner has ruled out a cube | `parquet` |
| A second output geometry wanted beside the first (a composite, a regrid, a subset beside the native archive, or the reverse) | An output of the same plugin, selected by a plugin option (`output=<view>`; the operator says which one is the default) and written to its own store: one run has one append dimension, and the engine reads it from the class (`time_dim_name`) before any batch hook. When the view's append dimension differs from the main output's, register a second ingestor class for it in the same package (own `@register_ingestor` ID and entry-point key, shared reader and config); never override `run()` or `_resolve_time_dim_name` to switch it. When the data owner supplies the routine that computes the view, port it as it is and record its provenance; otherwise use the Firecube extensions. Expose the view's parameters (spacing, extent, variables) as options. A time step computed across several files needs every one of them in one batch: the engine forms batches by file count, so make the bundle the item (`discover_source_files` returns one object per orbit or day; see templates.md, Batch Lifecycle) or use direct-write slots. Never one slice per source file on a fixed grid: each covers a small area and the cube is almost all fill. Only after the owner accepts what the view changes |

A swath with 2-D latitude and longitude and a per-file shape that varies is not a reason to pick Parquet. It is a reason to combine files per time unit first.

### Reasoning Traps

Each row is a real failure pattern: a true observation, the conclusion it tempts, and the check that prevents it. Rows are for misreadings of what a file or a run output shows; how to conduct the work belongs in the operating rules and the procedure, not here.

| Observed | Tempting conclusion | Check first |
| --- | --- | --- |
| 2-D lat/lon, shape varies per file | Not a cube, use rows | What is one time step for this sensor? Combine files per orbit or cycle first |
| Files on disk are in a format outside Firecube's built-in discovery and outside any reader the plugin could implement | Write a decoder, or hand off to the `eumdac` skill | Stop; ask the operator for a conversion they own or a converted sample; never write a decoder for the format found on disk, and the `eumdac` hand-off is only for an identifiable EUMETSAT Data Store collection |
| Archives extract fine in a test | Extraction errors will raise | `extract_all_from_zips` reports failures in its result and never raises; check the `failures` mapping in `read_dataset` |
| The operator names several candidate datasets or workflows in one message and commits to none | Gather evidence for all of them, or pick one on their behalf | Ask which one to start with before any Data-step evidence gathering; never fan out design work across candidates the operator has not chosen between |
| The source files carry no time coordinate; a time value exists only as a global or group attribute | Firecube will infer time from the file | The plugin must derive the time value from the attribute in `read_dataset` and declare it as the append dimension; check the attributes of every group, not only the root, before concluding none exists |
| A template does not fit the case exactly (atomic bundles, several groups, a second axis, a custom writer detail) | Drop to `BaseIngestor` for a specialised pipeline | Extend the template first: items may be bundles, `get_batch_groups`, `prepare_batch_data`, `get_zarr_config`, `write_parquet`, direct-Zarr write intents. `BaseIngestor` only for a limitation you can name and have verified in the template source, with the operator's explicit decision |
| Low valid fraction | Data is sparse, favour records | Coverage sparsity or retrieval sparsity? Only the first is a design problem |
| A regridded or composited output is wanted | Argue the operator back to the native geometry, or make the view the only output without asking | Regridding is a normal analysis choice; say once what it changes and ask which outputs they want and which is the default. Both are outputs of the same plugin |
| Operator asks for regridding, joins or a viewer | Defer it to a separate future product | Derived views belong to the same plugin as options; deferring them leaves the operator with a cube their tools cannot open |
| Owner supplies the routine that computes a view | Design a different rule | Port the owner's routine as it is and cite it; check only that its docstring claims match its code |
| A guard was added to make the implementation easier (one worker, one write mode, immutable inputs) | Present it as a requirement of the data or of Firecube | State it as an implementation limit: the shared state or hook it protects, and what would lift it. Verify against the engine source before claiming Firecube forbids something |
| First granules are all fill | Product is empty or broken | Inspect one where the retrieval is expected |
| Two files inspected | Everything is known | List what files cannot tell you: labels, cadence over a day, variants, flag meanings; ask the operator, then metadata, then the spec |
| Operator says "test cube" or "one-off" | Pick the simpler append template | Template follows the data design; scale only shortens the horizon. Estimate size and time first |
| A per-pixel or per-file time variable exists | Use it as the append coordinate | Check its dimensionality and monotonicity on the inspected files; derive an ordering key if it fails |
| `Found <n> files` is printed | Discovery is correct | Is n the number of products, or the number of physical files that matched? |
| One ingestion succeeds and the tests pass | The plugin works | Re-run with `pipeline_batch_size` below the files per time unit and compare the products |
| A group is missing from the store after a clean run | Something else failed | Does its dataset carry `time_dim_name` with a size above zero? The append writer skips such groups without a log line |
| A search listing or a sample set shows one platform, direction, or baseline | The collection has only that one | Group the listing by the identity field and read the collection metadata before concluding |
| An identity field shows two values | Sample one and generalise | Ask the operator whether both are in scope; each in-scope value gets a sample and a place in the group key |
| Two files that should be the same time step differ only by an identity or provenance attribute (platform, processing stream, version) | Merge them | Ask the operator; default to keeping them in separate groups; never merge silently |
| Every sampled file of one time unit has the same value of an identity field | The field is constant per unit; store it as a group attribute | Ingest one complete unit; a field that varies inside it belongs in the group key or in a per-row coordinate |
| Series metadata (attribute wording, casing, provenance text) changes partway through a series while the data variables stay the same | The first file inspected represents the whole series | Inspect the first and last file of the series, not only one; group attributes are frozen at first write (see Zarr Layout Rules, plugin-traps.md), so decide with the operator what the stored attributes should say before the first real ingestion |
| Two consecutive files abut in time | They do not overlap | Compare the boundary scanlines of a full unit: a repeated coordinate with identical geolocation is an overlap to drop, with different geolocation a distinct scanline to keep |
| A guard's tests pass and it never logs | It works | A guard that swallows its exceptions is indistinguishable from one that never ran; log the failure and check it fired on a full unit |
| A re-run after a failed run reports the earlier batches as already present | Rerunning without a flag will just continue from there | Firecube refuses: succeeded spans left by a failed run block a plain re-run; use `resume_existing=true` to keep them or `force_reingest=true` to redo them |
| The plugin writes Parquet and a retry targets the same output | Point the retry at the same target and rerun | `GenericParquetIngestor` refuses resume and force on an existing target unconditionally; every run, including a retry, needs a fresh target |
| A plugin option named `include_patterns` is remembered from an earlier version | It still filters source files | `include_patterns` is removed and raises `ValueError`; use `--input-filters` or the `input_filters` config key instead |
| The scaffolded Zarr ingestor raises `NotImplementedError` on the first batch | The scaffold or the install is broken | `TIME_DIM` is left empty on purpose; set it to the time dimension `read_dataset` returns before running |
| First ingestion passes at the default batch size | The time encoding on the append coordinate is fine | xarray infers `units` per batch from the values it sees; declare a fixed `encoding["units"]` and `calendar` in `read_dataset`, then run once with `pipeline_batch_size=1` and compare against a normal-batch-size run with `firecube zarr compare`, since per-batch inferred encodings can differ |

When a data owner overrules a recommendation, ask for the reasoning: it may name a step the design procedure missed for this case.

### Recommend, Then Defer

After inspection, ask what the user wants to achieve before settling the recommendation; use a structured question tool when one exists, with options such as analysis pattern (regional time series, per-pixel filtering and joins, model input on a regular grid, archiving), output geometry (native swath, regular lat/lon grid, HEALPix, composite; more than one is allowed, then which is the default), time step (half-orbit, orbit, daily composite), variable subset, and one-off versus operational. Then state the recommended template with the reasons it fits the data and that goal, the reasons the alternative fits less, and what answer would flip the choice. Present it as a recommendation, not a verdict. The operator's decision is final. The recommendation always names the template it rejects and the exact constraint that rules it out, verified in the installed template source or the public docs (operating rule 17); a recommendation that only argues for one template invites the operator to ask about the other.

At every later decision point, ask again with the structured question tool rather than a closing sentence: after a clarifying answer (for example what a preallocated horizon means), before scaffolding, before installing, before the first ingestion, and whenever a constraint surfaced that could change the design. Offer the next step, the alternatives the constraint opened, and "something else". The operator may have changed their mind, and a yes-or-no sentence at the end of a long answer hides that. If they choose a format that does not fit the data, give the implications once, ask them to confirm, and then implement exactly what they chose without further argument.

| Operator wants | Data is | Implications to state once |
| --- | --- | --- |
| Zarr | Tabular or ragged records (rows per detection, variable row counts per granule) | Needs an artificial record dimension or padding; appends are serialized per group; filtering by attribute means scanning arrays; no per-granule shape is preserved. Workable with `GenericZarrIngestor` if every batch returns the same schema. |
| A gridded output (regular lat/lon, HEALPix, composite) | Data on a native geometry with 2-D coordinates | Aggregation: two source pixels can share a cell and values change; state the binning rule once. The plugin computes it in `build_dataset` behind an `output` option, with its parameters as further options. Whether it or the native archive is the default is the operator's choice. |
| Parquet | Imager swath or gridded arrays | Each pixel becomes a row; volume multiplies by grid size; array structure and neighbourhood are lost and must be rebuilt by readers; fine for sparse or flagged subsets, wrong as the default for imagery. |
| Direct Zarr with parallel slots | Irregular timestamps or unknown extent | Only with `TimeAxis.discovered`; extent must be known before writes; more schema work than append. |

| Input shape the plugin can supply | Create with | Class | Output |
| --- | --- | --- | --- |
| Complete, ordered `xarray.Dataset` per batch, appended along one time dimension | `--template zarr` (default) | `GenericZarrIngestor` (Append) | Zarr group(s); serialized appends |
| Rows: `pyarrow.Table` or `pandas.DataFrame` per batch | `--template parquet` | `GenericParquetIngestor` (Tabular) | Parquet dataset root with part files |
| Arrays at known positions on a declared time axis; workers may write disjoint slot ranges of one group | `--template zarr --write-strategy zarr-python` | `DirectZarrIngestor` (Region) | Preallocated Zarr arrays written by region |
| Same, but timestamps are irregular and only known after reading items | Region scaffold, then `TimeAxis.discovered(...)` in `index_spec` | `DirectZarrIngestor` (Auto) | Axis discovered before any write |
| A serious, named limitation: none of the three templates can express the output even with their hooks (bundle items, `get_batch_groups`, `prepare_batch_data`, `get_zarr_config`, `write_parquet`, write intents) | `--template base`, last resort, operator's explicit decision | `BaseIngestor` (raw engine contract) | Plugin-defined; the plugin loses the managed writer, format-aware resume, schema drift checks, and every parallelism model |

- The source file format does not decide the class; the data the plugin can return does.
- `DirectZarrIngestor` also runs serially; choosing it does not enable parallel writes, it adds schema and index work.
- `BaseIngestor` is the engine's lowest-level contract, not a template: no runtime-managed writer, no public storage-writer protocol yet, no format-aware resume or drift checks, no parallel model. Offer it only when a limitation of the three templates is named and verified in their source (rule 17), state what is lost, and let the operator decide. "Specialised" or "more control" is not a limitation. Never import internal storage modules to compensate.

Guides: https://eumetsat.github.io/firecube/latest/guides/plugins/generic-zarr/ , .../generic-parquet/ , .../direct-zarr/ , .../direct-zarr-auto/ , .../base-ingestor/ .

## Create The Project

Before running anything:

1. Present the final design summary inside the structured question itself (its text or preview field), not in prose above it: the operator may see only the question. Cover template and class, groups and arrays, time axis and horizon, variables carried, plugin options, and what the first test run will do. Offer "confirm", "change something", and "stop".
2. Collect what the scaffold would otherwise prompt for, with the question tool, including the free-text values: the plugin name (the distribution name given to `plugins create`, and the registered ID derived from it), author name, author email, licence, and target directory. Every one of them goes through the question tool under the Response Contract rules: a value found in context is a suggestion until the operator selects it, one candidate is still a question, and a tool error is not an answer. Five values against a four-question limit means author and email as one question, or two calls. For the licence, offer the common choices with a one-line meaning each (Apache-2.0 with patent grant, MIT minimal permissive, BSD-3-Clause permissive with no-endorsement clause, EUPL-1.2 EU copyleft compatible with several others, GPL-3.0 strong copyleft, or none for now) and let the user pick or name another, with no option marked as recommended. Context worth stating, as context only, is the licence of Firecube and its public plugins and of the operator's own plugins in a workspace they named; the licence of an input document such as a notebook, tutorial, or sample dataset says nothing about the plugin. These are the user's identity and legal choices; never invent them or reuse them from another project, and never pass `--non-interactive` with values the user did not give. If the user prefers, run the scaffold interactively and let them answer the prompts.
3. Only then run `plugins create`.

Mutating: writes `firecube-<plugin-name>/` under `--target-dir` (default: current directory) and fails if it exists. `<plugin-name>` must start with a letter and contain only letters, digits, `-`, and `_`; any other name is rejected before anything is written. The class name derives from the snake-case id with acronym splitting (`HTTPServer` becomes `HttpServerIngestor`). `--write-strategy` is only meaningful with `--template zarr`; passing it with `--template parquet` or `--template base` is a usage error.

```bash
firecube plugins create <plugin-name> \
  --target-dir <workdir> \
  --template zarr \               # zarr | parquet | base
  --write-strategy xarray \       # xarray (append) | zarr-python (region); zarr template only
  --author "<author-name>" --license Apache-2.0 \
  --non-interactive               # omit to answer prompts for name, author, email, license, template, strategy
```

`--email TEXT` is optional; omitted, the scaffold writes a placeholder address. `--license` accepts an SPDX identifier or expression (`MIT`, `Apache-2.0`, `GPL-3.0-or-later`, ...); any other value is recorded as `LicenseRef-<value>` rather than rejected. Scaffolded tree (same shape for every template; only the ingestor body and dependencies differ):

```text
firecube-<plugin-name>/
├── pyproject.toml                    # entry point, deps, dev group (pytest, ruff, pyright)
├── README.md                         # generated implement -> test -> install -> ingest steps
├── src/firecube_<plugin_name>/
│   ├── __init__.py                   # imports the ingestor so @register_ingestor runs
│   └── ingestor.py                   # full template wiring; reader or TIME_DIM blocks until set
└── tests/
    ├── __init__.py
    └── test_ingestor.py              # test_entry_point_registers_the_ingestor
```

Generated `pyproject.toml`: `requires-python = ">=3.12"`, `dependencies = ["firecube>=0.1.5", ...]` plus `xarray`+`h5netcdf` (zarr/xarray), `pyarrow` (parquet), or `numpy` (zarr-python) by template, `hatchling` backend, `license = "<SPDX string>"`. The generated lower bound is always `firecube>=0.1.5` regardless of the CLI's own version; tighten it to a pinned bound (`firecube==<version>`) before the first real ingestion, not only before publishing, since an unbounded lower bound on the plugin's own dependency can drift from the version actually installed the moment the editable install is re-run in a different environment; `check_plugin_contract.py`'s `firecube-pin` check warns on an unbounded `>=`. Every generated source file (`__init__.py`, `ingestor.py`, `test_ingestor.py`) carries a `# Copyright <year> <author>` and `# SPDX-License-Identifier: <license>` header from the values given to `plugins create`. Fields:

```toml
[project.entry-points."firecube.plugins"]
<plugin_name> = "firecube_<plugin_name>"
```

Reader to implement per template, in `ingestor.py`: the zarr/xarray template's `read_dataset(path: Path) -> xr.Dataset` ships a working NetCDF example (`xr.open_dataset(path).load()`), and instead blocks on the module-level `TIME_DIM = ""` constant, which raises `NotImplementedError` from `build_dataset` until set to the time dimension `read_dataset` returns; it also declares a `ZarrStorageConfig(ZarrTemplateConfig)` class with commented `zarr_chunk_shape`, `zarr_compression`, `zarr_codecs`, `zarr_sharding`, and `zarr_shard_shape` defaults for this plugin. The parquet template's `read_table(path: Path) -> pa.Table` and the zarr-python (direct) template's `read_product_item(path: Path) -> tuple[np.datetime64, np.ndarray]` raise `NotImplementedError` until replaced; the base template's `write_product_item(source, target_dir) -> Path` likewise. Implement the reader (and, for zarr/xarray, set `TIME_DIM`) and the scaffold is runnable.

## Source Discovery

Discovery is a pipeline of hooks that runs in a fixed order and works on physical paths, not logical products (verified in `firecube/core/formats/discovery.py` and `firecube/ingestor/runtime/{base,batching}.py`):

1. `discover_source_files(ctx)` yields items. The default (all templates) calls `discover_input_files(ctx.source)`: a recursive walk below `--input-data` (local path, `file://`, or `s3://`, read through the configured storage driver, so `--storage-driver obstore` covers this read too), selecting files by a suffix set (default `.zip`, `.h5`, `.nc`, `.nc4`, `.hdf`, `.he5`, matched case-insensitively), plus any local file whose suffix is *not* in that set but whose content sniffs as HDF5 (not only extensionless files: with `include_suffixes=(".zip",)` a NetCDF-4 file is still selected because it is HDF5 inside; pass `sniff_hdf5=False` to make the suffix set exclusive), plus anything matching the configured `input_filters` (`preferred_globs`; positive entries add, `!`-prefixed entries exclude and always win). Glob matching against `preferred_globs` and `exclude` is case-sensitive on every platform. A `file://` source returns plain paths, not `file://` URIs. The result is de-duplicated by path only and sorted by **basename** across the whole tree.
2. `filter_item(item, ctx)` keeps or drops each item after discovery and before batching.
3. Items are chunked into batches of `pipeline_batch_size` in discovery order. Only then is `get_batch_groups(items, ctx)` called, once per batch; it must be deterministic.
4. `ctx.materialize(item)` resolves a remote item into the run cache and returns a local path. It does not open archives: `extract_all_from_zips` and `materialize_hdf5_path` from `firecube.core.api` handle archive members, otherwise the plugin's reader does.

What the plugin must decide from this:

- **What one item is.** The default item is a path string; `SourceFile`/`LocalSourceFile` from `firecube.ingestor.api`, or a plugin object holding several paths, are allowed as long as every downstream hook handles them end to end. When the unit you combine per time step is the item, it cannot straddle a batch; when files are the items, the plugin must handle a time unit split across batches.
- **One item per product.** The default selects every physical file that matches, so a product present in more than one physical form, or spread over several files, yields more items than products. Define the product identity from the inspection, then choose the narrowest mechanism that yields exactly one item per product: a smaller suffix set, `exclude`, `filter_item`, or a full override.
- **Every item maps to exactly one group.** An item whose group key resolves to nothing is a discovery error: reject it in `filter_item` with a log line, or raise. Never let `build_dataset` drop it silently; `files_processed` and the chunk records still count it, and the mismatch stays invisible.
- **Order.** Basename order is not directory order and not necessarily time order. Check that it matches the order the combination relies on, or sort in the override.
- **Count.** The run logs `"message":"Found <n> files"`. Zero is a discovery problem, not an ingestion failure; a count that differs from the number of products you expect is a discovery-design problem.

| Need | Do |
| --- | --- |
| Add filename patterns without code | `--input-filters '["*.nc4","!*_quicklook.nc"]'` on the command line (also on `zarr slots`/`zarr preallocate`), or `input_filters = [...]` under `[plugins.<plugin_name>]` in `config.toml`; positive entries add, `!` excludes and always wins, `[]` clears a configured list; a custom discovery hook must forward `self.engine_config.input_filters` to `discover_input_files(..., preferred_globs=...)` itself, this is not automatic. The removed `include_patterns` engine option now raises `ValueError` |
| Exclude files or change suffixes | Override the hook and call `discover_input_files` |
| Non-file sources (API, database) | Override `discover_source_files` to return any items; every hook that consumes them must handle that type |
| Remote listing with explicit credentials | Pass `storage_config=` to `discover_input_files`; do not build your own fsspec/S3 client |

```python
from firecube.core.api import discover_input_files

def discover_source_files(self, ctx):
    return discover_input_files(
        ctx.source,
        include_suffixes=(".nc", ".nc4"),           # replaces the default suffix set
        exclude=["*_quicklook.nc", "incoming/*"],   # applied before selection, wins over preferred_globs
        recursive=True,                             # preferred_globs=[...] adds patterns in code
    )
```

Multi-group writes: override `get_batch_groups(items, ctx)` to return a stable, sorted list such as `["quality", "sst"]`. The write hook then runs once per group with the full batch; branch on `group` inside `build_dataset`. Each name becomes a Zarr group path (nested `"sst/quality"` is valid). `DirectZarrIngestor` derives groups from `zarr_schema`; do not override there. Guide: https://eumetsat.github.io/firecube/latest/guides/plugins/multi-group-writes/ .

### Discovery Recipes

**Data inside an archive.** No `discover_source_files` override needed: `.zip` is already in the default discovery suffix set. Only `read_dataset` changes.

```python
from pathlib import Path
from tempfile import TemporaryDirectory

import xarray as xr

from firecube.core.api import extract_all_from_zips

MEMBER_PATTERN = "*.nc"

def read_dataset(path: Path) -> xr.Dataset:
    with TemporaryDirectory() as folder:
        extracted, failures = extract_all_from_zips([path], lambda _: Path(folder))
        if failures:
            raise RuntimeError(f"Cannot read {path}: {failures[path]}")
        members = sorted(extracted[path].rglob(MEMBER_PATTERN))
        if len(members) != 1:
            raise RuntimeError(
                f"Expected one {MEMBER_PATTERN} member in {path}, found {len(members)}"
            )
        with xr.open_dataset(members[0]) as dataset:
            return dataset.load()
```

Use when one archive holds exactly one data file. Watch: `extract_all_from_zips` never raises on a bad archive, it reports the failure in the returned `failures` mapping, so check that before indexing `extracted`; raise on 0 or more than 1 matched member so a malformed or repackaged archive never produces an empty or ambiguous dataset. A directory mixing archives of different cadence or type needs an exclusion (`exclude=` or `--input-filters`) so one kind never reaches a reader built for the other.

**Fields that exist only in the filename.** Requires the `firecube[patterns]` extra, added to the plugin's own dependencies (`uv add 'firecube[patterns]==0.1.7'`), not only the developer's shell.

```python
from pathlib import Path

import numpy as np
import xarray as xr

from firecube.ingestor.extensions import parse_pattern

TIME_DIM = "timestamp"
PATTERN = "reading_{sequence:04d}_{recorded:%Y%m%dT%H%M%S}.nc"

def read_dataset(path: Path, filename: str) -> xr.Dataset:
    try:
        fields = parse_pattern(PATTERN, filename)
    except ValueError as exc:
        raise ValueError(f"Unexpected filename: {filename}") from exc
    with xr.open_dataset(path) as source:
        dataset = source.load()
    return dataset.expand_dims(TIME_DIM).assign_coords(
        {TIME_DIM: [np.datetime64(fields["recorded"], "ns")]}
    )
```

Use when a timestamp or another field exists only in the filename, not inside the file. Watch: a non-matching filename raises `ValueError` from Trollsift, never a silent skip; call `read_dataset` with the filename taken from the source item (`Path(item).name`) inside `build_dataset`, never from `path`, since a remote item materializes under a hashed local name.

**Paired source files (one time step spans two or more files).** Override three hooks together; follow the paired-source-files guide.

```python
import logging
from pathlib import Path

import xarray as xr

log = logging.getLogger(__name__)

def discover_source_files(self, ctx):
    for filename in super().discover_source_files(ctx):
        reading = Path(filename)
        if reading.suffix != ".nc":
            continue
        yield reading, reading.with_suffix(".json")

def filter_item(self, item, ctx):
    reading, calibration = item
    if not calibration.is_file():
        log.warning("Dropping incomplete pair: %s", reading)
        return False
    return True

def build_dataset(self, group, items, ctx):
    datasets = [
        read_dataset(ctx.materialize(reading), ctx.materialize(calibration))
        for reading, calibration in items
    ]
    ...
```

Use when one time step needs two or more files (a reading plus its calibration or metadata) and either file can be missing. Watch: the pair is the item, not the file, so it cannot straddle a batch; `build_dataset` must call `ctx.materialize` on every member before reading, since it resolves one path at a time, never a tuple, and the engine's default `item_size_bytes` returns `None` for a non-path item rather than raising. See the paired-source-item row in [plugin-traps.md](plugin-traps.md) for the byte-count and materialize details; do not repeat them here.

Further source-discovery guides: https://eumetsat.github.io/firecube/latest/guides/plugins/source-discovery/ (built-in discovery and filters), .../discover-zipped-data/ (data inside `.zip` archives), .../parse-filename-fields/ (values that exist only in the file name, via `firecube.ingestor.extensions.parse_pattern`), .../paired-source-files/ (two files per source item), .../customize-source-discovery/ (redirects to Discover Source Data) .

## Implement The Ingestor

Import from `firecube.ingestor.api` (types, templates, errors) and `firecube.core.api` (helpers) only. Every class needs `@register_ingestor("<plugin_name>")` and a non-empty `PRODUCT_NAME: ClassVar[str]`; do not add a `name` attribute beside the decorator. Class declarations: `time_dim_name: ClassVar[str]` (default `"timestamp"`; must match the returned dataset's dimension or the write raises `ValueError`), `plugin_config_class`, and template-owned `template_config_class`.

Before writing any hook, read [plugin-traps.md](plugin-traps.md): the public hook contract (never override `run`, never use `_`-prefixed Firecube names), the resume and extension rules (never return `[]` from discovery), the Zarr layout rules, and the traps real plugins fell into. Per-template contracts, hook tables, skeletons, the context and exception tables, and the batch lifecycle are in [templates.md](templates.md). What the engine does with the plugin's hooks under workers and write modes, and the state rules that follow, are in [parallelism.md](parallelism.md); read it before adding any worker or write-mode guard.

## Configuration Options

`firecube plugins describe <plugin_name>` prints three tiers: `[ENGINE]` (`pipeline_workers`, `pipeline_batch_size`, `input_filters`, `force_reingest`, `resume_existing`, `no_progress`, slot flags, ...), `[TEMPLATE]` (`zarr_chunk_shape`, `zarr_compression`, `zarr_consolidate`, ... or `parquet_*`), and `[PLUGIN]` (yours). `firecube ingest <plugin_name> --show-options` lists the same keys as `--option` names. `firecube plugins explain <plugin_name>.<tier>.<field>` with tier `engine`, `template`, or `plugin` shows type, default, and allowed values.

Declare typed plugin options with a `@dataclass` `PluginConfig` subclass and read them from `self.plugin_config`, never from `ctx.option()`. Validate combinations in `__post_init__` (raise `ConfigurationError`). `plugin_config` is assigned inside `run()` after construction, so nothing that the engine reads from the class before the first batch (the append dimension `time_dim_name` above all) can come from it; such choices are separate registered classes, never a `run()` override. Keep the run window (`start`, `end`) and access settings out of the store identity: `slice_meta_keys`/`slice_meta` name only the options that must not change for one store (plugin-traps.md, Resume). Screening rules copied from an operator's notebook are claims: check each against the flag's `flag_masks`/`flag_meanings` and the variable's `valid_min`/`valid_max` on a real file before adopting it (a bitmask compared to a scalar rejects everything).

```python
@dataclass
class MyConfig(PluginConfig):
    scale_factor: float = 1.0          # shows as [PLUGIN] scale_factor [number] (default: 1.0)

class MyIngestor(GenericZarrIngestor):
    plugin_config_class = MyConfig
    def build_dataset(self, group, items, ctx):
        config = self.plugin_config
        assert isinstance(config, MyConfig)
        ...
```

| Rule | Detail |
| --- | --- |
| Set per run | `--option scale_factor=0.01` (repeatable `key=value`; unknown keys fail before any hook runs) |
| Set defaults | `[plugins.<plugin_name>]` table in the TOML config (see configuration-storage.md); `x_*` keys bypass the tiers and are read with `ctx.option("x_key", default)` |
| Keep out of `--option` | Product name, target, storage driver, output format, write mode: use their dedicated flags |

Guide: https://eumetsat.github.io/firecube/latest/guides/plugins/add-config-options/ .

## Telemetry And Extensions

Telemetry: guard with `if ctx.telemetry is not None`, then `with ctx.telemetry.span("<plugin_name>.parse", {"group": group}): ...` and `ctx.telemetry.emit("<plugin_name>_files", len(items), kind="counter", meta={"group": group})` (`kind` is `counter` or `gauge`; exported as `firecube_<plugin_name>_files_total`). Keep labels low-cardinality (no paths, timestamps, run IDs). Use `logging.getLogger(__name__)`; never configure handlers or exporters or use `print()`. Guide: https://eumetsat.github.io/firecube/latest/guides/plugins/observability/ ; metrics reference: .../reference/observability/ .

| Extension | Import | Notes |
| --- | --- | --- |
| `DuckDbMixin` | `firecube.ingestor.extensions.duck` | `class MyIngestor(DuckDbMixin, GenericParquetIngestor)`; implement `prepare_duckdb_schema(con, ctx)`; use `self.con` only inside batch hooks. Append and Parquet templates drive setup/teardown; Direct Zarr does not; Base calls the hooks itself. |
| Lat/lon gridding | `firecube.ingestor.extensions.grid` | `build_latlon_binner(lat=, lon=, grid_spacing=, bounds=)` then `regrid_with_binner(binner=, data=, aggregation=)`. `aggregation` is one of `mean`, `min`, `max`, `first`, `last`, `median`, `any`; NaN inputs are dropped before aggregating; empty cells are NaN (`any`: 0); results are float32 except `any`, a uint8 presence mask. `build_latlon_binner` and `LatLonBinner` are package exports; `regrid_with_binner` is not, import it from `.grid`; `bounds` is required for any grid that is appended to, otherwise each batch derives its own extent and the next append fails on a dimension mismatch |
| Filename field parsing | `firecube.ingestor.extensions.parse_pattern(pattern, text)` | Needs `uv add 'firecube[patterns]==0.1.7'` (Trollsift); parses a complete string against a named-field pattern (`"measurement_{recorded:%Y%m%d}.nc"`), preserving field names and types; no filesystem access or timestamp interpretation beyond what the pattern names |
| HEALPix gridding | `firecube.ingestor.extensions.healpix` | Needs `uv add 'firecube[healpix]==0.1.7'`; `target_cells` fixes one cell axis |

Reference: https://eumetsat.github.io/firecube/latest/reference/extensions/ .

## Test Locally

```bash
cd <workdir>/firecube-<plugin-name>
uv sync                                  # project-local .venv with firecube and the dev group
uv run pytest                            # scaffolded test: entry point and @register_ingestor agree
```

`test_entry_point_registers_the_ingestor` loads the `firecube.plugins` entry point declared in `pyproject.toml` (via `importlib.metadata.entry_points(group="firecube.plugins", name="<plugin_name>")`), then asserts `discover_ingestors()["<plugin_name>"] is <Class>` and its `PRODUCT_NAME`. Because it loads the entry point, `uv sync` (an editable install of the project into its own `.venv`) must run first, or the test fails with no matching entry point even when the decorator is correct. It fails when `pyproject.toml` and the decorator disagree, the usual cause of a plugin missing from `plugins list`. Add behaviour tests that call the reader or `build_dataset` on a small fixture and assert shape, dtype, or row count, then cover empty, partial, and malformed input. Sample files come from a fixture directory relative to the project or from an environment variable, and the tests skip when it is absent or does not hold the products they need (check the files, not only the directory); never an absolute path on the developer's machine or outside the repository. A fresh checkout without fixture data must report skips, never errors.

End-to-end smoke test with the developer's own sample files (mutating: writes the target and its `.firecube/` records):

```bash
firecube ingest <plugin_name> \
  --input-data <input-dir> \
  --target file:///<abs-path>/<product>.zarr \
  --product-name <product> \
  --storage-type local --storage-driver fsspec \
  --output-format zarr --write-mode direct \
  --option no_progress=true
firecube chunks list --product-name file:///<abs-path>/<product>.zarr      # expect one span record
python -c "import xarray as xr; print(xr.open_zarr('/<abs-path>/<product>.zarr', group='default', consolidated=False))"
```

Check stderr for `"Found <n> files"` and stdout JSON for `files_processed`, `coverage`, and `stored_at`. Use `--output-format parquet` and a `.parquet` target for the tabular template. Re-running the same input without a flag is refused (`ResumeConflictError`); for the Zarr templates use `--option force_reingest=true` while iterating, or `--option resume_existing=true` after adding new input; for the Parquet template resume and force are both refused unconditionally, so use a new target for every run.

One run proves one batch. Run a second ingestion into a new target with `--option pipeline_batch_size=<n>` smaller than the number of files in one time unit, so that a unit is split across batches, and compare the two products with `firecube zarr compare` (arrays, coordinates, and group attributes must agree). Record both commands, the target URIs, and whether the products were kept in the plan's Log; a validation that cannot be re-run from the Log is a claim, not evidence.

Then ingest one complete time unit (every file of one orbit, cycle, or day) and check the result the same way: group names and attributes constant where the design says so, the ordering coordinate strictly increasing with no repeated value unless the source genuinely repeats a scanline, and the row count equal to the sum of the files minus the overlaps the plugin dropped on purpose. A guard in the plugin that catches an exception and returns a default must log it at least once; a silent guard that never ran looks identical to one that did, so check that it fired on a full time unit, not only that its tests pass.

Then compare one variable against the decoded source: the count of finite values and their sum over every input product must equal the same figures over every group in the store. A mismatch means decoding, masking, or dropping changed values on the way in, whatever the tests say.

### Definition of done

The skill's `scripts/check_done.py` runs every check below as one command and prints PASS/FAIL lines to paste
into the Log (`uv run --project <plugin-project> python <skill-dir>/scripts/check_done.py --plugin-id <plugin_name>
--project <plugin-project> --input-dir <input-dir> --scratch <dir>`); use it
instead of running the steps by hand and printing their output. It runs several ingestions and `uv run` (tests,
ruff), so state that plainly and get the operator's confirmation before running it, and pass `--scratch` set to a
directory the operator named; it writes only a fresh subdirectory of its own inside `--scratch`, never the
operator's directory itself. It starts with `scripts/check_plugin_contract.py`, the static check for private
Firecube API use, `run()` overrides, empty discovery returns, store writes from hooks, and missing referenced
files, which also runs alone in seconds on any plugin checkout. The import boundary is not in that script: it
is a ruff rule the plugin carries in its own `pyproject.toml`, so it runs wherever the plugin's lint runs:

```toml
[tool.ruff.lint.flake8-tidy-imports.banned-api]
"firecube.ingestor.runtime".msg = "private: use firecube.ingestor.api"
"firecube.ingestor.templates".msg = "private: use firecube.ingestor.api"
"firecube.core.storage".msg = "private: use firecube.core.api"
"firecube.core.zarr".msg = "private: use firecube.core.api"
"firecube.cli".msg = "private: not a plugin surface"
```

with `TID251` in the plugin's selected rules. Allowed: `firecube.ingestor.api`, `firecube.core.api` and
`firecube.ingestor.extensions`. On a large input, or a plugin whose ingestion takes
minutes, pass `--quick`: the full input is ingested once, and the split-batch, workers, rerun and force runs use one
product of it (the first by name, or `--quick-glob`) against a one-product reference store, so the lifecycle costs
one small ingestion each instead of a full one; the extension check is skipped in that mode. A plugin that bins or
resamples onto another grid passes `--regridded`: the source-equivalence figures cannot match by construction, so
that check is skipped and the source is not decoded; compare against an independent regrid in the plugin's own
tests instead.

A plugin is done when the plan's Log holds every line below, each with the command that produced it.
`check_done.py` prints them; the flag after an item names the switch that changes it.

- The install's `Detected plugins: <plugin_name>`.
- The first ingestion's `files_processed`, with the found and product counts beside it. A bundling plugin
  reports items (a pass, a day), not files; anything else dropped is explained in the plugin's log.
- The split-batch comparison: a `pipeline_batch_size=1` run equal in groups, sizes, values and attributes to a
  normal-batch run. It catches time-encoding drift that only shows on single-item batches (plugin-traps.md).
  `--quick`: on one product.
- The source-equivalence figures: one variable's finite count and sum over every store group equal to the same
  figures over every decoded source product. `--regridded`: skipped; the plugin's own tests compare against an
  independent regrid instead.
- The test run with its counts, none skipped, against real fixtures, and a second run without the fixture
  variables (a fresh checkout) with zero errors and failures.
- The contract check clean (`check_plugin_contract.py`).
- Zarr templates only: a `pipeline_workers>1` run value-identical to the one-worker run (plugin-traps.md); a
  rerun without a flag refused; a rerun with `resume_existing=true` over the same window leaving the store
  unchanged (present timestamps skipped); an extension run (part of the input first, then all of it with
  `resume_existing=true` over a genuinely new window) value-identical to the one-shot store; a
  `force_reingest=true` run value-identical as well. `--quick`: all on one product, extension skipped.
  `--skip-lifecycle`: none of them.
- Parquet template: a rerun into the same target refused regardless of flag, every run against a fresh target.
- Every file the README, docs, or notebooks reference exists.
- A performance number in the docs only with its benchmark record (benchmarks.md): full scale, the machine, the
  command; never extrapolated from a sample.

Reporting completion without those lines is a claim, not a result. A run that stops before them ends with an
open item and says so; it does not say the plugin is built. If any figure disagrees (processed count,
split-batch comparison, source equivalence, tests), the plugin is not done: report the disagreement with its
command output, and do not report completion. The published example plugin
(https://github.com/eumetsat/firecube-quickstart-plugin) ships a data generator
(`python scripts/generate_sample_data.py`) for its own time-indexed NetCDF layout; clone it and run
`firecube plugins install .` to see a complete working plugin. Every other plugin needs real user-supplied files.

## Install, Upgrade, Uninstall

All three commands mutate the Python environment; run them in the environment that owns `firecube` and check the environment path they print.

| Task | Command | Notes |
| --- | --- | --- |
| Editable dev install | `firecube plugins install --editable <workdir>/firecube-<plugin-name>` | Wraps `uv pip install`; ends with `Detected plugins: <plugin_name>` from a fresh process. Code edits apply immediately; entry-point or dependency edits need a re-install. |
| Install a release | `firecube plugins install <distribution-name>`, a wheel/sdist path, or `git+https://<host>/<org>/<repo>.git` | Same specifiers as `uv pip install`; ends with `Detected plugins: <plugin_name>` |
| Upgrade | Re-run `plugins install` with the new version, path, or git ref | No dedicated upgrade command |
| Verify | `firecube plugins list` (`-f json` gives a list of IDs), `plugins describe <plugin_name>`, `ingest <plugin_name> --show-options` | `plugins list` prints IDs only in the table; the help text's module path and description columns are not shown |
| Uninstall | `firecube plugins uninstall <plugin_name>` or `--dist <distribution-name>` | Resolves the ID to its distribution; `plugins list` then prints `No plugins registered.` |

Inside the project, `uv run firecube plugins install --editable .` installs into the project's own `.venv`; without `uv run` it installs into whichever environment `firecube` resolves from. Mixing the two is the usual cause of "plugin imports but is not listed".

## Packaging Contract

| Requirement | Detail |
| --- | --- |
| Entry point | `[project.entry-points."firecube.plugins"] <plugin_name> = "firecube_<plugin_name>"`; the module must import the decorated class |
| Same name everywhere | Entry-point key == `@register_ingestor("<plugin_name>")`; a mismatch imports but breaks distribution metadata |
| Class declarations | Non-empty `PRODUCT_NAME`; `PluginConfig` subclass only when typed options are needed |
| Imports | Only `firecube.ingestor.api`, `firecube.core.api`, `firecube.ingestor.extensions`; no `_`-prefixed Firecube method or attribute, no `run()` override (plugin-traps.md) |
| Dependency | `firecube==<version>` (pinned to the tested release) plus the source-format reader library |
| Before publishing | `uv run pytest`, `uv run ruff check`, `uv run pyright`, one local ingestion on representative input, then `uv build` |

Guide: https://eumetsat.github.io/firecube/latest/guides/plugins/contract/ . Example repository: https://github.com/eumetsat/firecube-quickstart-plugin .

## Parallelism And Concurrency

See [parallelism.md](parallelism.md): the five parallelism models, the write domain each owns, what the engine runs in worker threads and under the write lock, plugin state rules, staged versus direct write modes, and the slot-range procedure for `DirectZarrIngestor`.

## Related References

plugin-traps.md (hook contract, resume, layout rules, authoring traps), templates.md (per-template contracts and skeletons), parallelism.md (parallelism models, plugin state, write modes), benchmarks.md (reproducible measurement), install.md (environment setup), cli-surface.md (command tree and safety classes), configuration-storage.md (`[plugins.<plugin_name>]` defaults, storage drivers), ingestion.md (running an installed plugin), zarr-parquet-archive.md (output layout and validation), chunks-catalog.md (control-plane records written by test runs), performance.md (batch size and parallel fan-out), troubleshooting.md (plugin not found, zero-count discovery, schema drift).
