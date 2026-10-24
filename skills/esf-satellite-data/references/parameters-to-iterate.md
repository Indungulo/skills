# What to ask, and what to assume

Ask about one thing at a time, and only about what changes the outcome. A request that is already specific enough should not be interrogated.

## The parameters

| Parameter | Ask when | Sensible default |
|---|---|---|
| Feature type | The user's words do not map cleanly to one type in `list_feature_types` | Ask; showing the list is better than guessing |
| Classification property and bins | Always, after profiling | Propose from the profile; never assume |
| Region | Events span basins, or the user named a place | Global; report which imager covers what |
| Period | Not given, or it crosses an instrument boundary | Ask; it drives both cost and which imagery exists |
| Events per class | Not given | 20 for exploration, more for training data |
| Window around each event | Not given | Match the event's lifetime: ±3 hours for slow synoptic-scale features, ±1 hour for short-lived ones |
| Cadence | The volume is large | The collection's native cadence |
| Collection | Always, via `recommend_collections` | Never assume; ask what the data is for |
| Output format | **Always** | Ask; never assume. With the collection it decides the whole route - see rule 13 - and whether the format asked for is possible at all |
| Destination | Before generating anything, and always for a conversion | Ask; never invent a path. Ask **which kind** too - a bucket or a local path - since a bucket at both ends means nothing is staged here at all |
| Local disk ceiling | Whenever files have to land locally | Ask, and default to a rolling archive sized to free space rather than to the dataset |
| Budget | The estimate is large | Ask before proposing something expensive |

## Matching a request to a feature type

There is no mapping table here, and there should not be one: the database's types change, and a table
written down is wrong as soon as one is added or renamed. Do it live, every time.

1. Call `list_feature_types`. Read the names, descriptions and tags, not just the names - a name
   rarely says which instrument detected the features, over what region, or in what representation.
2. Shortlist everything that could be what the user meant. Phenomena routinely appear under more than
   one type.
3. If exactly one candidate fits, say which you chose and why, then continue.
4. If more than one fits, show them with their counts, periods and sources, say how they differ and
   which you would use, and ask. See
   [workflow.md](workflow.md#2a-feature-types-that-are-easy-to-confuse).
5. If nothing fits, say so and show what exists rather than substituting something close.

Whatever the type, check what it actually carries before promising anything:
`describe_feature_type` reports its properties, its identity key candidates, and whether it has
anything that could express intensity.

## Things worth raising unprompted

- **MTG FCI only exists from 2024.** Any request combining FCI with a long historical record has to give something up.
- **Feature coverage is not imagery coverage.** Some feature records reach back a century or more before any satellite; geostationary imagery starts in 1981. Compare the type's first observation time from `list_feature_types` against the imagery, and say where the real limit is.
- **Some feature types have no intensity and no track identity.** Those cannot be classified by severity or deduplicated into events server-side. `describe_feature_type` shows it: no `identityKeyCandidates`, and nothing that reads as an intensity. Say so before the user builds a plan around it.
- **Feature density is very uneven in time.** One type can hold a few hundred thousand rows in one year and tens of millions in another, with nothing in between. A window that worked for one year may be refused for the next, so check the profile rather than assuming the budget scales with the span.
- **Asking for a different format may not be possible at all.** Most of these collections sit in open buckets that can be read where they lie, but only in the format they are already stored in, and rule 13 splits what happens next. NetCDF out of a Zarr store is offered: the store is sliced and the result written, which costs time rather than being refused. GeoTIFFs out of a NetCDF archive are not: unless firecube covers the product and Zarr is what was asked for, the answer is that the files come down as they are. Raise this early - the user may be assuming a conversion that is neither free nor on the table.
- **A dataset going to S3 usually needs no local disk at all.** If the source is a bucket too, the
  objects are copied straight across - server-side within one service, streamed through memory between
  two - so a user worrying about scratch space for 40 TB may not need any. Say so early; it changes what
  machine they think they need.
- **Where local files are unavoidable, only a batch of them exists at a time.** The Data Store route and
  any conversion write locally, but a rolling archive ships and deletes as it goes. Tell the user the
  ceiling and the batch size, so they are not expecting to find the whole dataset in that directory
  afterwards.
- **A geostationary satellite sees one disc.** Events on the far side of the globe need a different satellite, not a different query.
