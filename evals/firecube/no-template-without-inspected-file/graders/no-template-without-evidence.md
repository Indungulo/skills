---
type: llm
criteria: "The response does not recommend or choose a Firecube template (GenericZarrIngestor, DirectZarrIngestor, Parquet, zarr, parquet, base) from the collection ID alone. It asks whether the operator has a product on disk and where, or offers obtaining one or two products with the eumdac skill, and asks what the operator will do with the product. It does not search the filesystem for data, does not read a product user guide, and does not print commands the operator cannot run yet."
---

Mechanism: a template recommendation needs an inspected product file. Pass only if no template is recommended before one exists and the response asks for data or the goal instead.
