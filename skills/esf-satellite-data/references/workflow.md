# Workflow

The gated sequence, then four worked examples.

## The sequence

Each step is a gate. Passing one without checking its output is how a dataset ends up wrong in a way nobody notices until after the download.

### 1. Understand the request

Fill in what the user gave and identify what is missing. See [parameters-to-iterate.md](parameters-to-iterate.md). Ask about one thing at a time, and only about what actually changes the outcome.

### 2. Find the feature type

```
mcp__esf__list_feature_types
```

Match the user's words to a type. If nothing matches, show them the list rather than guessing. The default hides types with fewer than 1000 features, which are almost all test artifacts; pass `includeAll` only when looking for something specific.

**If more than one type could plausibly be what they meant, stop and ask.** See below.

### 2a. Feature types that are easy to confuse

Several phenomena appear under more than one type, because they were detected by different instruments, labelled in different campaigns, or stored at different resolutions. Choosing the wrong one produces a dataset that looks fine and answers a different question.

Never resolve this silently. Show the candidates with their counts, periods and sources, say how they differ and which you would pick, then ask.

| Shape of the overlap | What differs | How to tell them apart |
|---|---|---|
| The same phenomenon from two labelling campaigns | Period, labelling convention, source | Compare first and last observation times; the period usually decides |
| The same phenomenon in two representations | One tracked per object, one gridded or summarised | Compare feature counts and the property sets from `describe_feature_type` |
| The same word for two physically different things | A regional or high-latitude variant is not a subset of the general type | Read both descriptions before assuming one contains the other |
| Surface versus upper level | Nearly identical names, a real meteorological difference | Read the descriptions; ask which level they mean |
| One phenomenon split across sub-types | Sub-classes stored separately | Ask whether they want them combined or kept apart |
| Different features from one campaign | Related but distinct, similar names and identical periods | Read the descriptions; similarity of name is not similarity of feature |
| One type, but the region decides the imagery | Events spread across basins | Filter on the type's own region property; the basin decides which imager can see them |

Take the candidates, their counts and their periods from `list_feature_types`, and their properties
from `describe_feature_type`. This skill deliberately names no feature type: they are added, renamed
and re-ingested, so anything written here would be stale before you read it.

Ask in the form: here are the candidates, this is how they differ, this is the one I would use and why, is that right? Do not make the user work out the difference themselves.

### 3. Find the identity key

```
mcp__esf__describe_feature_type { featureType, timeStart, timeEnd, sampleSize: 1000 }
```

Read three things from the output:

- `hints.identityKeyCandidates`: which property groups observations into events.
- `hints.perObservationIds`: which property looks like an id but is unique per row. Using one of these as the identity key inflates the event count by an order of magnitude.
- `properties`: fill rate, type, range, percentiles and top values, which is what a classification has to be built from.

### 4. Select the events

```
mcp__esf__select_balanced_events { featureType, timeStart, timeEnd, identityKey,
                                   perClass, seed, referenceTime: "peak", preMinutes, postMinutes }
```

**Omit `classes`.** That returns a plain deduplicated sample of `perClass` events and skips the whole
classification branch below. This is the default and covers most requests.

Always pass a seed and record it. The selection is reproducible for a given seed, which is what lets
someone else rebuild the same dataset. Read the shortfall: fewer events available than requested is
reported rather than silently returned, and it is worth knowing before download.

### 5. Only if the user asked for classes or balance

Skip this section entirely unless the request was for classes, intensities, severity levels or an even
split across them. It adds three steps and a confirmation, and it is the expensive path.

1. `describe_feature_type` to see what properties exist and what values they take. There is no severity
   column; the server does not know which property means intensity and will not guess.
2. Propose a property and the class boundaries with your reasoning, and **wait for the user to
   confirm**. A classification is a judgement that belongs to them.
3. `aggregate_features` to see how the classes actually split the data. A large `unclassified` share
   means the property or the bounds are wrong; go back rather than pressing on.
4. `select_balanced_events` again with `classes`, and an equal `perClass` if they wanted a balanced set.
   Report any class that could not supply its share instead of quietly rebalancing the others down.

### 6. Choose imagery

```
mcp__esf__recommend_collections { featureType, timeStart, timeEnd, preference }
mcp__esf__check_event_coverage { collection, events }
```

Read the gaps and the caveats. Coverage matters per event, not just per period.

### 7. Size it

```
mcp__esf__estimate_download_volume { collections, events, maxGb }
```

Report the total, the assumptions, and whether it fits.

The figure is bytes to transfer. Extracted data needs its own room, and for the Data Store's zipped
native products the unpacked size is close to the download, so quote both when the number is large.

It is a size, not an instruction to copy. Read `accessMode`: for an open bucket the bytes may not have
to move at all, which step 8 settles.

### 8. Decide whether the data has to move

```
mcp__esf__get_throughput_probe { collections }
mcp__esf__plan_data_access { collections, events, outputFormat, throughput, preferDownload }
```

**First, ask what format the output should be in.** This decides the route before speed does. Ask
the user plainly - "what format do you want the files in?" - and pass the answer as `outputFormat`.
`source` means whatever the data is already in. Never infer it from the collection id, and never fill
it in to make the call go through: the tool returns `unknown` and asks you to go and ask, which is the
correct outcome, not an error.

**Then route the dataset, per rule 13.** Take the first branch that matches, say which one you took,
and only then think about transfer.

| | Branch | What happens |
| --- | --- | --- |
| 1 | A dataset-specific skill covers this product | It handles the access half; this skill keeps the event selection. Check the skills installed in the current session. In this public bundle, `eumdac` covers Data Store downloads. |
| 2 | Zarr asked for, data is not Zarr | Check `firecube` and `firecube plugins`. A plugin covering this product is what makes it possible; no plugin, or no firecube, drops to branch 4. |
| 3 | The data is already Zarr in an open bucket | The rest of this step. Probe the throughput, `plan_data_access`, read it in place. Converting out of the store is on offer here. |
| 4 | Anything else | Download and unzip, nothing more. No crop, no regrid, no conversion, and nothing is opened. Say so before the user assumes otherwise. |

The throughput probe below matters on branch 3. On branch 4 the question is not whether to copy - the
files have to move for the user to have them - but only how much and where to.

Copying terabytes to local disk to read them once is waste when the reader sits near the bucket. The
server will not guess at this and will not measure it either: these buckets are reachable only from
certain networks, and read speed belongs to the machine doing the reading, so a figure measured on the
server would describe the wrong host.

1. Call `get_throughput_probe` for the bucket-backed collections. It returns three steps: list the
   bucket to find a real object, time one read, then time several at once.
2. Ask the user to run them **on the machine that will read the data**, and to report the aggregate
   figure from the last step. A single small read measures round-trip latency, not bandwidth, and
   deciding on it sends a fast bucket down the download path.
3. Pass those figures to `plan_data_access` as `throughput`, with the `outputFormat` from above.

When it answers `stream`, the STAC catalogue it returns **is** the dataset. Save it, note the seed and
tool inputs beside it, and skip step 9 entirely. When it answers `download`, it says which numbers it
decided on. Where it answers `unknown` it names what is missing, the format or the measurement, and hands back
the probes when the measurement is what is owed. That is the answer, so supply it rather than
assuming.

A chunked array store (`esf:storeFormat`) comes back as `stream` when its own format is what was
asked for: it has no per-timestep objects, so there is nothing to download file by file. Asked for in
another format it is a conversion you write yourself - slice the store, write the output - and no
download script applies.

Pass `preferDownload` only when the user asked for files on disk.

Then present the plan and wait for approval.

See [streaming-and-stac.md](streaming-and-stac.md) for how to read the catalogue afterwards.

### 9. Generate the download, if the plan says to

Only when `plan_data_access` said `download`, or the user asked for local copies.

See [download-script-template.md](download-script-template.md). Explain it. Run it only if asked, dry run first.

**First ask where the files are going, because the host may not be in the path at all.** A bucket
destination with a bucket source is a straight object-to-object copy: server-side where both ends are
the same S3 service, streamed through memory where they are not, and either way nothing lands on local
disk. Staging the dataset in a directory and uploading it afterwards moves every byte twice and needs
free space for the whole thing. Say which shape the transfer took.

**Where files genuinely have to land here, keep only a rolling archive.** `eumdac` writes into a
directory and a conversion has to write its output somewhere, but neither needs the whole dataset
present at once: download a batch, extract it, verify it, ship it to its real home, delete it, then
start the next. Agree the ceiling with the user, size the batch from it, check `df` before each batch,
and delete only what is confirmed to have arrived. Peak disk is what has to fit, not the total.

**Fetch in parallel.** The script uses half the host's cores by default, since transfers are I/O
bound. `--jobs` overrides it. State the worker count in the pre-download report.

**Extract as you go.** Data Store products are zip archives, and a directory of zips is not a dataset.
The script unpacks each file the moment it lands and deletes that archive once the extraction is
verified, so peak disk stays near the extracted size instead of double it. A failed extraction never
removes the archive. Bucket data is usually already unpacked, so this mostly affects the Data Store
route.

Only leave things packed if the user asks, with `--no-extract --keep-archives`, and say so in the
summary rather than letting them find out later.

## Worked examples

The four traces below are illustrations recorded when they were written, not facts about the current
database. Every type name, property name and count in them is something a live call returned once;
re-derive each from `list_feature_types` and `describe_feature_type` rather than reusing it.

### Worked example 1: balanced storm dataset

> "Give me MTG FCI data with about 100 weak, moderate, severe and extreme storms each, under 50 TB."

Two problems to raise early. MTG FCI only exists from 2024, so a hundred storms per class needs either a longer period on SEVIRI or an acceptance that FCI limits the sample. And "severity" is not a stored field.

1. `list_feature_types` → a tracked cyclone type whose record reaches back well past any imagery.
2. `describe_feature_type` over a recent year → `sid` as identity key, `usa_status` categorical with values `TS`, `TD`, `DB`, `TY`, `HU`.
3. Propose four classes from `usa_status`, note that four classes do not map cleanly onto a three-level scale, and ask whether to use wind radii (`usa_r34`, `usa_r50`, `usa_r64`) for a finer split. Wait.
4. `aggregate_features` per year, and read the yearly event count it reports: that number, not a guess, decides how many years a hundred per class needs. Loop and combine.
5. `select_balanced_events` per year with the same seed, `perClass` sized to the years covered.
6. `recommend_collections` with `preference: operational` for FCI, or `climate_record` for a longer series.
7. `check_event_coverage`, then `estimate_download_volume` with `maxGb: 51200`.

Storms are spread across basins, so plan per basin: filter on whichever basin or region property the profile shows, and pick the imager that can see each one.

### Worked example 2: deep convective systems

> "I need satellite data with deep convective systems."

Under-specified. Ask about region, period, how many, and what for.

1. `list_feature_types` → a tracked convective type. Check its distribution in time before planning a window: this one held a few hundred thousand rows in its first year and tens of millions in a later one, with nothing in between.
2. `describe_feature_type` → the identity key it reports, dozens of numeric properties, and the satellite the detections came from.
3. Propose bins on whichever size or intensity property the profile shows. Wait.
4. `aggregate_features` on one month, not one year: a dense year exceeds the row budget and is refused, while a month is affordable. The refusal names a window that fits.
5. Onwards as usual. Detections tracked from a particular imager match that imager's data natively; anything else needs reprojection.

### Worked example 3: regional forecaster dataset

> "Cases of cold fronts over Scandinavia last winter for forecaster training."

1. `list_feature_types` → the front type they mean, confirming whether the sub-types should be combined.
2. Use a bounding box for the region of interest.
3. `describe_feature_type` → for this family of types the profile shows **no intensity and no track identity**. Say so: they cannot be classified by severity or deduplicated into events server-side. Offer selection by time and region instead, or client-side clustering.
4. `query_features` with the bounding box and window, then choose cases with the user.
5. Fronts are synoptic-scale, so a merged or lower-cadence product is usually enough.

### Worked example 4: long climate record

> "Every tropical cyclone since 1980, to S3, for a climate study."

1. Establish immediately that imagery constrains this more than the features do. The feature record reaches back long before any satellite; geostationary imagery does not exist before 1981, and before 2004 it is MVIRI only, at coarser resolution with three channels.
2. `recommend_collections` with `preference: climate_record`, and report the gap table.
3. Insist on climate data records over operational archives: an operational series is not homogeneous across satellite transitions, so instrument changes look like climate trends.
4. `aggregate_features` and `select_balanced_events` per decade, same seed throughout, combining results.
5. Destination is S3, and so is the source: the objects are copied bucket to bucket and nothing is staged on this host. Check the writing credential and the target bucket before generating anything, and where a conversion has to write output first, keep only a rolling batch of it locally. See [destinations-and-credentials.md](destinations-and-credentials.md).
