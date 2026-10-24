# Saving Features

Use for writes. Apply the environment write policy in `SKILL.md` before every `save_features`, `create_*`, or `update_*` call.

## Required Metadata And Minimal Example

Required: `featureType` (via flat ID `featureTypeId`/`('featureType', 'id')` or name `('featureType',
'name')`), `geom` (Shapely, EPSG:4326), `observationStartTime` (ISO 8601), and `observationEndTime`.
`labeller` and the other reference types below are optional for `save_features`, not required.

Reference data types `save_features` auto-detects and creates from multi-index columns (from
`REFERENCE_DATA_TYPES` in the source):
- satellite
- featureType
- modelVersion
- labeller
- tags
- productFile
- visualisationFile
- batch

There is no `named_region` reference type in this client; do not use it as a multi-index column.

See comprehensive example below for details on how to save them.

The minimal example below saves features with only required metadata plus a `labeller` reference,
shown because it's a common real-world case. It creates new `featureType` and `labeller` reference
rows as a side effect, so it must never run against production; confirm the target environment first.

```python
import os
import time
from datetime import datetime

import geopandas as gpd
from shapely.geometry import Point
from features.apiclient import FeatureAPIClient, ValidationError, FeatureAPIError

client = FeatureAPIClient(
    api_key=os.environ['FEATURE_API_KEY'],
    base_url=os.environ['FEATURE_API_URL'],
)
target_environment = "dev"  # confirmed with the user; never inferred from the URL text

# Create a timestamp for unique reference-data names.
timestamp = int(time.time())

# Create features with embedded reference data using multi-index columns
features_only = gpd.GeoDataFrame({

    'observationStartTime': [
        datetime(2024, 1, 1, 12, 0, 0),
        datetime(2024, 1, 2, 12, 0, 0),
    ],
    'observationEndTime': [
        datetime(2024, 1, 1, 12, 30, 0),
        datetime(2024, 1, 2, 12, 30, 0),
    ],
    ('featureType', 'name'): [f'Demo-feature-type-{timestamp}'] * 2,
    ('labeller', 'name'): [f'Demo-labeller-{timestamp}'] * 2,
    'status': 'draft',
    'geom': [
        Point(24.5, 60.2),
        Point(25.3, 61.1),
    ]
}, geometry='geom', crs='EPSG:4326')

print(f"Target environment: {target_environment}, rows to save: {len(features_only)}")

# confirm with the user before this line runs
try:
    result = client.save_features(features_only)
except (ValidationError, FeatureAPIError) as exc:
    print(f"save_features failed: {exc}")
else:
    print(result)  # {'ids': [...], 'total': 2, 'created': 2, 'errors': [], 'reference_data_created': {...}}
    if result['errors']:
        print(f"Rows rejected: {result['errors']}")
```

Key behaviors:
- Multi-index columns matching a reference type (`satellite`, `featureType`, `modelVersion`,
  `labeller`, `tags`, `productFile`, `visualisationFile`, `batch`) are saved first and their IDs are
  linked automatically; rows that already carry flat IDs (`featureTypeId`, ...) skip creation. Prefer
  this pattern over manual `create_*` calls.
- Batching is sized by bytes, not a fixed row count: `save_features` splits into batches capped at
  `max_batch_features` (constructor default 5000 rows) and further shrunk to fit under
  `max_batch_bytes` (constructor default 25 MB of serialized JSON), whichever is smaller for the
  measured geometry size. Override per call with `save_features(gdf, batch_size=..., max_batch_bytes=...)`.
  Each batch is its own transaction; a failed batch stops the run and reports how many features earlier
  batches already committed.
- Timestamps are converted to UTC ISO strings automatically; numpy scalars are converted too.
- For reference data, an existing `(ref_type, 'id')` value is reused as-is and skips re-creation
  (confirmed in the client's reference-resolution code). For the features themselves, `save_features`
  always POSTs to create new rows; the client has no update/upsert path for a feature that already
  carries its own `id` (only `update_usage_right` exists for a reference type, not for features). A
  round-trip pattern (`get_features` -> modify -> `save_features`) may therefore create duplicate
  feature rows rather than updating them; this is not settled by the client source, so tell the user
  directly and test against dev first before relying on it.

## Comprehensive Example With All Metadata

The client passes reference-data dictionaries through to the service largely unchanged, so beyond the
required columns and the reference-type names above, the exact field names each table accepts are
defined by the service schema, not enforced in the client source. Treat field names below as
illustrative; confirm an unfamiliar one against `get_*()` output or the service administrator before
relying on it.

```python
import time
from datetime import datetime

import geopandas as gpd
from shapely.geometry import Point

# Create a timestamp for unique reference-data names.
timestamp_complete = int(time.time())

# Comprehensive DataFrame with ALL possible tables and columns
complete_features = gpd.GeoDataFrame({
    # ============================================================================
    # SATELLITES
    # ============================================================================
    ('satellite', 'name'): [f'Complete-Sat-{timestamp_complete}'] * 2,
    ('satellite', 'description'): ['Complete satellite example'] * 2,
    ('satellite', 'programCode'): ['DEMO'] * 2,
    # Note: operationalPeriod and archivePeriod are complex types (DATERANGE)
    # They are not typically set via DataFrame but can be set via direct API calls

    # ============================================================================
    # TAGS (t_tags)
    # ============================================================================
    ('tags', 'name'): [['validation', 'test'], ['production']],
    ('tags', 'description'): [['Validation tag', 'Test tag'], ['Production tag']],

    # ============================================================================
    # FEATURE TYPES
    # ============================================================================
    ('featureType', 'name'): [f'Complete-Type-{timestamp_complete}'] * 2,
    ('featureType', 'description'): ['Complete feature type'] * 2,
    # Tags are linked to feature types via REFERENCE_DATA_DEPENDENCIES

    # ============================================================================
    # MODEL VERSIONS
    # ============================================================================
    ('modelVersion', 'algorithm'): ['RandomForest', 'XGBoost'],
    ('modelVersion', 'version'): ['v2.1.0', 'v1.5.3'],
    ('modelVersion', 'notes'): ['Updated model', 'Stable release'],
    # Optional fields not in multi-index (set via properties or direct API):
    # - trainingDate, parameters (JSONB), metrics (JSONB)

    # ============================================================================
    # LABELLERS
    # ============================================================================
    ('labeller', 'name'): [f'Complete-Labeller-{timestamp_complete}'] * 2,
    ('labeller', 'labellerType'): ['model', 'human'],
    ('labeller', 'organization'): ['Demo Org', 'Demo Org'],
    ('labeller', 'email'): ['demo@example.com', 'human@example.com'],
    ('labeller', 'reference'): ['model-v2', 'annotator-001'],
    # metadata is JSONB - can be set via properties column

    # ============================================================================
    # PRODUCT FILES (t_productFiles)
    # ============================================================================
    # Product files are linked to satellites via satId (handled automatically)
    ('productFile', 'filename'): [
        f'complete-{timestamp_complete}-1.nc',
        f'complete-{timestamp_complete}-2.nc'
    ],
    ('productFile', 'filepath'): [
        f'/data/complete-{timestamp_complete}-1.nc',
        f'/data/complete-{timestamp_complete}-2.nc'
    ],
    ('productFile', 'collection'): ['complete_collection'] * 2,
    ('productFile', 'serviceReference'): [
        's3://bucket/file1.nc',
        's3://bucket/file2.nc'
    ],

    # ============================================================================
    # VISUALISATION FILES
    # ============================================================================
    ('visualisationFile', 'filename'): [
        f'complete-{timestamp_complete}-1.png',
        f'complete-{timestamp_complete}-2.png'
    ],
    ('visualisationFile', 'filepath'): [
        f'/vis/complete-{timestamp_complete}-1.png',
        f'/vis/complete-{timestamp_complete}-2.png'
    ],
    ('visualisationFile', 'serviceReference'): [
        'https://viz.example.com/1.png',
        'https://viz.example.com/2.png'
    ],
    ('visualisationFile', 'createdBy'): ['pipeline-v1', 'pipeline-v1'],
    # Optional fields (complex types):
    # - spatialExtent (geometry)
    # - metadata (JSONB)

    # ============================================================================
    # FEATURES
    # ============================================================================
    # Temporal information (REQUIRED)
    'observationStartTime': [
        datetime(2023, 6, 15, 10, 30, 0),
        datetime(2023, 6, 16, 14, 45, 0)
    ],
    'observationEndTime': [
        datetime(2023, 6, 15, 11, 0, 0),
        datetime(2023, 6, 16, 15, 15, 0)
    ],

    # Quality metrics
    'confidence': [0.95, 0.88],
    'quality_score': [0.92, 0.85],
    # qualityFlags is JSONB - set via properties if needed

    # Review status
    'status': ['validated', 'draft'],
    # reviewedBy, reviewedAt can be set via properties or direct updates

    # Properties (JSONB) - flexible field for feature-specific data
    'properties': [
        {'area_km2': 150.5, 'perimeter_km': 50.2, 'custom_field': 'value1'},
        {'area_km2': 200.3, 'perimeter_km': 60.1, 'custom_field': 'value2'}
    ],

    # Geometry (REQUIRED)
    'geom': [
        Point(24.5, 60.2),
        Point(25.3, 61.1)
    ]
}, geometry='geom', crs='EPSG:4326')

print(f"Complete DataFrame created with {len(complete_features)} rows")
print(f"Total columns: {len(complete_features.columns)}")
print(f"\nMulti-index columns by reference type:")
ref_types = {}
for col in complete_features.columns:
    if isinstance(col, tuple):
        ref_type = col[0]
        if ref_type not in ref_types:
            ref_types[ref_type] = []
        ref_types[ref_type].append(col[1])

for ref_type, fields in sorted(ref_types.items()):
    print(f"  {ref_type}: {', '.join(fields)}")

```
