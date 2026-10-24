# Subscriptions And Livefeed

Use this reference for `subscribe`, `subs`, and `livefeed`.

## Subscription Commands

`subs` is an alias for `subscribe`.

```text
eumdac subscribe set-credentials
eumdac subscribe list
eumdac subscribe add
eumdac subscribe download
```

Set subscription credentials. The user runs this themselves, in their own terminal, with their real username and password; the agent never runs it with real values and never asks the user to paste secrets into the chat. The user should avoid shell history capture, for example a leading space with `HISTCONTROL=ignorespace` set, or the shell's equivalent. This overwrites any stored subscription credentials, so confirm with the user before suggesting it and check for an existing credentials file first (see [auth.md](auth.md)).

```bash
eumdac subscribe set-credentials "<username>" "<password>"
```

List active subscriptions and downloaders:

```bash
eumdac subscribe list
```

Add a subscription. This creates a remote subscription; state the collection, filters, and tag, and get the user's confirmation before running it:

```bash
eumdac subscribe add --collection "<collection-id>" --tag "<tag>"
```

Add search filters as needed, for example `--satellite`, `--bbox`, `--geometry`, `--filename`, `--product-type`, `--timeliness`, or time filters.

For `--bbox` and `--geometry`, use the same EPSG:4326 rules as Data Store search: `--bbox W S E N`, or quoted WKT for `--geometry`.

Download from a subscription:

```bash
eumdac subscribe download --tag "<tag>" --output-dir ./data
```

Useful options include:

```text
--only-incoming
--delay <minutes>
--entry "<pattern>"
--tailor / --chain <chain>
--local-tailor <id>
--threads <n>
--no-progress-bars
```

## Livefeed

`livefeed` downloads products from collections as soon as they are published. It is a long-running, continuous download; state the collection, filters, and output directory, and get explicit confirmation before starting it.

```bash
eumdac livefeed --collection "<collection-id>" --output-dir ./data --entry "*.nat" --onedir
```

`livefeed` supports many of the same search/download filters as `search` and `download`, plus:

```text
--print-notifications
--delay <minutes>
```

Use livefeed only when the user expects a long-running process.

## Safety

Subscriptions and livefeed may create continuous or repeated downloads. Confirm output directory, disk capacity, filters, and stop criteria before starting them.

Never expose subscription usernames/passwords or notification payloads containing private details.

## Validation

Credential-free validation:

```bash
eumdac subscribe --help
eumdac subscribe add --help
eumdac subscribe download --help
eumdac livefeed --help
```

Live validation requires subscription credentials, Data Store access, network access, and real collection IDs.
