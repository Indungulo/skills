---
name: esf-satellite-data
description: Use when building reproducible satellite imagery datasets around detected weather features from the EUMETSAT Earth System Feature database, including feature selection, class balancing, coverage checks, access-route planning, volume estimates, and manifests across EUMETSAT Data Store, EUMETSAT S3 buckets, and AWS Open Data.
license: CC-BY-4.0
compatibility: The internal esf MCP server 0.9.0 (feature-db-api) registered with the agent, plus EUMETSAT Data Store or S3 access for the imagery.
metadata:
  author: EUMETSAT
  version: "0.1.0"
---

# Earth System Feature satellite datasets

Turn a request like *"give me satellite imagery for 100 weak, moderate, severe and extreme storms each, under 50 TB"* into a selected, balanced, reproducible dataset.

Grounded in the `esf` MCP server (feature-db-api), the EUMETSAT Data Store, the EUMETSAT S3 buckets and AWS Open Data. The `esf` server is internal: there is no public request route, and access is granted only by the service administrator. This skill decides *which events and which imagery*; use `eumdac` for authenticated Data Store downloads and use another product-specific skill only if it is installed in the current session.

**Skill version 0.9.0, written for `esf` MCP server 0.9.0.** The server names its own version and the
skill version it expects in its instructions. If they disagree with these, say so and carry on.

**Prefer live tool output over anything written here.** Counts, extents and availability change; this file does not.

## Rules

1. **Connect first, and check versions.** If the `esf` tools are not available, give the user the connection command below and stop; do not guess at feature types, counts or extents from memory. Compare the server's own version and the skill version it expects against the versions declared at the top of this file; on a mismatch, say so, suggest updating the skill, and **carry on** rather than stopping for a patch release.
2. **Confirm which feature type when several are close.** Never pick silently or map a phrase to a type from memory: take the candidates from `list_feature_types`, list their counts, periods and sources, say how they differ and which you would choose, and ask. See [workflow.md](references/workflow.md), section 2a.
3. **Do not classify or balance unless asked.** By default call `select_balanced_events` with no `classes` argument: it returns a plain deduplicated sample and skips profiling for intensity, proposing thresholds, waiting for confirmation and running an aggregate. Only take the classification path when the user asked for classes, intensities or an even split across them, and then use an equal `perClass`. When a class cannot supply its share, report the imbalance rather than quietly rebalancing around it.
4. **Profile before classifying.** When you do classify, always call `describe_feature_type` first. The database has no severity column, and the server says so explicitly. Never invent an intensity property.
5. **Get the classification confirmed, when there is one.** If the user did ask for classes, propose the property, the classes and the thresholds with your reasoning, and wait. A classification is a scientific judgement and an expensive query; do not spend either on a guess.
6. **Deduplicate into events.** One real event is many observations. Always pass `identityKey`, taken from the `identityKeyCandidates` that `describe_feature_type` reports for the type in front of you: without one, a request for 100 events returns 100 observations from a handful of events. Some types carry no identity property at all and cannot be deduplicated server-side; say so rather than silently counting observations as events.
7. **Work within the row budget.** The heavy tools refuse a window that is too large and suggest a shorter one; follow it and iterate, looping a multi-year study one year at a time. Do not retry the same call.
8. **Report shortfalls and unclassified shares.** A class that could not supply enough events, or a large unclassified count, changes what the dataset means. Never present a truncated or badly-classified result as if it were complete.
9. **In a climate or global context prefer GeoRing to NOAA global composites such as GridSat, and prefer native discs to both when resolution drives the study.** GeoRing merges the full geostationary ring at native resolution; GridSat resamples onto a coarse, low-cadence grid. Use `recommend_collections` with `preference: highest_resolution` when small or short-lived features need pixel-scale detail; GeoRing is not a homogenised climate data record, so put both options to the user when a study turns on inter-calibration rather than resolution. See [data-sources.md](references/data-sources.md), "Choosing between them".
10. **Check coverage before promising data.** `check_event_coverage` confirms products exist for the specific events. A collection can span the period overall and still miss the times and places you need.
11. **Size it, then decide whether it has to move at all.** Present the volume and its assumptions; the figure is bytes to transfer, and extracted data needs its own room on top. For any open bucket, run the format and access decisions in rules 12 to 14 first. **Get explicit approval before any transfer.**
12. **Always ask what format the output should be in.** Never assume it, never infer it from the collection, and never let it default silently: pass the answer to `plan_data_access` as `outputFormat` (`source` when the user wants whatever the data is already in). It decides the access route before speed does, since anything but the stored format means every file is read and rewritten, a download however fast the bucket. See [parameters-to-iterate.md](references/parameters-to-iterate.md).
13. **Route the dataset before planning the transfer, and take the first branch that matches.** In order: a dataset-specific skill installed in this session (e.g. `eumdac` for the Data Store), then `firecube` if Zarr was asked for and a plugin covers the product, then reading an already-Zarr bucket in place, then download-and-unzip with no conversion. Say which branch you took. See [workflow.md](references/workflow.md), step 8.
14. **Prefer reading open buckets in place.** Call `get_throughput_probe`, ask the user to run it on the machine that will read the data, and pass the measured speed to `plan_data_access` with the format from rule 12; never invent a read speed. When it says stream, the STAC catalogue it returns is the dataset: save it and write no download script. See [streaming-and-stac.md](references/streaming-and-stac.md) and [zarr-store-template.md](references/zarr-store-template.md).
15. **Before writing any script that reads a bucket directly (branches 2 and 3 of rule 13), list what the data actually contains.** Never name a variable, channel or dimension from memory: run `read_store_subsets.py --list` first, which reads no data, and quote its output to the user before choosing. See [zarr-store-template.md](references/zarr-store-template.md).
16. **When downloading, fetch in parallel by default.** The generated script downloads with half the host's cores, because transfers are I/O bound and one file at a time wastes most of the link. `--jobs` overrides it. Say the worker count in the pre-download report.
17. **When the destination is another bucket, copy straight there and never stage the files on the host.** Copy server-side when both ends are the same S3 service, and stream through two rclone remotes (anonymous source, authenticated destination) when they are not; say which shape the transfer took. See [destinations-and-credentials.md](references/destinations-and-credentials.md), "Copying bucket to bucket".
18. **Extract archives automatically.** Extract each one as soon as it lands, verify the extraction, then delete that archive so peak disk stays near the extracted size rather than double it; never delete an archive whose extraction failed. Skip only on request, with `--keep-archives --no-extract`.
19. **When files must land on local disk, keep only a rolling batch, never the whole dataset.** Download a batch, extract, verify, ship it to its real destination, delete only what is confirmed to have arrived, then start the next; check `df` before each batch against a stated ceiling. State the ceiling and batch size in the pre-download report. See [download-script-template.md](references/download-script-template.md), "Rolling local archive".
20. **Access GeoRing, the EUMETSAT S3 buckets and AWS Open Data anonymously, never with a credential.** All three are anonymous (no credentials); the EUMETSAT ones are reachable only from inside the EWC, while AWS Open Data is reachable from anywhere, and a signed request gets 403 from any of them. Only the EUMETSAT Data Store needs a credential. See [data-sources.md](references/data-sources.md), "Anonymous access is mandatory, not optional".
21. **Ask the user which rclone remote or AWS profile to use for a transfer that needs a credential.** Check only presence with the read-only commands in [destinations-and-credentials.md](references/destinations-and-credentials.md) (e.g. `rclone listremotes`); never open, cat or print a credential file.
22. **Check the destination.** Confirm a local path exists, is writable and has room for the extracted data, not just the download; check local room against the rolling ceiling from rule 19 rather than the dataset total, since only one batch is ever on disk. For a bucket destination, a listing (e.g. `aws s3 ls`) confirms only that it exists and is readable; write permission is confirmed by the first small object of the approved transfer landing, not by a listing or a speculative test write. If the destination is non-empty, ask before writing into it.
23. **Always write a manifest.** Every file linked to its feature id, event id, class, reference time and offset, plus the seed and the exact tool inputs; write a missing-data report too. When the plan says stream, the STAC catalogue plays this part: save it and record the seed and tool inputs alongside it.
24. **Run scripts only when asked.** Generate and explain the download script by default; execute it only on request, and offer `--dry-run` first.

## Connect

The `esf` MCP server is internal for now: there is no public request route. Access is granted by the service administrator, and the user needs an authorised endpoint from their own organisation before any of this works. If no endpoint is available, say so plainly and stop rather than guessing at one or inventing a URL.

Give the command for the client the user is actually running. If the client is unknown, ask which client they use before choosing a configuration command.

Set `ESF_MCP_URL` to the authorised endpoint supplied by the user's organisation.

Claude Code:

```bash
claude mcp add --transport http esf "$ESF_MCP_URL" -s user
```

GitHub Copilot CLI:

```bash
copilot mcp add --transport http esf "$ESF_MCP_URL"
```

opencode, in `opencode.json` (project) or `~/.config/opencode/opencode.json` (global):

```json
{ "mcp": { "esf": { "type": "remote", "url": "<ESF_MCP_URL>", "enabled": true } } }
```

Any data transfer still needs the user's own credentials; the server holds none and never downloads anything.

## Route

| Intent | Read |
| --- | --- |
| The full gated sequence, and worked examples of the four common requests | [workflow.md](references/workflow.md) |
| What to ask the user, in what order, and sensible defaults | [parameters-to-iterate.md](references/parameters-to-iterate.md) |
| Per-tool inputs, outputs, costs and pitfalls | [mcp-tools.md](references/mcp-tools.md) |
| Which satellite source holds what, and how to fetch from each | [data-sources.md](references/data-sources.md) |
| Destination checks, credential discovery, bucket-to-bucket copies and the rolling local archive | [destinations-and-credentials.md](references/destinations-and-credentials.md) |
| Reading data in place: the probe, the STAC catalogue and the open snippets | [streaming-and-stac.md](references/streaming-and-stac.md) |
| Slicing a Zarr store around events, and the uv environment for it | [zarr-store-template.md](references/zarr-store-template.md) |
| The download script and manifest format, when files are wanted on disk | [download-script-template.md](references/download-script-template.md) |
| What went wrong and what to do about it | [error-cases.md](references/error-cases.md) |

## Response Shape

```text
Dataset goal:
Feature type (confirmed, and what it was chosen over):
Classification (confirmed with user? yes/no):
Sampling (plain sample by default; classes only if asked):
Events per class (requested / returned / available):
Collections and access route:
Coverage check:
Expected volume (transfer / extracted):
Output format (requested / as stored):
Route taken (rule 13: dataset skill / firecube / Zarr in place / download-and-unzip only):
Access mode (stream / download), measured read speed and where it was measured:
Destination (or STAC catalogue location, when reading in place):
Transfer shape (server-side bucket copy / streamed bucket to bucket / to local disk):
Peak local disk (ceiling, batch size, what is deleted when):
Extraction (automatic unless asked otherwise):
Parallelism (workers used):
Versions (skill / server):
Gaps and imbalance:
Seed and reproducibility:
Validation status:
```

Fill every line. "Not checked" is a valid and useful answer; a blank line is not.
