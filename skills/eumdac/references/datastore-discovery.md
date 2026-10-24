# Data Store Discovery

Use this reference for listing collections and describing collections/products.

## Discover / Describe

EUMETSAT guide material may refer to "discover, search and download" as the Data Store workflow. In the validated `eumdac 3.1.1` CLI, the discovery command is `describe`, not `discover`.

Always check the user's installed CLI:

```bash
eumdac --version
eumdac --help
```

If `eumdac --help` lists `discover` in a newer or different installation, inspect it directly:

```bash
eumdac discover --help
```

If `discover` is not listed, use `describe` for discovery/listing.

List available collections:

```bash
eumdac describe
```

Filter collections:

```bash
eumdac describe --filter "*MSG*"
```

Describe a collection or product:

```bash
eumdac describe --collection "<collection-id>"
eumdac describe --collection "<collection-id>" --product "<product-id>"
```

Use `--flat` when showing product package contents without a tree view.

## Validation

Credential-free validation:

```bash
eumdac describe --help
```

Live collection/product descriptions require credentials, network access, and real collection/product IDs.
