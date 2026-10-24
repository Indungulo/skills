# Destinations and credentials

Check both before generating a download, not after.

## Destination

```bash
DEST=/path/from/user
[ -d "$DEST" ] || echo "does not exist"
[ -w "$DEST" ] && echo "writable" || echo "NOT writable"
df -h "$DEST" | tail -1
ls -A "$DEST" | head -5
```

Rules:

- **Ask whether the destination is a bucket or a local path**, before checking anything. It decides the whole transfer: a bucket destination with a bucket source means the host never holds the data at all (rule 17, below), while a local path means a rolling archive rather than room for the whole dataset (rule 19, below).
- **Never invent a path.** Ask.
- **Non-empty destination: ask before writing into it.** Offer a dated subdirectory instead.
- **Compare free space against the estimate** and say the numbers, not "should be fine".
- For a local path, `[ -w "$DEST" ]` above is enough evidence of write permission; do not also write and
  remove a probe file.

Layout: `<dest>/<class>/<event_id>/<collection>/<file>`. Class first makes an imbalance visible in a directory listing.

## Credentials

Two separate things. The EUMETSAT Data Store credential is one file and one purpose:

| Purpose | Location |
|---|---|
| EUMETSAT Data Store | `~/.eumdac/credentials` |

S3 keys for a transfer that needs one can live in an rclone remote, an s3cmd config, the environment, or
the AWS SDK files. **Do not search these and pick one: ask the user which rclone remote or AWS profile
they want used.** They may have several, aimed at different endpoints, and only they know which one
belongs to this transfer. Once they name it, confirm only that it is present - never open, cat or print
a credential file to find out what it holds.

```bash
# Presence only. Report which store answered, never what is in it.
rclone listremotes 2>/dev/null                      # remote names only, reads no key
[ -f ~/.s3cfg ] && echo "s3cmd config present"
[ -n "$AWS_ACCESS_KEY_ID" ] && echo "S3 key in environment${AWS_PROFILE:+ (AWS_PROFILE=$AWS_PROFILE)}"
[ -f ~/.aws/credentials ] && echo "AWS credentials file present: $(grep -c '^\[' ~/.aws/credentials) profile(s)"
[ -f ~/.eumdac/credentials ] && echo "eumdac credentials present"
```

`rclone listremotes` prints remote names only, and `grep -c '^\['` counts profile headers. Neither
reads a key. Do not substitute `aws configure list`, which prints part of the access key id.

**s3cmd cannot read an anonymous bucket.** It has no `--no-sign-request` and no anonymous mode -
checked against s3cmd 2.4.0 - and it refuses a config with empty keys. If the user names an s3cmd
profile for an open bucket, say so and use the AWS CLI, boto3 or rclone instead.

Rules:

- **Never print, echo, log or write credential contents.** Not into a script, not into a manifest, not into a summary.
- **Never put credentials in a generated script.** Read them from the environment or the standard file at run time.
- If a needed credential is missing, say which one and where it goes, and point at the `eumdac` skill for the Data Store. Do not offer to create one.
- Anonymous sources need nothing. Say so, and prefer them.
- **Finding a key is a reason to check signing is off, not to use it.** A public bucket answers 403 to a signed request, and every one of these four stores is a way for a client to sign one without being asked. See [data-sources.md](data-sources.md), "Anonymous access is mandatory, not optional".

## Writing to S3

Confirm the target bucket exists before generating anything:

```bash
aws s3 ls s3://<bucket>/ --endpoint-url <endpoint> | head -3
```

**This proves the bucket exists and is readable, nothing about write access.** Do not run a speculative
test write to check that separately. Write permission is confirmed by the first small object of the
approved transfer landing and being read back with `head_object`; if that fails, stop and report it
before sending the rest.

For a large transfer to S3, prefer `rclone` or `aws s3 sync` with retries over a per-file loop, and still
write the manifest locally.

## Copying bucket to bucket

**When the source is a bucket and the destination is a bucket, the host should never hold the data.**
Downloading into a working directory and uploading it afterwards moves every byte twice, needs free space
for the whole dataset, doubles the wall-clock time and leaves a directory to clean up. Three shapes, best
first — say which one the transfer used.

### 1. Server-side, when both ends are the same S3 service

The bytes never reach the host at all: the service copies the object internally.

```bash
# One endpoint, two prefixes. CopyObject under the hood.
aws s3 cp --recursive --endpoint-url <endpoint> \
  s3://<src-bucket>/<prefix>/ s3://<dst-bucket>/<prefix>/

# rclone between two remotes on the same provider needs this flag, or it falls
# back to streaming through the host.
rclone copy --s3-server-side-across-configs src:bucket/prefix dst:bucket/prefix
```

### 2. Streamed between two services, still touching no disk

The usual shape here: an anonymous source (AWS Open Data, an EWC bucket) and an authenticated
destination. `rclone copy` reads each object and writes it to the other end through memory.

```bash
# The endpoint has to be quoted: an unquoted "https://" ends the parameter at its first colon.
rclone copy --transfers 8 \
  ':s3,provider=Other,endpoint="<endpoint-from-get_satellite_collection>":<bucket-name-from-get_satellite_collection>/2020/06/01/' \
  'mydest:datasets/storms/2020/06/01/'
```

Signing is decided per end, and that is the reason for rclone here rather than the AWS CLI:
`--no-sign-request` applies to the whole `aws` command, so one command cannot read anonymously and write
with a credential. A keyless rclone remote is the anonymous end, and it stays anonymous even on a host
with `AWS_ACCESS_KEY_ID` exported, because rclone reads the environment only when the remote sets
`env_auth = true`.

### 3. Streamed in Python, when the copy is per event rather than per prefix

```python
src = boto3.client("s3", endpoint_url=SRC_ENDPOINT,
                   config=Config(signature_version=UNSIGNED,
                                 s3={"addressing_style": "path"}))
dst = boto3.client("s3", endpoint_url=DST_ENDPOINT,          # keys from the environment
                   config=Config(s3={"addressing_style": "path"}))

# Same service: server-side, no bytes through the host.
dst.copy({"Bucket": src_bucket, "Key": key}, dst_bucket, dst_key)

# Different services: streamed. upload_fileobj reads the body in parts and
# uploads them, so peak memory is the part size times the concurrency, not the
# object size. Nothing is written to disk.
body = src.get_object(Bucket=src_bucket, Key=key)["Body"]
dst.upload_fileobj(body, dst_bucket, dst_key)
```

Verify before recording success: `head_object` on the destination and compare `ContentLength` against the
source. Do not treat an upload call returning as proof the object arrived.

## Keeping only a rolling archive locally

Some routes have no bucket-to-bucket form. `eumdac` writes Data Store products into a directory, and a
conversion — slicing a Zarr store, unpacking a native product — has to put its output somewhere. **Even
then the dataset never has to exist locally in full.**

Work in batches against a ceiling the user agrees to:

1. Pick the ceiling from free space, not from the dataset size. `df` on the destination, keep a margin.
2. Size a batch from it: `batch = ceiling / (mean file size × unpacked multiple)`. A Data Store zip and
   its extracted contents are briefly both on disk, so a zip route needs roughly twice its own size per
   file in flight.
3. For each batch: download, extract, verify, ship the result to its final home, `head_object` (or
   `stat`) to confirm it arrived, then delete the batch's local files. Only then start the next.
4. Check free space again before each batch. A run that silently fills the disk at 80 % complete has
   wasted the whole transfer.

State the ceiling, the batch size and what gets deleted when, in the pre-download report. `--jobs`
interacts with this: workers × per-file peak has to stay under the ceiling, so a small ceiling means
fewer workers, not a smaller margin.

Never combine this with `--keep-archives`, which exists to keep the packed copy and is exactly what a
rolling archive is trying not to do.

[download-script-template.md](download-script-template.md), "Rolling local archive", has the working
version.
