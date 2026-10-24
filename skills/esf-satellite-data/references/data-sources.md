# Satellite sources

Three catalogues, presented identically through the MCP but fetched very differently.

| Source id | What it is | Product search | Credentials |
|---|---|---|---|
| `eumetsat-datastore` | Live EUMETSAT Data Store | Yes | Browsing and search are anonymous; **download needs a token** |
| `aws-open-data` | opengeos index, filtered to Earth observation | No | Anonymous, except requester-pays buckets |
| `ewc-static` | EUMETSAT cloud buckets and GeoRing | No | Anonymous S3 |

## EUMETSAT Data Store

The only source with a per-file inventory, so it is where `search_satellite_products` and real `check_event_coverage` work.

Download with the `eumdac` skill:

```bash
eumdac download -c EO:EUM:DAT:MSG:HRSEVIRI -p MSG3-SEVI-MSG15-... -o <dest>
```

Credentials live in `~/.eumdac/credentials`. Never print them.

Notes:

- **Products arrive as zip archives** (`application/zip`). Extract each one on arrival and drop the
  archive; see the extraction rule in SKILL.md.
- **`eumdac` is the one route with no bucket-to-bucket form.** It writes into a directory, so the local
  disk is unavoidable here - but only for a batch at a time. Loop over short windows, extract, ship the
  result to wherever it is really going, delete, then take the next window. See
  [destinations-and-credentials.md](destinations-and-credentials.md), "Keeping only a rolling archive
  locally".
- Product search accepts at most 99 days per call. Split longer windows.
- A full-disc SEVIRI level 1.5 product size was roughly 180 MB when this was written; check the real size from `search_satellite_products` rather than assuming it holds.
- MTG FCI collections exist only from 2024 and are not in the cloud buckets.

## EUMETSAT S3 buckets on the EWC

**Anonymous (no credentials), but reachable only from inside the European Weather Cloud.** The same
listing that works from an EWC host returns 403 from a laptop. Establish where the user is running
before diagnosing anything as a signing problem. From outside the EWC, use the EUMETSAT Data Store via
the `eumdac` skill or AWS Open Data where the collection exists there; otherwise the read has to run
from a host inside the EWC.

Bucket names are long and specific, for example `seviri-meteosat-0-degree.fcdr.level15.netcdf`. Take
them from `get_satellite_collection`, never from memory; a shortened or guessed name returns
`NoSuchBucket`.

Two endpoints, and the split is not obvious:

| Endpoint | Holdings |
|---|---|
| `https://s3.r1.cloud.eumetsat.int` | SEVIRI FCDR at all three positions, MVIRI, CM SAF cloud type, ERA5 subset, drought and vegetation |
| `https://s3.waw3-1.cloudferro.com` | NWC SAF, OPERA radar, OPERA-SEVIRI-NORDLIS, GeoRing and its Himawari/GOES/SMS sources, OSI SAF sea ice |

**GeoRing is a Zarr store, not per-timestep files.** The `level1g` bucket holds a chunked array, so
there are no dated object keys to build and the per-file download model does not apply. Open it with
`xarray` or `zarr` against the endpoint and slice what you need. Collections carry `esf:storeFormat` to
mark this.

**Use path-style addressing.** Most of these bucket names contain dots. A virtual-host URL built from
one — `seviri-meteosat-0-degree.fcdr.level15.netcdf.s3...` — fails TLS certificate validation, and the
error does not say so. Pass `s3={'addressing_style': 'path'}` in the boto3 `Config`, and address
objects as `<endpoint>/<bucket>/<key>`.

Some buckets are families rather than single buckets: the per-year NWC SAF buckets, and the GOES and
SMS archives with one bucket per satellite. Substitute the year or satellite number into the name.

## Reading in place rather than downloading

Neither bucket family has to be copied before it is used. From inside the EWC, or from AWS in the same
region, reading objects directly is normally the better default: nothing to stage, no local storage,
nothing to clean up. Downloading earns its place when the link is slow, when the same data will be read
many times over a slow or metered link, or when the analysis runs somewhere with no network.

**The output format decides this before speed does.** Reading in place works only when the data is
wanted in the format it is already stored in, and rule 13 decides what happens when it is not. NetCDF
out of a Zarr store is a slice this skill writes, and the output needs a destination. GeoTIFFs out of
a NetCDF archive is a rewrite of every file, which this skill does not do: unless firecube covers the
product and Zarr is what was asked for, the files come down as they are stored. Ask the user for the
format before measuring anything; collections carry `esf:format` to say what they already hold.

Where the format matches, decide on a measured number from the machine that will read the data, never
on an assumption — `get_throughput_probe` gives the commands and `plan_data_access` applies the
thresholds. See [streaming-and-stac.md](streaming-and-stac.md).

The two bucket shapes behave differently. Per-file collections give a catalogue of object keys, or of
the narrowest prefix the documented layout determines; where an item is marked
`esf:prefixResolved: false` you list that prefix to get real keys. A store marked `esf:storeFormat`
has no per-timestep objects at all — open it and slice.

Requester-pays buckets invert the advice: every pass is billed again, so repeated reads are cheaper
downloaded once. Check `esf:requesterPays` before choosing.

And where data does have to move, it rarely has to move through the host. Bucket to bucket is a copy
between two S3 endpoints - server-side within one service, streamed through memory between two - so the
local disk is involved only when a file must genuinely land on it, and then only a batch at a time. See
[destinations-and-credentials.md](destinations-and-credentials.md), "Copying bucket to bucket".

## EUMETSAT cloud buckets

Anonymous S3 inside the European Weather Cloud, and the fastest route from a machine there. Use the
endpoint returned by `get_satellite_collection` for the collection in hand - see the endpoint table
above, which is the authority on which holdings sit on which endpoint.

```bash
aws s3 ls --no-sign-request --endpoint-url <endpoint-from-get_satellite_collection> \
  s3://<bucket-name-from-get_satellite_collection>/2020/06/01/
```

```bash
# The endpoint has to be quoted: an unquoted "https://" ends the parameter at its first colon.
rclone copy ':s3,provider=Other,endpoint="<endpoint-from-get_satellite_collection>":<bucket-name-from-get_satellite_collection>/2020/06/01/' <dest>
```

There is no product index, so build object keys from the documented layout in `get_satellite_collection` (`esf:keyPattern`) and the collection's cadence.

Bucket objects are usually stored unpacked (`.nc`, `.nat`), so extraction rarely applies here. Where a
key ends in `.gz` or `.zip`, unpack it the same way as a Data Store product.

The catalogue entries behind these holdings are hand-maintained and carry a verification date; treat an old one with suspicion.

## AWS Open Data

Anonymous S3, no index, well-documented key layouts.

| Bucket | Data | Key layout |
|---|---|---|
| `noaa-goes16` … `noaa-goes19` | GOES ABI | `ABI-L1b-RadF/<year>/<day-of-year>/<hour>/` |
| `noaa-himawari8`, `noaa-himawari9` | Himawari AHI | `AHI-L1b-FLDK/<year>/<month>/<day>/<hhmm>/` |
| `noaa-mrms-pds` | US radar mosaic | by product and date |

```bash
aws s3 ls --no-sign-request s3://noaa-goes16/ABI-L1b-RadF/2023/152/12/
```

Check `esf:requesterPays` before using a bucket in bulk: a requester-pays bucket bills the reader.

## Anonymous access is mandatory, not optional

GeoRing and the EUMETSAT cloud buckets are anonymous (no credentials), though reachable only from
inside the EWC; the AWS Open Data buckets are genuinely public. None of them hold per-user
authorisation, and all must be read with request signing switched **off**.

This trips people up because the failure looks like the opposite of what it is. A key in any of the
four places [destinations-and-credentials.md](destinations-and-credentials.md) searches - an rclone
remote, `~/.s3cfg`, `AWS_ACCESS_KEY_ID` or `AWS_PROFILE`, `~/.aws/credentials` - makes the client sign
the request by default. A public bucket has no idea who that identity is and answers
`403 AccessDenied` or `InvalidAccessKeyId`. It reads like "you lack permission", when in fact you had
too much: the fix is to send no identity at all.

| Tool | How |
|---|---|
| AWS CLI | `aws s3 ls --no-sign-request s3://noaa-goes16/` |
| boto3 | `boto3.client("s3", config=Config(signature_version=UNSIGNED))` |
| rclone | a remote with no `access_key_id` or `secret_access_key` set |
| s3cmd | **cannot.** It has no `--no-sign-request` and no anonymous mode, and refuses a config with empty keys. Use one of the three above |

```python
import boto3
from botocore import UNSIGNED
from botocore.config import Config

# AWS Open Data
s3 = boto3.client("s3", config=Config(signature_version=UNSIGNED))

# EUMETSAT cloud buckets and GeoRing: same, plus the endpoint the collection
# actually sits on - see the endpoint table above, or get_satellite_collection
ewc = boto3.client(
    "s3",
    endpoint_url="<endpoint-from-get_satellite_collection>",
    config=Config(signature_version=UNSIGNED),
)
```

The one exception is a requester-pays bucket, which does need an identity because it bills the reader.
Check `esf:requesterPays` on the collection before assuming a bucket is free, and tell the user when a
plan depends on one.

Only the EUMETSAT Data Store needs a real credential. Never pass Data Store or S3 credentials to a
public bucket; it cannot use them and will reject the request.

## Choosing between them

1. **Prefer anonymous sources** where they hold the same data. Fewer moving parts, no credential handling.
2. **For anything measuring change over time, use a climate or fundamental data record.** Operational archives are not homogeneous across satellite transitions, so instrument changes look like trends.
3. **Match the satellite to the events.** Geostationary imagery is usable to roughly 60 degrees from the sub-satellite point. Atlantic and European events suit SEVIRI at 0 degrees, west Pacific suits Himawari at 140 east, the Americas suit GOES.
4. **For whole-globe coverage use GeoRing**, accepting lower resolution. In a climate or global context it comes before NOAA global composites such as GridSat: GeoRing merges the full ring from the contributing imagers, while GridSat is resampled onto a coarse, low-cadence global grid. Fall back to a NOAA composite for the years GeoRing does not cover, and say that is why. GeoRing is not itself a homogenised climate data record; if a study turns on inter-calibration rather than resolution, put both options to the user.
5. **When the application needs higher spatial or temporal resolution, drop the merged products and use native discs**: MTG FCI at 0 degrees, GOES over the Americas, Himawari over the west Pacific. Small or short-lived features - overshooting tops, convective initiation, anything measured at the pixel scale - are this case. `recommend_collections` with `preference: highest_resolution` ranks them this way for you.
6. **MTG FCI is Data Store only, and only from 2024.**
