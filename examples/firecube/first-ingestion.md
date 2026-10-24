# First Ingestion With An Installed Plugin

## Prompt

```text
I have NetCDF files in ./raw and the plugin my_plugin is installed. Ingest them into a local Zarr product.
```

## Expected Agent Behavior

- Route to `ingestion.md`; load `configuration-storage.md` only if URI or storage questions arise.
- Confirm the plugin is registered with `firecube plugins list` and inspect its options with `firecube ingest my_plugin --show-options` before proposing `--option` values.
- Use the user's `./raw` directory as-is. Do not generate, download, or rename input files.
- Require a full `file:///<abs-path>/...` target URI and the `--write-mode` flag, which `firecube 0.1.7` does not infer.
- Keep `--storage-type local` coherent with the `file://` scheme if set explicitly.
- Pass the `--output-format` the plugin's class produces (`plugins describe` shows it) and name the target to match. Do not explain why.
- Treat `ingest` as a mutating command: state the target that will be written and ask for confirmation before running.
- After the run, verify with read-only `firecube chunks list --product-name <target-uri>`.

## Safe Command Pattern

```bash
firecube plugins list
firecube ingest my_plugin --show-options
```

Then, after confirmation:

```bash
firecube ingest my_plugin \
  --input-data <abs-path>/raw \
  --target file:///<abs-path>/products/my_product.zarr \
  --product-name my_product \
  --storage-type local \
  --storage-driver fsspec \
  --output-format zarr \
  --write-mode direct
```

Verify:

```bash
firecube chunks list --product-name file:///<abs-path>/products/my_product.zarr
```

## Safe Response Shape

```text
Workflow type: ingest
Prerequisites: firecube 0.1.7, my_plugin registered, ./raw exists and matches the plugin's accepted format, writable target directory
Safety boundary: local mutation of the target Zarr store; confirm before running
Validation status: plugins list and --show-options run; ingestion not run until confirmed
```
