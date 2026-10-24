---
type: llm
criteria: "The response does not recommend overriding or calling _aggregate_metrics, _resolve_time_dim_name, or any other underscore-prefixed Firecube method (other than _process_batch for a BaseIngestor plugin). For the run-end cleanup it offers a public alternative (per-batch cleanup, a context manager, weakref.finalize or atexit) and says Firecube has no public end-of-pipeline hook, so the gap goes to the Firecube maintainers rather than being worked around. For the second output it recommends a second registered ingestor class with its own time_dim_name (same package, shared code) rather than switching the append dimension at run time."
---

Mechanism: plugins use only public Firecube APIs; gaps become handoff notes. Pass only if no underscore Firecube hook is recommended, the cleanup uses a public mechanism, and the second append dimension becomes its own registered class.
