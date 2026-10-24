# Reference Data And Errors

Use for the `get_*` / `create_*` / `update_*` table per reference type and for the client's exception classes.

## Reference Data (get_* = read; create_*/update_* = write)

| Type | Fetch | Create | Update | Required fields |
|---|---|---|---|---|
| Satellites | `get_satellites()` | `create_satellite(d)` | - | name, description (+ optional period dicts) |
| Feature types | `get_feature_types()` | `create_feature_type(d)` | - | name, description (optional tags list) |
| Model versions | `get_model_versions()` | `create_model_version(d)` | - | algorithm, version |
| Labellers | `get_labellers()` | `create_labeller(d)` | - | name (optional email) |
| Tags | `get_tags()` | `create_tag({'name': ...})` | - | name |
| Product files | `get_product_files()` | `create_product_file(d)` | - | filename, filepath, satId |
| Visualisation files | `get_visualisation_files()` | `create_visualisation_file(d)` | - | filename, filepath |
| Batches | `get_batches()` | `create_batch(d)` | - | name, modelVersionId |
| Usage rights | `get_usage_rights()` | `create_usage_right(d)` | `update_usage_right(id, d)` | none enforced by the client (`license`, `description`, `url` are all optional; an empty dict is accepted) |

Shapely geometries passed in dicts (e.g. `named_region`) are serialized automatically.

## Error Handling

```python
from features.apiclient import (FeatureAPIError, AuthenticationError, ValidationError,
                                NotFoundError, ServerError, NetworkError, RateLimitError)
```

| Exception | HTTP / cause |
|---|---|
| `AuthenticationError` | 401/403 (bad API key) |
| `ValidationError` | 400 (request payload rejected) |
| `NotFoundError` | 404 |
| `RateLimitError` | 429 |
| `ServerError` | 5xx |
| `NetworkError` | timeout / connection failure |

Empty results return an empty GeoDataFrame with correct columns, not an error.

