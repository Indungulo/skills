# Scaffold And Test A New Plugin

## Prompt

```text
I have daily GeoTIFF files with a time dimension. Scaffold a Firecube plugin for them and show me how to test it locally.
```

## Expected Agent Behavior

- Route to `plugin-development.md`.
- Do not choose a template from the dataset description alone. Require an inspected sample file (dims, variables, coordinates, fill values, constant shape across granules) or the product format specification first.
- Ask what the user will do with the product, then recommend the template from the inspected data; the user does not need to know Parquet from Zarr. If they insist on a mismatched format, state the implications once and comply on confirmation. Templates: time-appended cube (GenericZarrIngestor), tabular rows (GenericParquetIngestor), region writes into a preallocated cube (DirectZarrIngestor). `BaseIngestor` is a last resort, offered only for a named, verified limitation of the three templates.
- Run `firecube plugins create --help` before proposing scaffold flags.
- Follow the Plugin Design Procedure: existing plugin, goals, data (ask; if no sample exists, hand off to the eumdac skill and resume once the user names the directory), inspect two products, design, feasibility estimate, recommend, summary, metadata, plan file, then a stop point (execute now, pause and resume from the file later, or change), then build with progress lines.
- Before `plugins create`: present the final design summary and have it confirmed with the question tool; then ask for plugin name, author, email, licence, and target directory with the question tool. Never invent identity or licence values or pass `--non-interactive` with placeholders.
- Treat `plugins create` and `plugins install` as mutating: they write a project directory and change the Python environment.
- For the local test, use files the user provides; do not generate sample GeoTIFFs. Use a `file://` target inside the user's chosen work directory.
- Verify registration with `firecube plugins list` and `firecube plugins describe <plugin-name>` after the editable install.
- Point to the public Plugin Development guide for hook details rather than reproducing it: https://eumetsat.github.io/firecube/latest/guides/plugins/

## Safe Command Pattern

```bash
firecube plugins create --help
firecube plugins create <plugin-name> --target-dir <workdir>   # confirm flags against help first
firecube plugins install <workdir>/<plugin-project>
firecube plugins list
firecube plugins describe <plugin-name>
firecube ingest <plugin-name> --show-options
```

Local test run after confirmation:

```bash
firecube ingest <plugin-name> \
  --input-data <abs-path>/sample-input \
  --target file:///<abs-path>/test-products/<plugin-name>.zarr \
  --product-name <plugin-name> \
  --output-format zarr \
  --write-mode direct
```

## Safe Response Shape

```text
Workflow type: plugin development
Prerequisites: firecube 0.1.7 in a venv, a writable project directory, a few real sample files from the user
Safety boundary: filesystem mutation (scaffold) and environment mutation (editable install); local test target only
Validation status: create --help inspected; scaffold and install not run until confirmed
```
