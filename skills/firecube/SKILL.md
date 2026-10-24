---
name: firecube
description: Use when working with Firecube, the EUMETSAT plugin-based batch ingestion CLI and Python SDK that turns Earth Observation products into analysis-ready datacubes, for installation, running ingestion, developing/testing/packaging plugins, Zarr/Parquet/Tensogram archive operations, chunk control-plane inspection and recovery, Intake catalogs, benchmarking, performance tuning, or CLI troubleshooting.
license: CC-BY-4.0
compatibility: firecube 0.1.7 on Python 3.12+. The helper scripts in scripts/ run with uv in the plugin project's environment (check_done.py needs NumPy, xarray and zarr).
metadata:
  author: EUMETSAT
  version: "0.1.0"
---

# Firecube

Use this skill for Firecube users and plugin developers: installing the `firecube` CLI, running ingestion with an installed plugin, building a plugin for a new dataset, operating Zarr/Parquet/Tensogram products, recovering interrupted runs, generating Intake catalogs, and benchmarking or tuning throughput. It does not cover contributing to Firecube itself; send those requests to the upstream repository.

This skill is grounded in the PyPI release `firecube 0.1.7`. Install that exact version (`firecube==0.1.7`); Firecube is pre-1.0 and a newer release may change commands, flags, or plugin hooks, so revalidate this skill before recommending one. Prefer the installed `firecube --help` and `firecube <group> <command> --help` output and the public docs at https://eumetsat.github.io/firecube/latest/ when exact flags or behavior matter.

## Operating Rules

1. Never print, commit, or log S3 access keys, secrets, endpoint credentials, private bucket names, or user data paths. Use placeholders such as `s3://<bucket>/<prefix>` and `file:///<abs-path>/<product>.zarr`.
2. Source data is supplied by the user. Never invent, fabricate, or download input files. The installed plugin decides which formats it accepts. If the user has only a relevant, identifiable EUMETSAT Data Store collection ID or name that they named and no local files, hand off to the `eumdac` skill, which owns search, size/space checks, authorisation, and download; resume this skill's work once the user names the directory holding the files. This hand-off is never a fallback for the user's own files in a format the plugin cannot read, or for data from a provider other than the EUMETSAT Data Store: in those cases, ask the user for files in a format the plugin can read, or for a conversion they own, and do not build a decoder for the format found on disk.
3. Before proposing a new plugin, check `firecube plugins list` and the known public plugins table in [plugin-development.md](references/plugin-development.md); MTG FCI L1C already has `mtg_fci_l1c`. Scaffold only when nothing covers the collection or the user wants their own.
4. Do not recommend a plugin template, output format, or data layout without empirical evidence of the data: an inspected product file (dimensions, variables, coordinates, fill values, and whether the shape is constant across granules) or the official product format specification, and a cube design that fixes the time unit from the acquisition geometry (repeat cycle, orbit or half-orbit, day, or event time; never the granule) and combines files per time unit without changing pixel values. A collection ID, product name, filename pattern, directory listing, catalogue abstract, or a tutorial for a similar collection is not evidence. Without it, ask the user whether they have a product on disk and where, or hand off to the `eumdac` skill to obtain one; do not search the user's filesystem for data, and stop until they answer. Once the data is inspected, recommend the output format (Parquet or Zarr) and template yourself from what the data is; do not expect the user to know. The operator's choice is decisive: if they want a format that does not fit the data, state the implications once, and if they confirm, build it that way.
5. Read-only commands run without confirmation when the user asks for a check: `--version`, `--help`, `plugins list|describe|explain`, `ingest <plugin> --show-options`, `chunks list`, `chunks claims list`, `chunks runs list`, `chunks snapshots status`, `zarr slots|validate|compare`, `zarr index show|verify`, `parquet validate`, `archive info|list|validate`, `advise`, `completion`.
6. Mutating commands require explicit user confirmation and, when the flag exists, a dry run first: `ingest`, `zarr preallocate|multires`, `zarr index rebuild`, `parquet consolidate`, `archive create|restore`, `chunks claims clear`, `chunks runs abandon`, `chunks snapshots rebuild`, `plugins create|install|uninstall`, `catalog intake`.
7. Destructive or irreversible commands require confirmation of the exact product URI and scope before execution: `chunks delete`, `chunks delete-span`, `zarr consolidate-time-coord`, and any `--overwrite` or `--force` flag on archive or chunk commands.
8. Always pass the target or product as a full URI (`file:///...` or `s3://...`). Keep `--storage-type` coherent with the URI scheme when you set it explicitly; `file://` means `local`, `s3://` means `s3`.
9. `firecube ingest` requires `--write-mode staged|direct` in 0.1.7; it is not inferred. Prefer `direct` for local targets and slot-range parallel Zarr, and `staged` for S3 targets when scratch disk is available; see [ingestion.md](references/ingestion.md).
10. Before proposing plugin options, run `firecube ingest <plugin> --show-options` or `firecube plugins describe <plugin>`. Do not guess option names.
11. Print one progress line before any step expected to take more than about twenty seconds and one result line after it; never run two long steps silently, and never narrate in between.
12. Keep a plan file for plugin work: operator answers, evidence, design, feasibility, open items, next step. Write it at a path the user names as soon as the design is confirmed and update it at every decision, so a later agent or a compacted context resumes from the file. Before building, obtain approval for the concrete design if it has not already been approved. Record the decision and resume from it without asking again for unchanged scope.
13. Combine evidence: ask the operator first, fetch the public collection metadata, inspect two products, and only then take what is still unknown to a targeted page of the format specification. Two files establish layout, not labels, cadence, or variants, and one complete time unit establishes the group key, the attributes, and the boundary behaviour; when an identity field (platform, direction, baseline) shows more than one value, the operator is asked at once which values are in scope, and each in-scope value is sampled before the group key is fixed. Never read a user guide whole; extract and search it for the relevant tables.
14. Locate the CLI with `command -v firecube` before anything else. Never assume a project `.venv`, a personal virtualenv directory, or any repository-specific path; install into standard user-tool locations or an environment the user names, per [install.md](references/install.md).
15. Run leaf `--help` locally before finalizing exact flags. If installed help and the docs disagree, follow the installed help.
16. Apply the known 0.1.7 quirks in [cli-surface.md](references/cli-surface.md) silently: use the right flag spelling per command, pass the plugin's native output format, always pass `-n` to `chunks`, read `parquet validate`'s JSON rather than its exit code, and so on. Report any material mismatch or failed check; if a known quirk explains it, give the fix briefly.
17. The installed `firecube` in the plugin's own environment is the authoritative source; a git checkout of core is not, it may be commits ahead of the pinned release. Before recommending or rejecting a template, verify the constraint that decides it in the installed template source (`firecube/ingestor/templates/`) or the public docs, and cite the docstring or page. The tables in this skill's references are summaries, not evidence. State the rejected template and the exact constraint next to the recommendation.
18. Never search the filesystem for data files. Once the operator has named a workspace, listing the plugins and readers already in it as a source of conventions is allowed; say what was looked at.
19. When inspection is delegated through an available agent workflow, require the complete dimension, coordinate, variable, and global-attribute tables in its report and copy them into the plan file. A representative sample is not evidence. Skip delegation when the current agent environment does not support it or the user has not authorised parallel agent work.
20. These rules are for the agent, not the user. Never narrate a rule, quote its wording, or explain what you are not allowed to do; the user sees only what is needed from them, in one line.
21. Execution may be parallel; planning and design never are. When the plan file lists independent steps, the tooling can run delegated agents, and the user has authorised parallel agent work, offer parallel execution at the execute stop point, with its cost stated once: more tokens for less wall-clock time. Independence is read from the plan's step dependencies, never assumed; each delegate gets the plan file as its brief and a disjoint set of files; the main agent integrates and runs install, first ingestion, and validation serially.
22. The cost of a run is context times turns: every turn re-reads all earlier tool output, so whatever a command prints is paid for again on every turn after it. Print summaries, not data (counts, `head`/`tail`, one line per item), never a listing, a file, or a dataset repr whole. Full tables and inspection dumps go to the plan file or a sidecar file; print the path and a ten-line summary. Where this skill ships a script for a step (`scripts/inspect_product.py`, `scripts/check_done.py`, beside this file), run the script: one command, one screen of output, the details on disk. Delegate an inspection at most once and receive a table; do not poll for it. Never re-read a file already in context.
23. `BaseIngestor` is the engine's lowest-level contract: no managed writer, no format-aware resume, no parallelism model. Never propose it for something specialised; only for a serious limitation of the three templates, verified in their source, with the loss stated and the operator deciding ([templates.md](references/templates.md)).
24. Plugins use only public Firecube APIs and hooks; gaps go to the Firecube maintainers, not workarounds ([plugin-traps.md](references/plugin-traps.md)).

## Response Contract

When the answer proposes commands, code, or execution, include:

1. **Workflow type**: install, ingest, plugin development, product operation, recovery, catalog, performance, or troubleshooting.
2. **Prerequisites**: Python 3.12+, installed Firecube version, required plugin, source data location, target URI, storage credentials, and optional extras such as `tensogram`.
3. **Safety boundary**: read-only, dry run, local mutation, remote storage mutation, or destructive control-plane change.
4. **Command or code**: minimal examples verified against installed help, or clearly marked as illustrative.
5. **Validation status**: what was run locally, what was not run, and why.

For short factual questions, answer directly without the template.

Keep answers short and lead with the recommendation or missing input. Show commands for the user's current step, verified against installed help; mark fragments as illustrative.

For plugin design, ask about the intended analysis, output geometry, time unit, variable subset, and operating constraints. Use a structured question tool when available, with meaningful options and a free-text answer; otherwise ask in prose. Ask only for missing decisions. Reuse answers and explicit authorization already supplied for the same scope. A failed tool call, silence, or rejected question is not approval; clarify the unresolved decision without repeating settled questions.

Explain the evidence behind technical recommendations and what would change them. Before scaffolding, confirm the design and obtain the plugin name/ID, target directory, author, email, and license if the user has not supplied them. Present identity and legal choices neutrally. Values found in Git configuration or another project may be offered for confirmation but must not be silently adopted. Record the chosen values and evidence in the plan file. Use multi-select only when several answers can apply, and honor the current tool's input limits.

Report material validation failures and environment limitations plainly. Apply known CLI quirks in the command itself and explain them only when needed to understand a result.

## Workflow

1. Capture context: Firecube version, install method, Python version, installed plugins, source data location and format, target URI and storage type, and whether the task mutates storage or control-plane state.
2. Route by intent with the table below and load only the matching reference.
3. Inspect installed help before giving exact flags.
4. Propose the minimal safe command with placeholders; prefer read-only probes and dry runs before mutation.
5. Emit the Response Contract when commands or code are proposed.

## Route By Intent

| Intent or symptom | Read this reference | First checks |
| --- | --- | --- |
| Install, upgrade, verify, extras, shell completion | [install.md](references/install.md) | Python 3.12+, venv, `firecube --version`, needed extras |
| Which commands exist, what each does, read-only vs mutating, renamed flags | [cli-surface.md](references/cli-surface.md) | `firecube --help`, leaf `--help` |
| Config file, env vars, flag precedence, URI rules, storage type/driver, S3 setup | [configuration-storage.md](references/configuration-storage.md) | Full URI, `--storage-type`/`--storage-driver`, config path, credential source |
| Run or plan an ingestion, choose output format, parallel slots, re-runs | [ingestion.md](references/ingestion.md) | Plugin installed, `--show-options`, source data exists, target URI, `--write-mode` |
| Ingest a collection a known public plugin covers (MTG FCI L1C, quickstart example) | [plugin-development.md](references/plugin-development.md) known plugins table, then [ingestion.md](references/ingestion.md) | `plugins list`, `plugins install git+<repo-url>` (no clone needed), plugin README for options and preparation steps |
| Create, implement, test, install, or package a plugin | [plugin-development.md](references/plugin-development.md), start at "Plugin Design Procedure", then [plugin-traps.md](references/plugin-traps.md) | Known plugins, operator goals, sample data (user-supplied, or obtained through the eumdac skill), two inspected products, plan file |
| Zarr slots/preallocate/validate/multires/compare/index, Parquet validate/consolidate, Tensogram archives | [zarr-parquet-archive.md](references/zarr-parquet-archive.md) | Product URI, storage flags, `tensogram` extra for archives, dry-run availability |
| Chunk records, claims, runs, snapshots, crash recovery, delete/reingest, Intake catalog | [chunks-catalog.md](references/chunks-catalog.md) | Product URI, workspace, read-only listing first, destructive scope |
| Choose or explain a plugin template, its hooks, batch lifecycle, context and exceptions | [templates.md](references/templates.md) | The cube design first (plugin-development.md), then the template section |
| Run in parallel, workers, slot ranges, group fan-out, write safety, a plugin's worker or write-mode guard, staged versus direct | [parallelism.md](references/parallelism.md) | Template in use, write domain each writer owns, `--write-mode` |
| Measure or compare runs, benchmark a setting, justify a limit with numbers | [benchmarks.md](references/benchmarks.md) | Fixed source window, what to hold constant, `zarr compare` for equivalence |
| Tune batch size or knobs, metrics/logs/traces, production checklist | [performance.md](references/performance.md) | `advise batch-size`, `advise compliance`, what to hold constant |
| Errors, tracebacks, old flags, plugin not found, URI rejected, missing extras | [troubleshooting.md](references/troubleshooting.md) | Exact command, sanitized output, `firecube --version`, `plugins list` |

## Core CLI Surface

`firecube 0.1.7` registers these groups, as shown by `firecube --help`:

```text
Core:     ingest, archive
Inspect:  zarr, parquet, chunks, catalog
Tools:    plugins, advise, completion
```

Minimal local ingestion shape (the plugin, input directory, and target come from the user):

```bash
firecube ingest <plugin-name> \
  --input-data <input-dir> \
  --target file:///<abs-path>/<product>.zarr \
  --product-name <product-name> \
  --output-format zarr \
  --write-mode direct
```

## Public Sources

- Documentation: https://eumetsat.github.io/firecube/latest/
- API reference: https://eumetsat.github.io/firecube/latest/reference/
- Source and issue tracker: https://github.com/eumetsat/firecube
- Package: https://pypi.org/project/firecube/
- Example plugin used by the official quickstart: https://github.com/eumetsat/firecube-quickstart-plugin
- MTG FCI L1C plugin: https://github.com/eumetsat/firecube-mtg-fci-l1c

Point users to the issue tracker for bugs and feature requests. Do not cite private contacts.
