# Reading a Zarr store around events

The concrete counterpart to [streaming-and-stac.md](streaming-and-stac.md), for the case where the
plan says `stream` and the item's asset is a `store` rather than a `data` file. There is nothing to
list and nothing to download: the store is opened once, and each event's window and area is sliced out
of it. What crosses the network is the chunks those slices touch, which for a storm-sized box over a
few hours is a few megabytes out of a petabyte-scale array.

Use it whenever an item carries `esf:storeFormat` and the output format asked for is the store's own.
Wanted in another format, the same slicing is the first half of a conversion you write - not a
download script. That is the one conversion this skill writes: out of a store, never into one from
per-file data.

**Nothing in the script is specific to one store.** It reads the grid, the time axis and the variable
list out of the store's own metadata: a discrete global grid is sliced by cell index, a lat/lon grid
by coordinate, and a store shaped like neither is reported rather than guessed at. GeoRing is the only
store in the catalogue today, and is what the worked numbers below come from, but adding another means
adding a catalogue entry, not editing this.

## Environment, with uv

The stack is `xarray` + `zarr` + `s3fs`, plus `healpy` for stores on a discrete global grid and
`netcdf4` to write the extracts. [uv](https://docs.astral.sh/uv/) is the quickest way to get it, and
needs no preinstalled Python.

If uv is not already installed, see the [uv installation docs](https://docs.astral.sh/uv/getting-started/installation/) for the current method for the user's platform.

**Nothing to install: run the script directly.** The dependency block at the top of the template is
PEP 723 inline metadata, and `uv run` builds a cached environment from it on the first run and reuses
it after.

```bash
uv run read_store_subsets.py --dry-run
```

**As a project**, when the analysis grows past one file:

```bash
uv init esf-subsets && cd esf-subsets
uv add "xarray>=2025.1" "zarr>=3.0" "s3fs>=2024.6" "healpy>=1.17" "netcdf4>=1.6" "numpy>=2.0"
uv run python read_store_subsets.py --dest ./subsets
```

**For a notebook**, add `jupyterlab` and `matplotlib` and launch through uv, so the kernel is the same
environment:

```bash
uv add jupyterlab matplotlib
uv run jupyter lab
```

`zarr>=3` is not optional for GeoRing: the store is Zarr v3 and its arrays are sharded, and it is the
sharding that makes a small spatial slice cheap. `healpy` is needed only for a store whose grid is
HEALPix; a store with plain `lat`/`lon` coordinates is sliced with `.sel()` and needs none of it.

## First: list what is in it

**Never name a variable, channel, band or dimension from memory.** Those names belong to the store,
not to the instrument: the same 11-micron window band is `temp_11_00um` here and `bt_11`, `IR_108` or
`channel_9` in the next store along. A guessed name fails at read time, and where it collides with
something real it quietly returns the wrong field instead.

```bash
uv run read_store_subsets.py --list
```

It opens the store lazily and prints the variables with their dtypes, dimensions, units, nicknames,
wavelengths and flag meanings, plus the time axis and its step. It reads no data, so it costs one
metadata fetch. On GeoRing:

```
store   s3://level1g/zarr
grid    healpix nside 1024, nested
time    `time` 1402560 steps, 1970-01-01T00:00:00 .. 2049-12-31T23:30:00, step 30 min
        the axis can be longer than the data written to it; a window outside the populated part reads as all-missing
extra   {'layer': 3} - every one of these multiplies the read

variables (28):
  refl_00_47um               float64    ('time', 'layer', 'healpix_index') %      Blue 0.47 um
  ...
  sensor_flag                uint16     ('time', 'layer', 'healpix_index')
                             flags: MISSING ABI_GOES_16 ABI_GOES_17 ... FCI_METEOSAT_12
  temp_11_00um               float64    ('time', 'layer', 'healpix_index') K      IR Longwave Window Band 11.0 um
```

Read three things off it before writing anything:

- **Which parameters exist**, and what they are. The nickname and wavelength are what let a user
  choose; quote the list to them rather than picking channels on their behalf.
- **What the extra dimensions are.** `layer` is not a formality - it triples every read here, and its
  meaning is in `sensor_flag`'s attributes and nowhere else.
- **How long the time axis is.** It is not the same as how much of it holds data.

Then pass the chosen names as `--vars`. An unknown name is refused with the store's own list rather
than half-read.

## What the store looks like

Read this from the store rather than trusting it. GeoRing (`level1g`) at the time of writing:

| | |
|---|---|
| Store root | `s3://level1g/zarr`, endpoint `https://s3.waw3-1.cloudferro.com`, anonymous |
| Bucket | `level1g` — the store is a prefix inside it, which the catalogue records as `esf:storePath` |
| Format | Zarr v3, consolidated metadata, sharded chunks |
| Dimensions | `time` 1,402,560 × `layer` 3 × `healpix_index` 12,582,912 |
| Grid | HEALPix level 10 (nside 1024), nested, per the `dggs` root attribute |
| Chunks | one inner chunk is `(1, 1, 1048576)` — a twelfth of the globe for one step and one layer |
| Cadence | 30 minutes, from the `time` array's `scale_factor` |
| Variables | 27 3-D fields: `temp_*` brightness temperatures, `refl_*` reflectances, view and solar angles, `sensor_flag`, `pixel_time` |
| Dtypes | `int16` with `scale_factor`/`add_offset`; xarray decodes them to `float64`, four times the stored size |

Several things about it are not obvious and are worth checking before relying on an assumption:

- **The time axis is far longer than the data.** It runs 1970 to 2049 at 30-minute steps because it is
  allocated, not filled. A window outside the populated span returns the right shape full of NaN
  rather than an error, so a run can look successful and contain nothing. The template reports
  `read but all missing` for that. Populated steps were 2019-01-01 to 2024-12-31 when this was
  written, which is shorter than the catalogue's stated extent — check rather than assume.
- **There are no `lat`/`lon` coordinates.** Position lives in the HEALPix cell index, described by the
  `dggs` root attribute (the [DGGS Zarr convention](https://github.com/zarr-conventions/dggs)).
  `.sel(lat=..., lon=...)` does not work; cells have to be selected by index and the positions
  attached afterwards with `pix2ang`.
- **The store root is not the bucket root.** The Zarr metadata is at `s3://level1g/zarr`, and
  `s3://level1g` holds nothing but that one prefix. The catalogue records the difference as
  `esf:storePath`, and the `store` asset's `href` is already the store root, with the bucket kept
  separately as `esf:bucket` for listings and throughput probes. Where an `href` holds no store
  metadata directly, `open_store` looks one level down rather than failing on it.
- **`layer` is up to three overlapping satellite views of the same cell**, not a vertical axis.
  `sensor_flag` names the satellite per layer (`flag_meanings` decodes it). Layer 0 is the
  nearest-nadir view and is the one populated everywhere; layers 1 and 2 are alternate views and are
  frequently all-NaN, and their `sensor_flag` can name a satellite that contributed no radiance. Take
  layer 0 unless the study is about parallax or inter-satellite differences.

## The template

```python
#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "xarray>=2025.1",
#     "zarr>=3.0",
#     "s3fs>=2024.6",
#     "healpy>=1.17",
#     "netcdf4>=1.6",
#     "numpy>=2.0",
# ]
# ///
"""
Read subsets of a chunked array store around selected events, without copying it.

Reads access-plan.json (the STAC catalogue from plan_data_access) and events.json
(from select_balanced_events). For every item whose asset is a `store`, it opens
the store lazily, and for each event reads only the time steps inside that
event's window and only the grid cells inside its area of interest. Nothing else
crosses the network.

One netCDF per event plus a manifest, so a dataset that was never downloaded in
full is still traceable back to the query that produced it.

Nothing here is specific to one store. The grid, the time axis and the variables
are read from the store's own metadata: a discrete global grid is sliced by cell
index, a lat/lon grid by coordinate, and a store shaped like neither is reported
rather than guessed at.

Anonymous throughout: these buckets need no credentials, though GeoRing is reachable only from
inside the EWC, and signing must be off.

    uv run read_store_subsets.py --dry-run
    uv run read_store_subsets.py --dest ./subsets --radius-km 200

Requires no install: the dependency block above is PEP 723 metadata and uv
builds the environment on the first run.
"""

import argparse
import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import xarray as xr

MANIFEST_FIELDS = [
    "file", "collection", "store_format", "store_root", "feature_id", "event_id",
    "class", "ref_time", "window_start", "window_end", "lon", "lat", "area",
    "cells", "time_steps", "variables", "size_bytes", "status", "dest_uri",
]

# Store formats this script knows how to open. A catalogue entry naming
# anything else is reported rather than opened: the slicing below assumes a
# chunked array store, and forcing another layout through it would fail
# somewhere less obvious than here.
OPENERS = {"zarr"}

# Degrees of latitude per kilometre, for turning a radius into an angle.
KM_PER_DEGREE = 111.195


def anonymous_storage_options(endpoint):
    """
    fsspec options that send no identity at all.

    Two things here are not optional. Signing must be switched off explicitly:
    with AWS credentials in the environment the client signs by default, and a
    public bucket answers 403 because it cannot place that identity. And
    addressing must be path style, because several of these bucket names
    contain dots and a virtual-host URL built from one fails certificate
    validation.
    """
    options = {"anon": True, "config_kwargs": {"s3": {"addressing_style": "path"}}}
    if endpoint:
        options["client_kwargs"] = {"endpoint_url": endpoint}
    return options


def open_store(asset):
    """
    Open a store lazily and return the dataset and the root it was found at.

    `chunks=None` is deliberate and is the single most important line here.
    Without dask, xarray hands the whole selection to Zarr in one call and the
    sharding codec fetches only the byte ranges it covers. With dask the same
    read pulls whole inner chunks for every step and layer: measured against
    GeoRing, a three-hour window over an 8-degree box took 0.7 s and 300 MB
    without dask and 37 s and 10 GB with it.

    `consolidated` is left unset so xarray uses consolidated metadata when the
    store has it and falls back when it does not, which is what a catalogue of
    stores written by different producers needs.

    The href is the store root, which is not always the bucket root. Recent
    catalogue entries say which with esf:storePath and the href already accounts
    for it; an older plan may still point at the bucket, so an href holding no
    store metadata is searched one level down rather than failing.
    """
    import s3fs

    fmt = asset.get("esf:storeFormat", "").lower()
    if fmt not in OPENERS:
        raise SystemExit(f"store format {fmt or 'unrecorded'!r} is not one this script opens "
                         f"({', '.join(sorted(OPENERS))}); check esf:storeFormat on the item")

    options = anonymous_storage_options(asset.get("esf:endpoint"))
    fs = s3fs.S3FileSystem(**options)
    root = asset["href"].removeprefix("s3://").rstrip("/")

    if not _is_store_root(fs, root):
        found = [p for p in fs.ls(root, detail=False) if _is_store_root(fs, p)]
        if len(found) != 1:
            raise SystemExit(f"no single Zarr root at or below s3://{root}; "
                             f"candidates: {found or 'none'}. Check esf:storePath on the "
                             "collection.")
        root = found[0]

    return xr.open_zarr(f"s3://{root}", storage_options=options, chunks=None), root


def _is_store_root(fs, path):
    """Zarr v3 writes zarr.json at the root; v2 writes .zmetadata when consolidated."""
    return any(fs.exists(f"{path.rstrip('/')}/{name}")
               for name in ("zarr.json", ".zmetadata", ".zgroup"))


def time_dim(ds):
    """
    Find the time axis by dtype rather than by name.

    Every store here has one, but they do not all call it `time`, and picking
    the wrong coordinate would silently select the wrong data instead of
    failing.
    """
    for name, coord in ds.coords.items():
        if coord.ndim == 1 and np.issubdtype(coord.dtype, np.datetime64):
            return str(name)
    raise SystemExit("the store has no one-dimensional datetime coordinate, so an event "
                     "window cannot be selected from it")


class HealpixGrid:
    """
    A discrete global grid, addressed by cell index rather than by position.

    GeoRing is one: it carries the DGGS Zarr convention in its root attributes
    and has no lat/lon coordinates at all, so an area of interest has to become
    a list of cells and the positions are attached afterwards. The parameters
    come from the store, never from this file - guessing the resolution or the
    indexing scheme selects the wrong cells and says nothing about it.
    """

    def __init__(self, dggs):
        import healpy

        self.hp = healpy
        self.nside = 2 ** dggs["refinement_level"]
        self.nest = dggs.get("indexing_scheme", "nested") == "nested"
        self.dim = dggs.get("spatial_dimension", "cell_ids")

    def describe(self):
        return f"healpix nside {self.nside}, {'nested' if self.nest else 'ring'}"

    def disc(self, lon, lat, radius_km):
        """Cells within radius_km of a point, which is what an event centre gives you."""
        vec = self.hp.ang2vec(lon, lat, lonlat=True)
        return np.sort(self.hp.query_disc(self.nside, vec, np.radians(radius_km / KM_PER_DEGREE),
                                          inclusive=True, nest=self.nest))

    def bbox(self, west, south, east, north):
        """
        Cells inside a lon/lat box.

        Done as a latitude strip filtered by longitude rather than with
        query_polygon: polygon edges are great circles, so a box wider than a
        few degrees bulges past the latitudes asked for, and healpy rejects a
        densified outline as a degenerate corner. The strip is exact and costs
        one pix2ang over the band. A box crossing the antimeridian is written
        with west > east.
        """
        cells = self.hp.query_strip(self.nside, np.radians(90 - north), np.radians(90 - south),
                                    inclusive=True, nest=self.nest)
        lon, lat = self.positions(cells)
        inside = (lon >= west) & (lon <= east) if west <= east else (lon >= west) | (lon <= east)
        return np.sort(cells[inside & (lat >= south) & (lat <= north)])

    def positions(self, cells):
        lon, lat = self.hp.pix2ang(self.nside, cells, nest=self.nest, lonlat=True)
        return (lon + 180) % 360 - 180, lat

    def select(self, ds, event, radius_km):
        """
        Return the subset selector and a description of the area it covers.

        `query_disc`/`query_strip` return cell indices, which are positions on
        a full, contiguous sphere - not every store covers every cell that
        way. Where the dimension carries a real coordinate of cell-id values,
        `.sel` matches by that value; `.isel` would instead treat the index
        as a position and silently select the wrong cells on a store that
        omits some. Fall back to `.isel` only when there is no such
        coordinate to select by.
        """
        box = event_bbox(event)
        if box:
            cells, area = self.bbox(*box), f"bbox {box}"
        else:
            cells = self.disc(event["lon"], event["lat"], radius_km)
            area = f"disc {radius_km:g} km"
        if cells.size == 0:
            return None, area, 0
        if self.dim in ds.coords:
            subset = ds.sel({self.dim: cells})
        else:
            subset = ds.isel({self.dim: cells})
        return subset, area, int(cells.size)

    def attach_positions(self, subset):
        """The store gives cell indices, not positions; without these it cannot be plotted."""
        lon, lat = self.positions(subset[self.dim].values)
        return subset.assign_coords({"lon": (self.dim, lon), "lat": (self.dim, lat)})


class LatLonGrid:
    """
    An ordinary gridded store, addressed by coordinate.

    Latitude is sliced in whichever direction the store stores it, because
    `.sel` with a slice running the wrong way returns nothing at all rather
    than raising.
    """

    def __init__(self, ds, lat_name, lon_name):
        self.lat, self.lon = lat_name, lon_name
        self.descending = bool(ds[lat_name][0] > ds[lat_name][-1])
        self.lon_0_360 = bool(ds[lon_name].max() > 180)

    def describe(self):
        return f"lat/lon grid on {self.lat}/{self.lon}"

    def select(self, ds, event, radius_km):
        box = event_bbox(event) or self._disc_box(event, radius_km)
        west, south, east, north = box
        if self.lon_0_360:
            west, east = west % 360, east % 360
        lats = slice(north, south) if self.descending else slice(south, north)

        if west <= east:
            subset = ds.sel({self.lat: lats, self.lon: slice(west, east)})
        else:
            # An antimeridian box is two slices; a single one would run
            # backwards and select nothing.
            subset = xr.concat([ds.sel({self.lat: lats, self.lon: slice(west, None)}),
                                ds.sel({self.lat: lats, self.lon: slice(None, east)})],
                               dim=self.lon)
        cells = subset.sizes[self.lat] * subset.sizes[self.lon]
        return (subset if cells else None), f"bbox {[round(v, 3) for v in box]}", cells

    def _disc_box(self, event, radius_km):
        """A radius around a point, as the box that contains it."""
        half_lat = radius_km / KM_PER_DEGREE
        half_lon = half_lat / max(np.cos(np.radians(event["lat"])), 0.01)
        return (event["lon"] - half_lon, event["lat"] - half_lat,
                event["lon"] + half_lon, event["lat"] + half_lat)

    def attach_positions(self, subset):
        return subset


def _is_geographic(coord, units, std_name):
    """
    True only when the coordinate is actually marked as degrees latitude or
    longitude, by CF `standard_name` or by `units`.

    `y`/`x` are common projected-coordinate names too - metres on some grid,
    not degrees - so a name match alone is not enough evidence. Trusting the
    name for those would slice the wrong grid silently, which is worse than
    refusing to open it.
    """
    name = str(coord.attrs.get("standard_name", "")).lower()
    units_value = str(coord.attrs.get("units", "")).lower()
    return name == std_name or units_value in units


def grid_of(ds):
    """
    Work out how this store is addressed in space, from the store itself.

    A DGGS store says so in its root attributes; anything with recognisable
    latitude and longitude coordinates is an ordinary grid, provided their
    `units` or `standard_name` actually say so. A store that is neither, or
    whose coordinates cannot be confirmed geographic, is reported rather than
    guessed at, because every wrong guess here returns data from the wrong
    place instead of an error.
    """
    dggs = ds.attrs.get("dggs")
    if isinstance(dggs, str):
        dggs = json.loads(dggs)
    if isinstance(dggs, dict) and dggs.get("name") == "healpix":
        return HealpixGrid(dggs)

    names = {str(name).lower(): str(name) for name in ds.coords}
    lat = next((names[n] for n in ("lat", "latitude", "y") if n in names), None)
    lon = next((names[n] for n in ("lon", "longitude", "x") if n in names), None)
    if lat and lon and ds[lat].ndim == 1 and ds[lon].ndim == 1:
        lat_ok = _is_geographic(ds[lat], ("degrees_north", "degree_north", "degrees", "degree"),
                                "latitude")
        lon_ok = _is_geographic(ds[lon], ("degrees_east", "degree_east", "degrees", "degree"),
                                "longitude")
        if not (lat_ok and lon_ok):
            raise SystemExit(
                f"{lat!r}/{lon!r} are not marked as degrees latitude/longitude (no matching "
                "units or CF standard_name); this may be a projected grid this script cannot "
                "safely slice by lon/lat. Check the store's coordinate attributes."
            )
        return LatLonGrid(ds, lat, lon)
    return None


def event_bbox(event):
    """The event's own box, if it has one with area. A point bbox is not a box."""
    box = event.get("bbox")
    if box and len(box) == 4 and box[0] != box[2] and box[1] != box[3]:
        return tuple(float(v) for v in box)
    if event.get("lon") is None or event.get("lat") is None:
        raise SystemExit(f"event {event['eventId']} has neither a bbox nor a position")
    return None


def parse_time(value):
    """
    RFC3339 in, numpy datetime64 out.

    The store's time coordinate is tz-naive UTC, as netCDF and Zarr time axes
    always are, and comparing it against a tz-aware datetime raises rather than
    converting. So the offset is applied and then dropped.
    """
    moment = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return np.datetime64(moment.astimezone(timezone.utc).replace(tzinfo=None), "ns")


def window_of(event):
    """The event's window, falling back to the reference time alone."""
    return (parse_time(event.get("windowStart") or event["refTime"]),
            parse_time(event.get("windowEnd") or event["refTime"]))


def read_event(ds, grid, tdim, event, variables, args):
    """
    Read one event's window and area.

    Everything before `.load()` is lazy; the load is the only network read, and
    it touches only the chunks the selection covers. A dry run stops short of
    it, so it costs nothing beyond the metadata already read at open time.
    """
    start, end = window_of(event)
    selected = ds[variables].sel({tdim: slice(start, end)})
    if args.layer is not None and "layer" in selected.dims:
        selected = selected.isel(layer=args.layer)

    subset, area, cells = grid.select(selected, event, args.radius_km)
    steps = 0 if subset is None else subset.sizes[tdim]
    if subset is None or steps == 0:
        return None, area, cells, steps, 0

    estimate = sum(int(np.prod(subset[name].shape)) * subset[name].dtype.itemsize
                   for name in variables)
    if estimate > args.max_bytes:
        raise SystemExit(
            f"event {event['eventId']} would load {estimate / 1e9:.1f} GB at once, over the "
            f"{args.max_bytes / 1e9:.1f} GB limit. Narrow the window or the area, cut --vars, "
            "pass --layer 0, or raise --max-bytes."
        )
    if args.dry_run:
        return None, area, cells, steps, estimate

    return grid.attach_positions(subset.load()), area, cells, steps, estimate


def write_subset(subset, event, path):
    """
    Write one event to netCDF.

    Two things have to be undone first. The root attributes can hold nested
    objects - the DGGS description, a convention list - which netCDF cannot
    represent, so they are flattened to JSON rather than dropped: they are what
    says which grid the cell indices belong to. And the variables still carry
    the source store's encoding, whose scale_factor would be applied a second
    time on write.
    """
    subset = subset.copy()
    subset.attrs = {
        key: value if isinstance(value, (str, int, float, np.number)) else json.dumps(value)
        for key, value in subset.attrs.items()
    }
    subset.attrs.update({
        "esf_event_id": event["eventId"],
        "esf_feature_id": str(event.get("featureId", "")),
        "esf_class": str(event.get("class", "")),
        "esf_reference_time": event["refTime"],
    })
    for variable in subset.variables.values():
        variable.encoding.clear()

    path.parent.mkdir(parents=True, exist_ok=True)
    subset.to_netcdf(path)


def choose_variables(ds, grid, requested):
    """
    Every variable that is actually gridded, unless the caller named some.

    A store carries scalars, per-step metadata and cell indices alongside the
    fields; taking all of `data_vars` would drag those through the selection
    and the size estimate.
    """
    if requested:
        names = [name.strip() for name in requested.split(",") if name.strip()]
        missing = [name for name in names if name not in ds.variables]
        if missing:
            raise SystemExit(f"{', '.join(missing)} not in the store; it has "
                             f"{', '.join(sorted(map(str, ds.data_vars)))}")
        return names
    spatial = grid.dim if isinstance(grid, HealpixGrid) else grid.lat
    return [str(name) for name, da in ds.data_vars.items() if spatial in da.dims]


def describe_store(ds, grid, tdim, root):
    """
    Print what the store actually holds, and read no data doing it.

    Run this before naming a single variable in any script. Channel and
    parameter names are a property of the store, not of the instrument: the same
    11-micron window band is `temp_11_00um` in one store, `bt_11` or `IR_108` or
    `channel_9` in the next. A name taken from memory or from a product guide
    either fails at read time or, where it happens to collide with something
    real, quietly returns the wrong field.

    The dimensions matter as much as the names. An extra axis such as `layer` is
    not a formality - it multiplies the read, and its meaning is in the store's
    attributes rather than anywhere else.
    """
    print(f"store   s3://{root}")
    print(f"grid    {grid.describe()}")

    times = ds[tdim]
    step = ""
    if times.size > 1:
        minutes = (times[1] - times[0]).values / np.timedelta64(1, "m")
        step = f", step {minutes:g} min"
    print(f"time    `{tdim}` {times.size} steps, {times.values[0]} .. {times.values[-1]}{step}")
    print("        the axis can be longer than the data written to it; a window outside the "
          "populated part reads as all-missing")

    extra = {d: ds.sizes[d] for d in ds.dims if d != tdim and d != _spatial_dim(grid)}
    if extra:
        print(f"extra   {extra} - every one of these multiplies the read")

    print(f"\nvariables ({len(ds.data_vars)}):")
    for name, da in sorted(ds.data_vars.items()):
        units = da.attrs.get("units", "")
        nick = da.attrs.get("nickname") or da.attrs.get("standard_name", "")
        wl = da.attrs.get("central_wavelength_um")
        label = " ".join(str(x) for x in (nick, f"{wl} um" if wl else "") if x)
        print(f"  {str(name):<26} {str(da.dtype):<10} {str(tuple(da.dims)):<34} "
              f"{units:<6} {label}")
        if "flag_meanings" in da.attrs:
            print(f"  {'':<26} flags: {da.attrs['flag_meanings']}")


def _spatial_dim(grid):
    return grid.dim if isinstance(grid, HealpixGrid) else grid.lat


def parse_s3_uri(uri):
    bucket, _, prefix = uri.removeprefix("s3://").partition("/")
    return bucket, prefix.strip("/")


def ship_extract(path, row, bucket, prefix, endpoint):
    """
    Upload one extract to its real destination and remove the local copy.

    Reads `row["size_bytes"]`, already set from `path.stat()` when the row was
    built, rather than statting the file again here - by the time an upload is
    confirmed and the file is unlinked below, a second `path.stat()` would
    raise instead of reading 0. Nothing is deleted until the destination's own
    view of the object, from `info`, matches that size.
    """
    import s3fs

    fs = s3fs.S3FileSystem(anon=False, client_kwargs={"endpoint_url": endpoint} if endpoint else {})
    key = f"{prefix}/{path.name}".strip("/")
    fs.put(str(path), f"{bucket}/{key}")
    if fs.info(f"{bucket}/{key}")["size"] != row["size_bytes"]:
        row["status"] = "size mismatch at destination"
        return
    row["dest_uri"] = f"s3://{bucket}/{key}"
    path.unlink()


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--catalog", default="access-plan.json",
                        help="STAC catalogue from plan_data_access")
    parser.add_argument("--events", default="events.json",
                        help="events array from select_balanced_events")
    parser.add_argument("--dest", default="subsets", help="where to write the extracts")
    parser.add_argument("--vars", default="",
                        help="comma-separated variables; default is every gridded variable")
    parser.add_argument("--radius-km", type=float, default=200.0,
                        help="radius around an event with no bbox (default 200)")
    parser.add_argument("--layer", type=int, default=None,
                        help="for a store with a `layer` dimension, keep one layer; on GeoRing "
                             "0 is the nearest-nadir view and the only one populated everywhere")
    parser.add_argument("--max-bytes", type=float, default=4e9,
                        help="refuse a single event larger than this in memory (default 4 GB)")
    parser.add_argument("--dry-run", action="store_true",
                        help="report cells, steps and size without reading any data")
    parser.add_argument("--list", action="store_true",
                        help="print the store's variables, dimensions and time axis, then stop; "
                             "run this before naming any variable in a script")
    parser.add_argument("--s3-dest",
                        help="s3://bucket/prefix to ship each extract to as it is written, instead "
                             "of leaving it under --dest")
    parser.add_argument("--dst-endpoint",
                        help="endpoint for --s3-dest when it is not AWS")
    args = parser.parse_args()

    dst_bucket = dst_prefix = None
    if args.s3_dest:
        dst_bucket, dst_prefix = parse_s3_uri(args.s3_dest)

    catalog = json.loads(Path(args.catalog).read_text())
    # --list describes the store itself, so it needs no event selection.
    events = []
    if not args.list:
        events = json.loads(Path(args.events).read_text())
        if isinstance(events, dict):
            events = events["events"]
    dest = Path(args.dest)

    stores = [item for item in catalog.get("items", []) if "store" in item.get("assets", {})]
    if not stores:
        raise SystemExit(f"{args.catalog} has no item with a `store` asset; nothing to read "
                         "in place here. Per-file collections are listed and opened "
                         "differently - see streaming-and-stac.md.")

    rows = []
    for item in stores:
        asset = item["assets"]["store"]
        collection = item.get("collection", item["id"])
        ds, root = open_store(asset)
        grid = grid_of(ds)
        if grid is None:
            raise SystemExit(f"{collection} has neither a DGGS description nor lat/lon "
                             f"coordinates, so this script cannot tell where its cells are. "
                             f"Its coordinates are: {', '.join(map(str, ds.coords))}")
        tdim = time_dim(ds)
        if args.list:
            describe_store(ds, grid, tdim, root)
            continue
        variables = choose_variables(ds, grid, args.vars)
        covered = (f"{item['properties'].get('start_datetime')} .. "
                   f"{item['properties'].get('end_datetime')}")
        print(f"{collection}: s3://{root}, {grid.describe()}, time on `{tdim}`, "
              f"{len(variables)} variables, catalogue window {covered}", flush=True)

        for event in events:
            subset, area, cells, steps, estimate = read_event(ds, grid, tdim, event,
                                                              variables, args)
            path = dest / str(event.get("class", "all")) / f"{event['eventId']}-{collection}.nc"

            if args.dry_run:
                status = "would-read"
            elif subset is None:
                status = "nothing in window"
            else:
                write_subset(subset, event, path)
                status = "read but all missing" if _all_missing(subset, variables) else "ok"

            written = status in ("ok", "read but all missing")
            rows.append({
                "file": str(path) if written else "",
                "collection": collection,
                "store_format": asset.get("esf:storeFormat", ""),
                "store_root": f"s3://{root}",
                "feature_id": event.get("featureId", ""),
                "event_id": event["eventId"],
                "class": event.get("class", ""),
                "ref_time": event["refTime"],
                "window_start": event.get("windowStart", ""),
                "window_end": event.get("windowEnd", ""),
                "lon": event.get("lon"),
                "lat": event.get("lat"),
                "area": area,
                "cells": cells,
                "time_steps": steps,
                "variables": ";".join(variables),
                "size_bytes": path.stat().st_size if written else 0,
                "status": status,
                "dest_uri": "",
            })
            if args.s3_dest and written:
                ship_extract(path, rows[-1], dst_bucket, dst_prefix, args.dst_endpoint)
            print(f"  {event['eventId']:<16} {area:<34} cells={cells:>7} steps={steps:>3} "
                  f"~{estimate / 1e6:>7.1f} MB  {status}", flush=True)

    if args.list:
        return 0

    dest.mkdir(parents=True, exist_ok=True)
    with (dest / "manifest.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=MANIFEST_FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    # The catalogue is the dataset definition, so it is saved beside the
    # extracts rather than left in the conversation.
    (dest / "dataset.json").write_text(json.dumps({
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "catalog": catalog,
        "events": len(events),
        "readInPlace": True,
        "arguments": vars(args),
    }, indent=2))

    empty = [r for r in rows if r["status"] not in ("ok", "would-read")]
    print(f"\n{len(rows)} extracts, {len(empty)} with no data -> {dest}/manifest.csv")
    return 1 if empty else 0


def _all_missing(subset, variables):
    """
    Whether an extract came back empty rather than absent.

    A store's time axis can be longer than the data written to it - GeoRing's
    runs to 2049 - so a window outside the populated part returns the right
    shape full of fill values and no error at all. Without this check a run
    like that looks successful and contains nothing.

    The verdict rests on the variables that can express missing. Integer flags
    cannot, so a selection of nothing but those is reported as read.
    """
    nullable = [subset[name] for name in variables
                if np.issubdtype(subset[name].dtype, np.floating)
                or np.issubdtype(subset[name].dtype, np.datetime64)]
    return bool(nullable) and all(bool(da.isnull().all()) for da in nullable)


if __name__ == "__main__":
    sys.exit(main())
```

## Running it

`access-plan.json` is the catalogue `plan_data_access` returned; `events.json` is the `events` array
from `select_balanced_events`, unchanged. Both are saved as they came back, because together they are
what makes a dataset nobody copied still reproducible.

```bash
uv run read_store_subsets.py --list                             # what is in the store, no read
uv run read_store_subsets.py --dry-run                          # cells, steps and megabytes, no read
uv run read_store_subsets.py --dest ./subsets --layer 0         # the usual run
uv run read_store_subsets.py --dest ./subsets --radius-km 300 \
    --vars temp_11_00um,temp_06_20um,sensor_flag                # one channel set, wider disc
```

| Option | Effect |
|---|---|
| `--radius-km` | Disc around the event centre when the event carries no bbox. 200 km by default |
| `--layer` | For a store with a `layer` dimension, keep one. On GeoRing `0` is the nearest-nadir view and cuts the read by two thirds |
| `--vars` | Comma-separated variables; the default is every variable on the spatial dimension, which for GeoRing is 27 of them |
| `--max-bytes` | Refuse a single event bigger than this in memory. 4 GB by default |
| `--dry-run` | Report the selection without reading any data |
| `--list` | Print the store's variables, dimensions and time axis, then stop. Run this first; it needs no `events.json` |

An event with a `bbox` is read as that box; one with only `lon`/`lat` is read as a disc. Outputs are
one netCDF per event under `<dest>/<class>/`, plus `manifest.csv` and `dataset.json`.

**Where those extracts are going to a bucket, do not let them pile up here.** One netCDF per event is
small beside the store; a few thousand of them is not, and this directory is then a staging area rather
than the deliverable. Pass `--s3-dest s3://bucket/prefix` (and `--dst-endpoint` when it is not AWS) and
the template ships each file as it is written, confirms it arrived, and only then deletes the local
copy - the same rolling archive as the download route, one event per batch instead of one window. See
`ship_extract` in the template above: it is called right after the row is built, using the size already
read from `path.stat()`, since the file may be gone by the time anything downstream asks again.

The manifest stays local either way. It is small, and it is the thing that makes a dataset scattered
across a bucket explainable. See
[destinations-and-credentials.md](destinations-and-credentials.md), "Keeping only a rolling archive
locally".

## Why there is no dask here

`chunks=None` is the reason this is fast, and it is the opposite of the usual advice.

With `chunks=None` xarray keeps its own lazy indexing and hands the whole selection to Zarr in one
call, so the sharding codec fetches only the byte ranges the selection covers. With `chunks={}` dask
takes over and materialises whole inner chunks — one twelfth of the globe, decoded to float64 — for
every time step and layer, then does it concurrently.

Measured against `level1g` at time of writing, three hours over an 8-degree box:

| | Wall time | Peak RSS |
|---|---|---|
| `chunks=None` | **0.7 s** | **0.3 GB** |
| `chunks={}` (dask) | 37 s | 10 GB |

The same slice read straight from `zarr` with no xarray takes 0.2 s, so the lazy path is close to the
floor and dask is not paying for itself. Dask earns its place when the extract is genuinely larger
than memory; per-event windows are not, which is why the template guards with `--max-bytes` and reads
each event whole.

## When it goes wrong

- **`403` from a listing or an open.** Too much identity, not too little. `anon=True` must be set, and
  it is undone by nothing except AWS credentials leaking in through a client built elsewhere.
- **A certificate error naming a long hostname.** Virtual-host addressing on a bucket name containing
  dots. `addressing_style: path` is in `anonymous_storage_options` for this reason; keep it.
- **`GroupNotFoundError` or an empty group on the catalogue's href.** The store is under a prefix and
  the entry does not say so. Add `storePath` to it; GeoRing's store root is `s3://level1g/zarr`, not
  `s3://level1g`. `open_store` looks one level down as a fallback, which covers a plan made before the
  field existed, but the entry is what should be fixed.
- **`TypeError: Cannot compare tz-naive and tz-aware datetime-like objects`.** The store's time axis
  is naive UTC and the event times are RFC3339 with an offset. `parse_time` drops the offset after
  applying it.
- **`TypeError: Invalid value for attr 'dggs'` on write.** netCDF attributes cannot hold nested
  objects, and the DGGS description is one. `write_subset` flattens them to JSON rather than dropping
  them, since they are what says which grid the cell indices belong to.
- **`SerializationWarning: saving variable time ... as an integer dtype`.** The variables still carry
  the source store's encoding and its `scale_factor` would be applied a second time.
  `write_subset` clears it.
- **`degenerate corner` from healpy.** `query_polygon` with a densified outline. Use the latitude
  strip in `HealpixGrid.bbox`, which is exact and does not have the problem.
- **A lat/lon store returns an empty selection for a box that should have data.** Latitude stored
  descending, sliced ascending. `.sel` with a slice running against the coordinate returns nothing
  rather than raising; `LatLonGrid` checks the direction at open time.
- **`<name> not in the store` on `--vars`.** A channel name from memory or from another collection.
  Run `--list` and take the names from there; the error already prints what the store does have.
- **The extract is three times the size expected.** An extra dimension nobody looked at - `layer` on
  GeoRing. `--list` reports these under `extra`, and `--layer 0` collapses it.
- **The read returns the right shape and every value is NaN.** The window is outside the populated
  part of the time axis. Check against the store rather than the catalogue's stated extent.

## Reproducibility

Nothing was copied, so the record has to carry what a directory tree would otherwise imply. The script
writes `dataset.json` with the catalogue, the arguments and the timestamp, and `manifest.csv` with one
row per extract linking it to its feature id, event id, class, reference time, area and cell count.
Save the seed and the exact `select_balanced_events` inputs beside them, and state which store version
was read: a prototype store can be reshaped upstream, and that is the one risk a streamed dataset
carries that a downloaded one does not.
