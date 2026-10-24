# Download script and manifest

**This is the opt-in path.** Reach it only when `plan_data_access` returned `download`, or when the user asked for files on disk. For an open bucket the usual answer is to read the data where it lies — see [streaming-and-stac.md](streaming-and-stac.md).

**This path delivers the files as they are stored, and no conversion is on offer.** It downloads and unzips; it does not crop, regrid or change format, and it opens nothing - the script's only imports are transfer, archive and hashing machinery. Time is narrowed by choosing which objects or products fall in each event window, from the documented key layout and the collection's cadence, never by opening a file and slicing it. If the user asked for a format the data is not in, rule 13 has already decided what to tell them: firecube on branch 2 if a plugin covers the product, and otherwise say the conversion is not something this path does. Do not quietly hand back the inputs and call it the dataset.

**Before any of it, settle where the files are going, because the host may not be in the path at all.**
Three shapes, and the answer changes the script rather than a flag in it:

| Source | Destination | What the script does |
| --- | --- | --- |
| Bucket | Bucket | Copies object to object and writes nothing to local disk (rule 17). Server-side where both ends are the same S3 service, streamed through memory where they are not. |
| Bucket or Data Store | Local path, files are the deliverable | The skeleton below. Local disk holds the dataset because the dataset *is* the local files. |
| Data Store, or anything needing conversion | Bucket | Stages a batch locally, ships it, deletes it, repeats (rule 19). Peak disk is one batch, never the dataset. |

Ask which one applies before generating anything. "Put it in S3" and "put it in /data" are different scripts, and the first usually needs no scratch space at all.

Generate a script the user can read, re-run and hand to someone else. Explain it before running it, and offer `--dry-run` first.

The dependency block at the top is PEP 723 inline metadata: `uv run download_events.py --dry-run` builds
the environment on first run and reuses it after, so nothing has to be installed by hand. It names
`boto3` without a pin - state a version only if this skill states one elsewhere, which it does not.

## Inputs

Two files written from the MCP output:

- `events.json`: the `events` array from `select_balanced_events`, unchanged.
- `plan.json`: the collections, cadence, destination and the exact tool inputs including the seed.

Keeping the raw tool output means the dataset can be traced back to the query that produced it.

## Skeleton

```python
#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "boto3",
# ]
# ///
"""
Download satellite imagery for a selected set of weather events.

Reads events.json (from select_balanced_events) and plan.json, expands each
event window into time steps at the collection's cadence, resolves each step to
an object key or product id, downloads it, extracts it if it is an archive, and
writes a manifest.

Fetches in parallel by default, using half the host's cores, because these
transfers are I/O bound and one file at a time wastes most of the link. Pass
--jobs to change it.

Archives are extracted as soon as they land and the archive is then removed, so
peak disk stays near the extracted size instead of double it. Pass --no-extract
to leave everything packed.

Idempotent, in two parts: an existing file is skipped once its size matches the
object's real size (or is simply non-empty when the real size cannot be had
cheaply), and an archive that has already been extracted and removed is skipped
by its `<name>.done` marker rather than re-downloaded, since the archive itself
is gone by then. An interrupted run resumes by running it again.

Credentials are read from the environment or the standard config files at run
time. None are stored here.
"""

import argparse
import boto3
import bz2
import os
import csv
import gzip
import hashlib
import shutil
import json
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from botocore import UNSIGNED
from botocore.config import Config

MANIFEST_FIELDS = [
    "file", "collection", "source", "feature_id", "event_id", "class",
    "ref_time", "step_time", "offset_minutes", "lon", "lat", "bbox",
    "size_bytes", "sha256", "status", "archive", "extracted_files", "dest_uri",
]


def time_steps(window_start, window_end, cadence_minutes):
    """
    Yield acquisition times inside an event window, inclusive of both ends.

    Real acquisitions fall on the cadence grid from midnight (00:00, 00:15,
    00:30, ... for a 15-minute cadence), not on whatever second the window
    happens to start at. Snapping window_start up to the next grid point
    first is what makes the generated keys line up with real objects; without
    it a window starting at 03:07 would build keys for 03:07, 03:22, ... that
    nothing on the server ever wrote.
    """
    step = timedelta(minutes=cadence_minutes)
    epoch = window_start.replace(hour=0, minute=0, second=0, microsecond=0)
    steps_since_midnight = -(-(window_start - epoch) // step)  # ceiling division
    t = epoch + steps_since_midnight * step
    while t <= window_end:
        yield t
        t += step


def object_key(collection, step_time):
    """Build the object key for one acquisition from the collection's layout."""
    # From get_satellite_collection's esf:keyPattern. Substitute the real
    # pattern for the collection being downloaded rather than guessing.
    return f"{step_time:%Y/%m/%d}/{collection}_{step_time:%Y%m%dT%H%M}Z.nc"


ARCHIVE_SUFFIXES = (".zip", ".tar", ".tar.gz", ".tgz", ".gz", ".bz2")

# Assumed when a collection publishes no cadence; the volume tool makes the
# same assumption and says so.
DEFAULT_CADENCE_MINUTES = 15


def default_jobs():
    """
    Half the host's cores.

    These transfers are I/O bound, so threads are the right tool and the GIL is
    not a constraint. Half rather than all leaves room for the extraction work
    and for whatever else the machine is doing.
    """
    return max(1, (os.cpu_count() or 2) // 2)


def is_archive(path):
    name = path.name.lower()
    return any(name.endswith(sfx) for sfx in ARCHIVE_SUFFIXES)


def extract(path, keep_archive=False):
    """
    Unpack one archive into a fresh scratch directory, move its files into
    place, and return the moved paths.

    `path.parent` is the shared event directory every worker downloading
    into that event writes to, so listing it after unpacking - rather than
    the scratch directory alone - would count every other worker's files
    too, and the empty-extraction guard below would never fire. Unpacking
    into `tempfile.mkdtemp(dir=target)` first, and listing only that, is
    what makes the guard mean something. The archive is removed only after
    its files have been moved into place, so a failed unpack never loses
    the download.
    """
    target = path.parent
    produced = []

    if path.name.lower().endswith((".zip", ".tar", ".tar.gz", ".tgz")):
        scratch = Path(tempfile.mkdtemp(dir=target))
        try:
            shutil.unpack_archive(str(path), str(scratch))
            for extracted_path in scratch.rglob("*"):
                if not extracted_path.is_file():
                    continue
                dest = target / extracted_path.relative_to(scratch)
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(extracted_path), str(dest))
                produced.append(dest)
        finally:
            shutil.rmtree(scratch, ignore_errors=True)
    elif path.name.lower().endswith((".gz", ".bz2")):
        opener = gzip.open if path.name.lower().endswith(".gz") else bz2.open
        out = target / path.stem
        with opener(path, "rb") as src, out.open("wb") as dst:
            shutil.copyfileobj(src, dst)
        produced = [out]
    else:
        return [path]

    if not produced:
        raise RuntimeError(f"{path.name} extracted to nothing; archive kept")
    if not keep_archive:
        path.unlink()
    return produced


def sha256_of(path, chunk=1 << 20):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(chunk), b""):
            digest.update(block)
    return digest.hexdigest()


def anonymous_s3(endpoint_url=None):
    """
    An S3 client that sends no identity at all.

    GeoRing and the EUMETSAT cloud buckets are anonymous (no credentials), though reachable only
    from inside the EWC; AWS Open Data is genuinely public. None hold per-user authorisation.
    Signing must be switched off explicitly: with AWS credentials in the environment boto3 signs
    by default, and an anonymous bucket answers 403 because it cannot place that identity. The fix
    is to send none.
    """
    return boto3.client(
        "s3",
        endpoint_url=endpoint_url,  # EWC buckets need this; AWS does not
        config=Config(signature_version=UNSIGNED, s3={"addressing_style": "path"}),
    )


def marker_path(target):
    """Where the completion marker for an extracted archive lives."""
    return target.with_name(target.name + ".done")


def write_marker(target, size_bytes, sha256):
    marker_path(target).write_text(f"{size_bytes}\t{sha256}\n")


def expected_size(collection, key):
    """
    The object's real size from the bucket, or None when it cannot be had
    cheaply (a Data Store product, or a lookup that fails).
    """
    if collection.get("accessType", "s3-anonymous") != "s3-anonymous":
        return None
    try:
        client = anonymous_s3(collection.get("endpoint"))
        return client.head_object(Bucket=collection["bucket"], Key=key)["ContentLength"]
    except Exception:  # noqa: BLE001 - falls back to the size-only check
        return None


def download_one(collection, key, target, dry_run):
    """
    Fetch one object. Returns "ok", "skipped", or an error string.

    An archive is deleted once it is extracted (see `extract`), so the
    archive's own presence cannot be the resume check for it - a re-run
    would see no file and download it again even though the data already
    landed. `<name>.done`, written after a successful extraction, is
    checked first for that reason. Short of that, an existing file is
    trusted only when its size matches the object's real size where one is
    known; a merely non-empty file also matches a truncated download.
    """
    if marker_path(target).exists():
        return "skipped"
    if target.exists():
        expected = expected_size(collection, key)
        if expected is None:
            if target.stat().st_size > 0:
                return "skipped"
        elif target.stat().st_size == expected:
            return "skipped"
    if dry_run:
        return "would-download"
    target.parent.mkdir(parents=True, exist_ok=True)

    access = collection.get("accessType", "s3-anonymous")
    if access == "s3-anonymous":
        client = anonymous_s3(collection.get("endpoint"))
        client.download_file(collection["bucket"], key, str(target))
        return "ok"
    if access == "datastore":
        # eumdac handles the token itself; never pass credentials in here.
        raise NotImplementedError("call eumdac for Data Store products")
    # Requester-pays buckets bill the reader, so they do need an identity.
    raise NotImplementedError(f"unsupported access type {access!r}")


def fetch_one(event, collection, key, target, ref_time, step, args):
    """
    Download, and if needed extract, one file. Returns its manifest row.

    Runs on a worker thread and touches nothing shared, so the only ordering
    concern is the manifest, which the caller sorts.
    """
    status, extracted = "failed", []
    for _ in range(args.retries):
        try:
            status = download_one(collection, key, target, args.dry_run)
            break
        except Exception as exc:  # noqa: BLE001 - recorded, not raised
            status = f"error: {exc}"

    # Read the archive's own size and hash now, while it still exists: extract()
    # deletes it, and computing these afterwards would record 0 and "".
    size_bytes = target.stat().st_size if target.exists() else 0
    sha256 = sha256_of(target) if target.exists() and not args.dry_run else ""

    # Extract immediately, so at most one archive per worker exists at a time.
    archive_name = ""
    if status in ("ok", "skipped") and not args.no_extract and is_archive(target):
        archive_name = target.name
        try:
            extracted = extract(target, keep_archive=args.keep_archives)
            write_marker(target, size_bytes, sha256)
        except Exception as exc:  # noqa: BLE001 - recorded, not raised
            status = f"extract failed: {exc}"

    return {
        "file": str(target),
        "collection": collection["id"],
        "source": collection.get("source", ""),
        "feature_id": event.get("featureId"),
        "event_id": event["eventId"],
        "class": event["class"],
        "ref_time": event["refTime"],
        "step_time": step.isoformat(),
        "offset_minutes": int((step - ref_time).total_seconds() // 60),
        "lon": event.get("lon"),
        "lat": event.get("lat"),
        "bbox": json.dumps(event.get("bbox")),
        "size_bytes": size_bytes,
        "sha256": sha256,
        "status": status,
        "archive": archive_name,
        "extracted_files": ";".join(p.name for p in extracted),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--events", default="events.json")
    parser.add_argument("--plan", default="plan.json")
    parser.add_argument("--dest", required=True)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--retries", type=int, default=3)
    parser.add_argument("--no-extract", action="store_true",
                        help="leave archives packed instead of extracting them")
    parser.add_argument("--keep-archives", action="store_true",
                        help="extract but also keep the archive, roughly doubling disk use")
    parser.add_argument("--jobs", type=int, default=default_jobs(),
                        help=f"parallel downloads (default {default_jobs()}, half this host's cores)")
    parser.add_argument("--s3-dest",
                        help="s3://bucket/prefix to write to. With a bucket source the files are copied "
                             "straight across and never touch this host; otherwise --dest becomes a "
                             "staging area pruned batch by batch")
    parser.add_argument("--dst-endpoint",
                        help="endpoint for --s3-dest when it is not AWS (an EWC bucket, for instance)")
    parser.add_argument("--max-local-gb", type=float, default=50.0,
                        help="ceiling for the rolling local archive; the batch size is derived from it")
    args = parser.parse_args()

    events = json.loads(Path(args.events).read_text())
    plan = json.loads(Path(args.plan).read_text())
    dest = Path(args.dest)

    # Build every unit of work first, then hand the whole list to the pool.
    # Nesting the pool inside the event loop would drain it at each event
    # boundary and leave workers idle between events.
    tasks = []
    for event in events:
        ref_time = datetime.fromisoformat(event["refTime"].replace("Z", "+00:00"))
        start = datetime.fromisoformat(event["windowStart"].replace("Z", "+00:00"))
        end = datetime.fromisoformat(event["windowEnd"].replace("Z", "+00:00"))

        for collection in plan["collections"]:
            cadence = collection.get("cadenceMinutes", DEFAULT_CADENCE_MINUTES)
            for step in time_steps(start, end, cadence):
                key = object_key(collection["id"], step)
                target = dest / event["class"] / event["eventId"] / collection["id"] / Path(key).name
                tasks.append((event, collection, key, target, ref_time, step))

    print(f"{len(tasks)} files across {len(events)} events, {args.jobs} workers")

    manifest_rows, missing_rows = [], []
    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        futures = [pool.submit(fetch_one, *t, args) for t in tasks]
        for future in as_completed(futures):
            row = future.result()
            manifest_rows.append(row)
            if not row["status"].startswith(("ok", "skipped", "would")):
                missing_rows.append(row)

    # Sort in the main thread: completion order is arbitrary, and a manifest
    # that reshuffles between runs is not reproducible.
    manifest_rows.sort(key=lambda r: (r["class"], r["event_id"], r["collection"], r["step_time"]))
    missing_rows.sort(key=lambda r: (r["class"], r["event_id"], r["collection"], r["step_time"]))

    write_csv(dest / "manifest.csv", manifest_rows)
    write_csv(dest / "missing.csv", missing_rows)
    (dest / "dataset.json").write_text(json.dumps({
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "plan": plan,
        "eventCount": len(events),
        "fileCount": len(manifest_rows),
        "missingCount": len(missing_rows),
    }, indent=2))

    print(f"{len(manifest_rows)} files, {len(missing_rows)} missing")
    return 1 if missing_rows else 0


def write_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=MANIFEST_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    sys.exit(main())
```

## Straight to another bucket

**With a bucket at each end, nothing lands here.** Downloading into a working directory and uploading it
afterwards moves every byte twice, needs free space for the whole dataset, roughly doubles the wall-clock
time and leaves a directory to clean up. Replace `download_one` with a copy, and drop the extraction and
hashing machinery: an object copied unopened needs neither.

```python
def parse_s3_uri(uri):
    bucket, _, prefix = uri.removeprefix("s3://").partition("/")
    return bucket, prefix.strip("/")


def destination_client(endpoint_url=None):
    """
    The writing end, with the user's own credentials from the environment.

    Signing is per end, and the usual shape here is an anonymous source with an
    authenticated destination - which is why this is two clients rather than one
    `aws` command: --no-sign-request applies to a whole command and would
    unsign the write as well.
    """
    return boto3.client(
        "s3",
        endpoint_url=endpoint_url,
        config=Config(s3={"addressing_style": "path"}),
    )


def copy_one(src, src_bucket, key, dst, dst_bucket, dst_key, same_service, dry_run):
    """
    Move one object bucket to bucket, writing nothing to disk.

    Same service: copy_object, and the bytes never leave it. Different services:
    the body is handed to the multipart uploader as a file-like object, so peak
    memory is the part size times the concurrency, not the object size.

    Returns the destination's own view of the size, because an upload call
    returning is not evidence the object arrived.
    """
    if dry_run:
        return 0
    if same_service:
        dst.copy({"Bucket": src_bucket, "Key": key}, dst_bucket, dst_key)
    else:
        body = src.get_object(Bucket=src_bucket, Key=key)["Body"]
        dst.upload_fileobj(body, dst_bucket, dst_key)
    return dst.head_object(Bucket=dst_bucket, Key=dst_key)["ContentLength"]
```

The manifest row records `dest_uri` instead of a local path, and `size_bytes` from the `head_object`
above. `sha256` stays empty and the manifest says so: hashing would mean reading every object back, which
is the transfer this route exists to avoid. Compare sizes against the source instead, and say in the
summary that verification was by size.

The same thing without Python, for a whole prefix rather than per event:

```bash
rclone copy --transfers 8 \
  ':s3,provider=Other,endpoint="https://s3.r1.cloud.eumetsat.int":<src-bucket>/<prefix>/' \
  '<dst-remote>:<bucket>/<prefix>/'
```

See [destinations-and-credentials.md](destinations-and-credentials.md), "Copying bucket to bucket", for
the server-side variant and the signing caveats.

## Rolling local archive

**When files must land here first - `eumdac` writes to a directory, and a conversion has to write its
output somewhere - keep only a batch of them.** Peak disk is what has to fit, not the total: a 50 TB
dataset must not need 50 TB of scratch.

```python
def batch_size(mean_file_bytes, ceiling_bytes, jobs):
    """
    How many files may be on local disk at once.

    An archive and its extracted contents briefly coexist, so budget twice the
    file size per file in flight. Never smaller than the worker count, or the
    pool drains at every batch boundary.
    """
    return max(jobs, int(ceiling_bytes // max(1, mean_file_bytes * 2)))


def ensure_room(path, needed_bytes):
    """Check before each batch, not once at the start."""
    free = shutil.disk_usage(path).free
    if free < needed_bytes:
        raise SystemExit(
            f"{free / 1e9:.1f} GB free at {path}, batch needs {needed_bytes / 1e9:.1f} GB"
        )


def ship_and_prune(rows, dest, dst, dst_bucket, prefix, dry_run):
    """
    Move a finished batch to its real home, then delete the local copies.

    Takes the paths `fetch_one` recorded in row["local_paths"] - the extracted
    files where there was an archive, the downloaded file where there was not -
    so nothing has to be reconstructed from names.

    Nothing is deleted on the strength of an upload call returning: each file is
    confirmed present at the destination, at the size it was written, before it
    is removed here. A file that failed to arrive stays on disk and stays in the
    manifest as failed, which is the only way the run resumes honestly.
    """
    for row in rows:
        delivered = []
        for local in (Path(p) for p in row["local_paths"]):
            if dry_run or not local.exists():
                continue
            key = f"{prefix}/{local.relative_to(dest)}".lstrip("/")
            dst.upload_file(str(local), dst_bucket, key)
            arrived = dst.head_object(Bucket=dst_bucket, Key=key)["ContentLength"]
            if arrived != local.stat().st_size:
                row["status"] = f"size mismatch at destination: {arrived}"
                continue          # leave it on disk; it has not been delivered
            delivered.append(f"s3://{dst_bucket}/{key}")
            local.unlink()
        row["dest_uri"] = ";".join(delivered)
```

Then run the batches in sequence rather than submitting every task at once. `dst_client`, `dst_bucket`
and `dst_prefix` are the writing end, built once from `--s3-dest` and `--dst-endpoint` before the loop
starts - `parse_s3_uri` and `destination_client` are the two helpers already defined above, under
"Straight to another bucket":

```python
    dst_client = dst_bucket = dst_prefix = None
    if args.s3_dest:
        dst_bucket, dst_prefix = parse_s3_uri(args.s3_dest)
        dst_client = destination_client(args.dst_endpoint)

    size = batch_size(plan.get("meanFileBytes", 200 << 20), int(args.max_local_gb * 1e9), args.jobs)
    print(f"{len(tasks)} files in batches of {size}, ceiling {args.max_local_gb:.0f} GB")

    for start in range(0, len(tasks), size):
        batch = tasks[start:start + size]
        ensure_room(dest, size * plan.get("meanFileBytes", 200 << 20) * 2)
        with ThreadPoolExecutor(max_workers=args.jobs) as pool:
            rows = [f.result() for f in as_completed(
                [pool.submit(fetch_one, *t, args) for t in batch])]
        if args.s3_dest:
            ship_and_prune(rows, dest, dst_client, dst_bucket, dst_prefix, args.dry_run)
        manifest_rows.extend(rows)
```

`fetch_one` needs one addition for this: alongside `extracted_files` it records
`local_paths`, the actual paths it produced, which is what `ship_and_prune` deletes. Keep it out
of `MANIFEST_FIELDS` - it is working state, not provenance, and the manifest already carries
`dest_uri`, which is where the file ended up. Pop it before `write_csv`, or pass
`extrasaction="ignore"` to the `DictWriter`, which raises on an unknown key otherwise.

### The same thing around `eumdac`

The Data Store route is not this script - `eumdac` is its own downloader, and the `eumdac` skill drives
it - so there the rolling archive is a shell loop around it. One window at a time, shipped and pruned
before the next starts:

```bash
set -euo pipefail

# STAGE has to be a scratch directory named by the user, never a shared or
# guessed one: rclone move below deletes whatever is already in it.
: "${STAGE:?set STAGE to an empty scratch directory - eumdac skill owns the download rules}"
if [ -n "$(ls -A "$STAGE" 2>/dev/null)" ]; then
  echo "$STAGE is not empty; refusing to start (rclone move would delete its contents)" >&2
  exit 1
fi

CEILING_GB=50
failures=0

while read -r start end; do
  avail=$(df -BG --output=avail "$STAGE" | tail -1 | tr -dc '0-9')
  if [ "$avail" -lt "$CEILING_GB" ]; then
    echo "$avail GB free at $STAGE, below the $CEILING_GB GB ceiling; stopping" >&2
    exit 1
  fi

  if ! timeout 3600 eumdac download -c "$COLLECTION" -s "$start" -e "$end" -o "$STAGE"; then
    echo "eumdac download failed for $start .. $end" >&2
    failures=$((failures + 1))
    continue
  fi

  for zip in "$STAGE"/*.zip; do
    [ -e "$zip" ] || continue
    unzip -q -d "${zip%.zip}" "$zip" && rm "$zip"
  done

  # move, not copy: rclone deletes each source file only once the transfer has
  # succeeded, and --checksum makes that a verification rather than a hope.
  rclone move --checksum --transfers 8 "$STAGE" "$DEST_REMOTE:$BUCKET/$PREFIX/"
done < windows.txt

if [ "$failures" -gt 0 ]; then
  echo "$failures window(s) failed to download; see the messages above" >&2
  exit 1
fi
```

Windows are the batch here, so size them by what a window costs on disk rather than by the calendar: a
day of 15-minute full discs is not the same number of gigabytes for every collection. `timeout` bounds
each `eumdac` call so a stalled transfer cannot hang the loop; the `eumdac` skill owns everything about
how that command itself behaves, so nothing here overrides its retries or pins its version.

Notes that matter more than the code:

- **`--jobs` and the ceiling are the same budget.** Workers times per-file peak has to stay under it. A
  small ceiling means fewer workers, not a thinner margin.
- **Never pass `--keep-archives` here.** It exists to keep the packed copy, which is the opposite of what
  a rolling archive is for.
- **Failures accumulate and are reported, not swallowed.** A window whose download fails is skipped and
  counted rather than falling through to `unzip` on files that never arrived; the loop still exits
  non-zero when any window failed.
- **Say the numbers before starting**: the ceiling, the batch size, the number of batches, and what is
  deleted when. A user who expected the whole dataset locally needs to hear that it will not be there.

## Outputs

| File | Contents |
|---|---|
| `manifest.csv` | One row per file, linking it to its feature, event, class, reference time and offset, plus the archive it came from, what was extracted, and `dest_uri` where the file actually ended up |
| `missing.csv` | The subset that failed or was unavailable |
| `dataset.json` | Provenance: the plan, the seed, the tool inputs, the counts, the timestamp |

The manifest is not optional. Without it nobody can tell which storm a file belongs to, what class it was assigned, or how to rebuild the selection. Always state where it was written.
