# Data Tailor, Local Tailor, And Orders

Use this reference for `tailor`, `local-tailor`, and `order`.

## Data Tailor CLI

Top-level commands in `eumdac 3.1.1`:

```text
eumdac tailor post
eumdac tailor list
eumdac tailor status
eumdac tailor log
eumdac tailor quota
eumdac tailor resources
eumdac tailor delete
eumdac tailor cancel
eumdac tailor clean
eumdac tailor download
```

Post a customisation job:

```bash
eumdac tailor post --collection "<collection-id>" --product "<product-id>" --chain "<chain-id-or-file>"
```

Check status and download output:

```bash
eumdac tailor status "<customisation-id>"
eumdac tailor download "<customisation-id>" --output-dir ./tailored
```

Use `--local-tailor <id>` on supported `tailor` commands to use a configured local instance instead of the Data Tailor Web Service.

## Data Tailor Resources

Resources include:

```text
chains
filters
rois
quicklooks
```

Inspect help before resource operations:

```bash
eumdac tailor resources --help
eumdac tailor resources chains --help
```

## Local Tailor

Manage local Data Tailor instances:

```bash
eumdac local-tailor instances
eumdac local-tailor set "<id>" "http://localhost:40000/"
eumdac local-tailor show "<id>"
eumdac local-tailor remove "<id>"
```

Confirm the local service is running before suggesting local customisations.

## Orders

Order commands:

```text
eumdac order list
eumdac order housekeep
eumdac order status
eumdac order resume
eumdac order restart
eumdac order delete
```

Examples:

```bash
eumdac order list
eumdac order status "<order-id>"
```

`order list` supports filters such as `--failed`, `--archived`, and `--reverse`. `order status` can work with a specific ID or failed/archived orders.

## Safety

Data Tailor and order operations can create, resume, restart, cancel, delete, or clean remote work. Ask for confirmation before `post` (creates a customisation job), and before destructive actions such as `delete`, `cancel`, `clean`, `resume`, `restart`, or broad housekeeping.

## Validation

Credential-free validation:

```bash
eumdac tailor --help
eumdac local-tailor --help
eumdac order --help
```

Live validation requires credentials, network access, and real customisation/order IDs.
