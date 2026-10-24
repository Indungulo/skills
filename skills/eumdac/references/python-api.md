# Python API

Use this reference for EUMDAC Python examples.

## Main Classes

Installed `eumdac 3.1.1` exposes:

```python
import eumdac

eumdac.AccessToken(credentials, validity=86400, cache=True)
eumdac.DataStore(token)
eumdac.DataTailor(token)
```

The v3.1.0 API docs describe the main classes as:

```text
AccessToken - manages authentication and provides tokens
DataStore - accesses collections and searches Data Store
Collection - collection metadata and product searching
Product - product metadata and downloading contents
DataTailor - customises Data Store products
```

## Data Store Setup

```python
import eumdac

credentials = ("<consumer-key>", "<consumer-secret>")
token = eumdac.AccessToken(credentials)
datastore = eumdac.DataStore(token)
```

List collections:

```python
for collection in datastore.collections:
    print(f"{collection} - {collection.title}")
```

Get a known collection or product:

```python
collection = datastore.get_collection("<collection-id>")
product = datastore.get_product("<collection-id>", "<product-id>")
```

## Search

Collection search parameters vary by collection. Inspect `collection.search_options` when live credentials/network are available:

```python
collection = datastore.get_collection("<collection-id>")
print(collection.search_options)
```

Search:

```python
results = collection.search(dtstart="2024-01-01", dtend="2024-01-02")
first = results.first()
```

OpenSearch query string:

```python
results = datastore.opensearch("pi=<collection-id>&dtstart=2024-01-01&dtend=2024-01-02")
```

## Product Access

Product objects expose metadata properties such as `sensing_start`, `sensing_end`, `size`, `md5`, `satellite`, `product_type`, `timeliness`, and `entries`.

Stream a whole product or one entry. A single `product.open()` call downloads that product; a loop over several products is a bulk download, so state the count, expected size, and destination, and get the user's confirmation first, the same as the CLI `download` command:

```python
product = datastore.get_product("<collection-id>", "<product-id>")

with product.open() as source, open("<output-file>", "wb") as target:
    target.write(source.read())
```

For package entries:

```python
for entry in product.entries:
    print(entry)

with product.open(entry="<entry-name>") as source, open("<output-file>", "wb") as target:
    target.write(source.read())
```

## Data Tailor API

Use `eumdac.DataTailor(token)` for web-service customisations. Core installed methods/properties include:

```text
customisations
get_customisation(customisation_id)
new_customisation(product, chain)
new_customisations(products, chain)
quota
info
user_info
is_local
```

`DataTailor.new_customisation(product, chain)` and `new_customisations(products, chain)` start an asynchronous remote job, the Python equivalent of `tailor post`. State what will be customised and get the user's confirmation before calling them. Monitor status, download outputs, and clean up finished customisations.

## Validation

Credential-free validation:

```bash
python -c "import eumdac; print(eumdac.__version__)"
python - <<'PY'
import inspect, eumdac
print(inspect.signature(eumdac.AccessToken))
print(inspect.signature(eumdac.DataStore))
print(inspect.signature(eumdac.DataTailor))
PY
```

Live examples require credentials and network access.
