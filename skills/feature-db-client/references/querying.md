# Querying

Use for reads: reference data lookups, feature queries, and nearest-feature search. Reads run freely in every environment.

## Reference Data

```python
satellites = client.get_satellites()          # GeoDataFrame
feature_types = client.get_feature_types()    # GeoDataFrame
model_versions = client.get_model_versions()  # GeoDataFrame
labellers = client.get_labellers()            # GeoDataFrame
tags = client.get_tags()                      # GeoDataFrame
```

## Features

In order to filter by reference data, you can use either the ID or the name of the reference data. For example, `feature_types=[1, 2, 'cloud']` will filter for features with feature type IDs 1 or 2, or with feature type name 'cloud'. When only planning, not executing, read possible reference data and compare it to the prompt. Ask from which reference data user wants to use if there is ambiguity.

```python
gdf = client.get_features(
    feature_types=[1, 2, 'cloud'],          # IDs (int) or names (str), mixed OK
    bbox=(24.0, 60.0, 26.0, 61.0),          # minx, miny, maxx, maxy in EPSG:4326
    time_window=('2023-01-01T00:00:00Z', '2023-01-31T23:59:59Z'),  # ISO 8601
    model_version_id=1, batch_id=3, labeller_id=2, satellite_id=1,
    status='validated',                      # 'draft'|'validated'|'rejected'|'pending'
    tags=['cloud', 'cirrus'],                # OR logic; tags_all=... for AND
    limit=10000, offset=0,                   # paginate manually; default limit 10000
    include_related=True                     # join reference data as columns
)
```

- Returns a `geopandas.GeoDataFrame`, geometry column `geom`, CRS EPSG:4326.
- With `include_related=True` (default) reference data appears as **multi-index columns**:
  `gdf[('satellite', 'name')]`, `gdf[('featureType', 'description')]`.
- Single feature: `client.get_features_by_id(12345)`.
- Nearest neighbours (returns `distance_m`, `time_diff_minutes` columns; `feature_types` is optional here too):
  ```python
  nearest = client.find_nearest_features(lon=25.0, lat=60.0, ref_time='2023-06-15T12:00:00Z',
                                         k=10, time_window_hours=24)
  ```

The signature of `get_features` (verified against the source, `features/apiclient/client.py`):
```python
    feature_types: Optional[List[Union[int, str]]] = None,
    bbox: Optional[Tuple[float, float, float, float]] = None,
    time_window: Optional[Tuple[str, str]] = None,
    model_version_id: Optional[int] = None,
    batch_id: Optional[int] = None,
    labeller_id: Optional[int] = None,
    status: Optional[str] = None,
    tags: Optional[List[str]] = None,
    tags_all: Optional[List[str]] = None,
    satellite_id: Optional[int] = None,
    limit: int = 10000,
    offset: int = 0,
    include_related: bool = True
```

