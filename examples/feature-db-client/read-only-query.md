# Query Features In A Bounding Box

## Prompt

Get all validated cloud features in this bounding box for January 2023 using feature_client.

## Expected Agent Behavior

- Use the `feature-db-client` skill and load `references/querying.md`.
- Resolve `FEATURE_API_URL` explicitly; state which environment it is before connecting. Reads run
  freely in every environment, so this does not block the query, but the environment is still stated.
- Use `client.get_features` with `feature_types` accepting either an ID or a name (e.g. `'cloud'`), a
  `bbox` in `(minx, miny, maxx, maxy)` EPSG:4326 order, a `time_window` in ISO 8601, and
  `status='validated'`.
- If the feature-type name is ambiguous against `get_feature_types()`, show the candidates and ask
  rather than guessing.
- Do not call `save_features`, `create_*`, or `update_*` for a read-only request.

## Command Pattern

```python
import os
from features.apiclient import FeatureAPIClient

client = FeatureAPIClient(
    api_key=os.environ['FEATURE_API_KEY'],
    base_url=os.environ['FEATURE_API_URL'],
)

gdf = client.get_features(
    feature_types=['cloud'],
    bbox=(<minx>, <miny>, <maxx>, <maxy>),
    time_window=('2023-01-01T00:00:00Z', '2023-01-31T23:59:59Z'),
    status='validated',
)
```

## Expected Response Shape

- Workflow type: read-only query.
- Prerequisites: resolved `base_url`, valid feature-type name or ID.
- Safety boundary: no write call proposed or run.
- Validation status: reads run freely once the environment is stated; result is a `geopandas.GeoDataFrame`.
