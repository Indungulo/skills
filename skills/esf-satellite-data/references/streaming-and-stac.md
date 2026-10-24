# Reading data in place

The counterpart to [download-script-template.md](download-script-template.md). That file is for when
files are wanted on disk; this one is for the usual case, where they are not.

Most of what this server points at is an anonymous object store. When the reader sits near it — inside
the EWC for the EUMETSAT buckets, in the same AWS region for the Open Data ones — copying the data
first buys nothing and costs storage, time and a cleanup step. Reading it where it lies starts
immediately, needs no staging area, and leaves a STAC catalogue as the dataset definition instead of a
directory tree.

## Asking about the format first

Before any measurement, ask the user what format they want the output in. It decides the route, and
nothing below matters if the answer implies a conversion:

- **The format it is already stored in** (`outputFormat: "source"`, or naming that format) — reading
  in place is on the table, and the rest of this page applies.
- **Another format, out of a Zarr store** — still reading in place. Slicing the store and writing the
  result is what [zarr-store-template.md](zarr-store-template.md) already does; the conversion is the
  expensive part, not the transfer, so say so.
- **Another format, out of anything else** — not something this path does. Rule 13 decides it:
  firecube on branch 2 when Zarr is what was asked for and a plugin covers the product, and otherwise
  branch 4, where the files come down as they are and nobody crops or rewrites them. Go to
  [download-script-template.md](download-script-template.md) and tell the user plainly which of those
  two they are getting.

Collections record what they already hold as `esf:format`, and `plan_data_access` compares the two for
you, understanding aliases (`nc4` and NetCDF are the same thing; HDF5 and NetCDF are not). Where a
collection records no format the plan says so rather than assuming — confirm it before relying on the
verdict.

Do not fill `outputFormat` in yourself to make the call go through. Omitting it returns an instruction
to ask the user, which is the intended behaviour.

## Measuring second

The decision needs a number, and the number has to come from the machine that will do the reading. The
`esf` server does not measure it: these buckets are reachable only from certain networks, and read
speed is a property of the reading host, so a figure measured on the server would describe the wrong
machine. `get_throughput_probe` returns the commands instead.

```
mcp__esf__get_throughput_probe { collections: [<id>, ...] }
```

Three steps come back per collection.

1. **List the bucket** to find a real object. The server cannot name one: for most of these buckets it
   knows the key layout, not the filenames.
2. **Time one read.** Pick an object of at least 50 MB. A small object measures round-trip latency, and
   a link judged on latency looks slow even when it is not.
3. **Time several reads at once.** This is the figure to report. A real analysis reads many objects
   concurrently, and single-stream speed understates what it will actually see — often by a lot.

Ask the user to run them and report back. Then:

```
mcp__esf__plan_data_access {
  collections, events, outputFormat,
  throughput: [{ collection, megabytesPerSecond, measuredFrom }]
}
```

Never invent `megabytesPerSecond`. With no measurement the plan answers `unknown` and returns the
probes, which is the correct answer; a guessed figure produces a confident decision resting on nothing.

## What the plan returns

`perCollection` carries the mode, the measured speed, the size, the estimated single-pass time and the
reasons. `catalog` is a STAC Catalog covering the collections it decided to stream.

- **`stream`** — the catalogue is the dataset. Save it, record the seed and the exact tool inputs
  beside it, and write no download script.
- **`download`** — go to [download-script-template.md](download-script-template.md), and say which
  numbers drove the decision.
- **`unknown`** — `needs` says what is missing: `outputFormat` means go and ask the user,
  `measuredThroughput` means run the attached probes. Supply it and call again.

## Reading the catalogue

Items are one per event window, not one per file. Each item's `data` asset points at whatever the
documented key layout determines for that window:

- `esf:prefixResolved: true` — the href is a real object key.
- `esf:prefixResolved: false` — the href is the narrowest key prefix the layout fixes, and
  `esf:keyPatternRemainder` shows the part it does not. **List that prefix to get real keys.** The
  layouts in the catalogue elide filenames, so a generated filename would be a plausible dead link;
  the catalogue says which listing is owed rather than guessing.

The collection carries `esf:listCommand`, which is that listing with the prefix left as a placeholder.

```python
import json, boto3
from botocore import UNSIGNED
from botocore.config import Config

catalog = json.load(open("access-plan.json"))
collection = catalog["collections"][0]

# Path addressing is not optional: several of these bucket names contain dots,
# and a virtual-host URL built from one fails certificate validation.
s3 = boto3.client("s3", endpoint_url=collection["esf:endpoint"],
                  config=Config(signature_version=UNSIGNED,
                                s3={"addressing_style": "path"}))
bucket = collection["assets"]["root"]["href"].removeprefix("s3://").rstrip("/")

keys = []
for item in catalog["items"]:
    asset = item["assets"]["data"]
    rest = asset["href"].removeprefix(f"s3://{bucket}/")
    if asset["esf:prefixResolved"]:
        keys.append(rest)
        continue
    pages = s3.get_paginator("list_objects_v2").paginate(Bucket=bucket, Prefix=rest)
    keys += [o["Key"] for page in pages for o in page.get("Contents", [])]
```

## Opening the data

Per-file collections, with `s3fs` and `xarray`:

```python
import s3fs, xarray as xr

fs = s3fs.S3FileSystem(anon=True, client_kwargs={"endpoint_url": endpoint},
                       config_kwargs={"s3": {"addressing_style": "path"}})
ds = xr.open_mfdataset([fs.open(f"{bucket}/{k}") for k in keys], combine="nested",
                       concat_dim="time")
```

A chunked array store — an item whose asset is `store` and carries `esf:storeFormat` — has no
per-timestep objects to enumerate at all. Open it once and slice:

```python
store = catalog["items"][0]["assets"]["store"]
options = {"anon": True, "client_kwargs": {"endpoint_url": store["esf:endpoint"]},
           "config_kwargs": {"s3": {"addressing_style": "path"}}}
# chunks=None keeps xarray's own lazy indexing, which pushes the whole selection
# down to Zarr in one call. Backing it with dask instead reads whole chunks per
# step and is dramatically slower here; see zarr-store-template.md.
ds = xr.open_zarr(store["href"], storage_options=options, consolidated=True, chunks=None)
subset = ds.sel(time=slice(start, end)).isel(healpix_index=cells).load()
```

Slice before computing. The point of reading in place is that only the chunks touched by the slice
cross the network; calling `.load()` on the whole store gives up that advantage and downloads
everything the slow way.

The `href` is the store root, which is not the bucket root when the store sits under a prefix — the
collection says which with `esf:storePath`, and the asset keeps the bucket separately as `esf:bucket`
because a listing and a throughput probe are addressed to that while the store is opened at the href.

How the spatial slice is written depends on the store's grid, and it is not always `lat`/`lon`.
GeoRing has no lat/lon coordinates at all: position is a HEALPix cell index described by the store's
own `dggs` attribute, so an area of interest becomes a list of cells.
Before naming any variable in a script, list what the store holds - `read_store_subsets.py --list`
prints its variables, dimensions, units and flag meanings without reading data. Channel names belong
to the store, not to the instrument, and a name carried over from another collection fails or returns
the wrong field.

**[zarr-store-template.md](zarr-store-template.md) is the working version of this** — environment
setup with uv, event windows and areas turned into slices for either kind of grid, one netCDF per
event and a manifest, plus the failure modes each of these details produces.

## Reproducibility without a copy

A streamed dataset is reproducible on exactly the same terms as a downloaded one, provided the same
things are written down. Save alongside the catalogue:

- the seed and the exact `select_balanced_events` inputs,
- the output format asked for, and the format the data was already in,
- the measured read speed and where it was measured,
- the collection ids and the tool versions.

The catalogue plus that record reconstructs the dataset. What it does not do is protect against the
upstream changing: a bucket can be reorganised or a prototype collection reshaped. When the dataset has
to be stable for years rather than months, that is an argument for downloading, and worth saying so.

## When it goes wrong

- **403 from the probe.** Almost always too much identity, not too little — check the request is
  unsigned. If it is, check the host: the EWC buckets return 403 from the public internet.
- **A certificate error naming a long hostname.** Virtual-host addressing on a bucket name with dots.
  Set `addressing_style` to `path`.
- **`NoSuchBucket` on a name containing `<year>` or `<nn>`.** A bucket family: substitute the value.
- **The measured speed looks implausibly low.** Check the object was large enough and that the
  aggregate step, not the single-read step, was reported.
- **The plan says `download` and the speed looks fine.** Check `requestedFormat` against
  `nativeFormat`: a conversion is a download whatever the link does.
