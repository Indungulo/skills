# Data Store Metalink

Use this reference for downloading Data Store cart metalink files.

## Download A Cart Metalink

This downloads every product listed in the metalink file. State the destination directory and, where known, the product count and size, and get the user's confirmation before running it.

Download a Data Store cart metalink file:

```bash
eumdac download-metalink cart-user.xml --output-dir ./data --integrity
```

Useful options:

```text
--output-dir DIR
--integrity
--dirs
--keep-order
--no-progress-bars
```

Use `--dirs` to put each product in its own directory. Use `--keep-order` only when the user wants the order file retained.

## Validation

Credential-free validation:

```bash
eumdac download-metalink --help
```

Live metalink downloads require a real Data Store cart metalink file, credentials, network access, and storage space.
