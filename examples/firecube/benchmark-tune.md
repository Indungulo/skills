# Benchmark And Tune An Ingestion

## Prompt

```text
My ingestion is slow. Help me benchmark it and tune batch size and parallelism.
```

## Expected Agent Behavior

- Route to `performance.md`.
- Ask for the current command, plugin, input size, target storage type, and machine resources before recommending values.
- Use `firecube advise batch-size` and `firecube advise compliance` with flags verified against their `--help`; both are read-only.
- Describe a reproducible benchmark: same input subset, same target type, one variable changed at a time, wall time and throughput recorded per run.
- Do not quote specific throughput numbers as expectations. The published benchmarks are examples on specific hardware, linked from the reference.
- Present tuning knobs in order of likely impact for the user's setup: batch size, slot-range parallelism, storage driver, write mode, S3 settings.
- Suggest enabling metrics or traces only if the user wants measurement detail, and mark that as optional.

## Safe Command Pattern

```bash
firecube advise batch-size --help
firecube advise compliance --help
firecube zarr slots --help
```

## Safe Response Shape

```text
Workflow type: performance
Prerequisites: a repeatable input subset, the current ingest command, target storage type, CPU and memory available
Safety boundary: advise commands are read-only; benchmark runs write to a scratch target the user chooses
Validation status: advise help inspected; no benchmark run
```
