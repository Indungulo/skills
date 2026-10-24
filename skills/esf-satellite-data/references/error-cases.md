# When things go wrong

## The `esf` tools are not available

Give the connection command for the user's client and stop:

Use the authorised endpoint supplied by the user's organisation:

```bash
# Claude Code
claude mcp add --transport http esf "$ESF_MCP_URL" -s user

# GitHub Copilot CLI
copilot mcp add --transport http esf "$ESF_MCP_URL"
```

opencode has no add command: add an `mcp` entry with `"type": "remote"` and the authorised endpoint URL to `opencode.json`.

Then `/mcp` to confirm. Do not answer from memory about feature types, counts or extents.

## A tool returns an error result

`isError` with a message means the tool ran and refused. The message says what to change. Read it and act; do not retry unchanged.

| Message contains | What it means | Do |
|---|---|---|
| `exceeds the configured scan budget` | The window is too large to run | Narrow to the suggested window and iterate |
| `time budget` or `narrow your time range` | The query hit its statement timeout | Narrow further, or pin a bounding box |
| `timeStart and timeEnd are both required` | The heavy tools need both bounds | Supply both; they are what makes the query affordable |
| `no feature type named` | The name does not exist | Call `list_feature_types` and show the user |
| `unsupported op` | Bad property filter operator | Use `eq`, `ne`, `in`, `lt`, `lte`, `gt`, `gte`, `exists`, `missing` |
| `99 days` | Data Store search window too long | Split into shorter windows |
| `no product index` | Bucket collection with no inventory | Build keys from the layout in `get_satellite_collection` |

## HTTP 429

The endpoint rate-limits per client IP (120 requests a minute by default, at time of writing), with
`Retry-After`. Back off and batch: use `check_event_coverage` for many events rather than one search each.

## A class comes back empty or tiny

In order of likelihood:

1. The bin bounds miss the data's real range. Check the percentiles in `describe_feature_type`.
2. The property name is wrong. Check the exact spelling in the profile.
3. The period genuinely has few such events. Widen it, or accept and report the imbalance.
4. The wrong basin or region is filtered.

A large `unclassified` count points at 1 or 2.

## The event count looks ten times too high

Almost always a missing or wrong `identityKey`, so every observation counted as an event. Check `hints.perObservationIds`: grouping by one of those is the classic mistake.

## A feature type has no intensity and no track identity

Some feature type families carry only a generic identifier and a creator property, and nothing that
reads as intensity or track identity. They cannot be classified by severity or deduplicated
server-side; `describe_feature_type` shows this directly, so check it rather than assuming from the
type's name.

Say so plainly. Offer selection by time and region instead, or client-side spatio-temporal clustering, and be explicit that the clustering is yours rather than the data's.

## A source is unavailable

The federation degrades: the warning names the failed source and the others still answer. Report which source is missing, since a Data Store outage means no product search and no real coverage check.

The embedded catalogue needs no network and always answers.

## Coverage is zero for some events

- Wrong satellite for the region. Check each event's longitude against the sub-satellite point.
- Before the collection's start. Check the extent from `get_satellite_collection`.
- Too tight a search box. Widen `radiusDeg`.

If most events have no coverage, the collection is wrong, not the events.

## The volume estimate is enormous

In order of effectiveness: fewer events per class, a shorter window around each event, a longer cadence, a smaller product (level 2 rather than radiances), a lower-resolution merged product.

Report the options with numbers and let the user choose.

## The format asked for cannot be produced

The user asked for GeoTIFF, or for a crop, or for Zarr out of something that is not Zarr, and neither
a dataset-specific skill nor `firecube` covers it. This is not an error and not a gap to work around:
rule 13 has run out of branches and the route is download-and-unzip.

Say which format the data is stored in, which was asked for, and that this route downloads and unzips
and does not crop, regrid or convert. Name a skill that could if one exists. Offer the files as they
are stored, with the manifest, and let the user convert downstream. Do not open a file to check
whether it would have worked - that is the one thing this route does not do.

## The destination is not writable or too small

Stop and say so with the numbers. Do not start a transfer that will fail partway.

## 403 AccessDenied on a public bucket

Two different causes. Check which one before changing anything.

**Are you inside the EWC?** The EUMETSAT S3 buckets are anonymous but not reachable from the public
internet. From outside they answer 403 no matter how the request is signed, and no amount of
credential fiddling will help. Confirm where the code is running first. AWS Open Data buckets are
genuinely public and do not have this constraint. If the collection also exists in the EUMETSAT Data
Store or AWS Open Data, use that route via the `eumdac` skill instead; otherwise the request has to run
from a host inside the EWC.

**If you are inside, the request was signed when it should not have been.**
GeoRing, the EUMETSAT cloud buckets and AWS Open Data hold no per-user authorisation, so a signed
request presents an identity they cannot place and they refuse it.

A key in any of the four stores searched in
[destinations-and-credentials.md](destinations-and-credentials.md) - `~/.config/rclone/rclone.conf`,
`~/.s3cfg`, `AWS_ACCESS_KEY_ID`/`AWS_PROFILE`, `~/.aws/credentials` - makes the client sign by
default. Switch signing off rather than hunting for permissions:

- `aws s3 ... --no-sign-request`
- `boto3.client("s3", config=Config(signature_version=UNSIGNED))`
- rclone: a remote with no keys configured
- s3cmd: not usable for anonymous buckets at all, so use one of the above

`InvalidAccessKeyId`, `SignatureDoesNotMatch` and expired-token errors on a public bucket have the same cause and the same fix.

The exception is a requester-pays bucket, which genuinely does need an identity. Check
`esf:requesterPays` on the collection before concluding the credentials are the problem.

## Extraction failed

The archive is kept, never deleted, and the manifest row reads `extract failed: ...`. Usual causes:

- A truncated download. Delete that one file and re-run; the script skips what is already complete.
- Disk filled mid-unpack. Check free space against the extracted size, not the download size.
- An unexpected format. A Data Store product should be a zip; a bucket object is usually already
  unpacked and needs no extraction at all.

If the user wants files left packed, pass `--no-extract --keep-archives` and say so in the summary
rather than leaving them to discover a directory of zips.

## The local disk fills up mid-run

The run was staging the whole dataset instead of a batch of it. Do not just widen the ceiling: switch to
the rolling archive, where each batch is shipped to its real destination and deleted before the next
starts, and check `df` before each batch rather than once at the start.

Two things fill a rolling archive anyway, and both are worth checking before blaming the ceiling:

- **Failed files stay on disk by design**, since a file that never arrived at the destination must not be
  deleted. A run with many failures slowly eats the ceiling; read `missing.csv`, fix the cause, and
  re-run rather than raising the limit.
- **`--jobs` and the ceiling are one budget.** Workers times per-file peak - and an archive plus its
  extracted contents is roughly twice the file - has to stay under it.

## 403 or AccessDenied writing to the destination bucket

The opposite problem to a public bucket answering 403: this end needs a credential, and either it is
missing or the request went out unsigned. Signing is decided per end, so a transfer reading anonymously
and writing with a key is two clients or two rclone remotes, never one `aws` command with
`--no-sign-request` on it. Check which credential the writing end picked up - by name, never by printing
it - and that the bucket and prefix exist.

## The download failed partway

The script is idempotent: re-running skips complete files. Check `missing.csv` for the pattern. Failures clustered on one collection or one period usually mean an upstream problem rather than a local one.
