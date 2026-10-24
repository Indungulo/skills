---
name: feature-db-client
description: Use when interacting with the Earth System Feature Database through the feature_client Python library (FeatureAPIClient, features.apiclient) - fetching or saving features as GeoDataFrames, spatial, temporal and tag queries, nearest-feature search, managing reference data such as satellites, feature types, model versions, labellers, tags, product and visualisation files, batches and usage rights, or running the library's tests.
license: CC-BY-4.0
compatibility: feature-client Python package 0.1.0 (import features.apiclient) and an authorised Earth System Feature Database endpoint and API key (internal service).
metadata:
  author: EUMETSAT
  version: "0.1.0"
---

# Feature DB Python client (feature_client)

Grounded in the public `feature-client` package (import `features.apiclient`), version 0.1.0, from
https://gitlab.eumetsat.int/usc-feature-detection/earth-system-feature-db-client. Verified against
commit `b866f3905fdd95ac12fae9937db9eae305fbee71` (the repository carries no release tags). The
Feature Database service itself is internal: an authorised API endpoint and API key come from the
service administrator, and no public request channel exists yet. Without them, explain this and stop
before live API calls.

- Full API docs: [docs/api_featureapi_client.md](https://gitlab.eumetsat.int/usc-feature-detection/earth-system-feature-db-client/-/blob/b866f3905fdd95ac12fae9937db9eae305fbee71/docs/api_featureapi_client.md)
- Runnable notebooks: [examples/basic_interaction.ipynb](https://gitlab.eumetsat.int/usc-feature-detection/earth-system-feature-db-client/-/blob/b866f3905fdd95ac12fae9937db9eae305fbee71/examples/basic_interaction.ipynb)
- Credentials: `.env` file in working directory

## Package checking

Test package installation and version:

```bash
python3 -c "import features.apiclient; print(features.apiclient.__version__)"
```

If you see `ModuleNotFoundError`, install the package using uv in your Python environment, pinned to
the commit this skill is verified against:

```bash
uv venv
uv pip install "git+https://gitlab.eumetsat.int/usc-feature-detection/earth-system-feature-db-client.git@b866f3905fdd95ac12fae9937db9eae305fbee71"
```

After installing, rerun the version check above and compare `features.apiclient.__version__` against 0.1.0. This skill is verified against 0.1.0 only; warn the user on any mismatch before continuing. Do not guess PyPI package names; install from the repository at the pinned commit above.

## Running the client's tests

The repository's test suite needs its own running test instance of the Feature Database, never a
shared or production service, since the tests create and mutate reference data:

```bash
pip install -e ".[dev]"
pytest tests/                                 # full suite; needs the test instance reachable
pytest tests/test_feature_api_client.py -v    # single file
```

## Hard safety rules

### 1. Secret hygiene

- Never print or log API keys, or embed them in generated code. Load credentials from the environment or an existing local `.env`:
  - `FEATURE_API_KEY` (alias `FEATURE_APIKEY`)
  - `FEATURE_API_URL` (alias `FEATURE_APIURL`)
- Show placeholders like `$FEATURE_API_KEY` in responses.
- Do not read, display, or edit `.env`; the user edits it. Check presence only, with checks that print
  nothing secret, e.g. `test -n "$FEATURE_API_KEY"`.
- If the user is only missing the endpoint and already has a key set, tell them to add
  `FEATURE_API_URL` to their existing `.env` without touching the existing key line.

If necessary secrets are not available, give user instructions to create the `.env` file with the correct keys and URLs, and ensure they are loaded into the environment before running any scripts:

```
FEATURE_API_URL=<authorised_feature_api_url>
FEATURE_API_KEY=<your_api_key_here>
```

### 2. Environment-based write policy

Classify by the base_url the client actually resolves, BEFORE any write call
(`save_features`, `create_*`, `update_*`):

| Resolved base_url | Environment | Writes |
|---|---|---|
| URL the user identifies as development or test | dev/test | Allowed after stating target and row count |
| URL the user identifies as production | **prod** | Ask first for every occurrence |
| anything else | unknown | Ask first |

- Never infer the environment from the URL text (hostnames, path segments, "dev"/"test"/"prod"-looking
  strings). Ask the user once which environment the resolved `base_url` points to, and record the
  answer in the conversation. Anything left unanswered is unknown, and unknown is handled exactly like
  production.
- **Prod-is-default trap:** never construct `FeatureAPIClient` without an explicit `base_url`. The
  constructor's `base_url` parameter does have a default when omitted, and that default must never be
  relied on: an unset `FEATURE_API_URL` means stop and ask. The `KeyError` raised by
  `os.environ['FEATURE_API_URL']` in the Connection snippet when the variable is unset is the intended
  safe outcome, not a bug to work around.
- Reads are always free: `health_check`, `get_features*`, `find_nearest_features`, all other `get_*`.
- When asking, present the exact operation, target environment, and row counts (e.g. "save_features:
  432 GeoDataFrame rows -> prod"). New/edited operations need new approval.
- There is no delete in the client (`delete_feature` is commented out). Do not improvise deletes
  via raw HTTP; if needed, direct the user to their authorised database administration workflow.

## Connection

```python
import os
from dotenv import load_dotenv
from features.apiclient import FeatureAPIClient, AuthenticationError

load_dotenv()  # or rely on exported env vars
client = FeatureAPIClient(
    api_key=os.environ['FEATURE_API_KEY'],
    base_url=os.environ['FEATURE_API_URL']
)
try:
    print(client.health_check())  # {'status': 'healthy', 'database': 'connected'}
except AuthenticationError:
    print("Authentication failed: check FEATURE_API_KEY.")
```

Constructor also accepts `timeout=30`, `verify_ssl=True`, `write_timeout=300` (writes get a longer
budget than reads), and `max_batch_bytes`/`max_batch_features` (defaults for `save_features` batching,
see [saving-features.md](references/saving-features.md)). Supports `with FeatureAPIClient(...) as client:`.

## Route

| Intent | Read |
| --- | --- |
| Reference data lookups, feature queries, nearest-feature search | [querying.md](references/querying.md) |
| Saving features, required metadata, multi-index reference columns, full example | [saving-features.md](references/saving-features.md) |
| Per-type `get_*`/`create_*` table, exception classes | [reference-data-and-errors.md](references/reference-data-and-errors.md) |

## Workflow

1. Resolve environment: read `FEATURE_API_URL`; ask the user which environment it is rather than
   guessing from the URL, then state dev/test/prod/unknown before doing anything.
2. Connect via env-based snippet; verify with `health_check()`.
3. Reads run freely; for writes apply the environment policy (dev/test allowed after stating target and row count, prod/unknown ask).
4. Prefer `save_features` with multi-index reference columns over manual `create_*` calls.
5. Report which environment was used and the result counts.
