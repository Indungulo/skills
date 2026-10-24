# Behavior cases

Each directory under `evals/<skill>/<mechanism>/` contains a prompt and graders for one observable behavior. Case names identify the mechanism; product names belong in the fixture. These are evaluation inputs, not records of a passing run.

`skills-bench` is not publicly available yet; see [validation](../docs/validation.md). Maintainers run these
cases with an available installation. For a small explicit run:

```bash
skills-bench eval evals/firecube --skills-repo . --driver codex --model gpt-5.5 --runs 1
```

Agent-backed evaluations use your configured model account and may incur costs. Inspect the cases and authorize the run budget first. Use isolated fixtures and prohibit live downloads or infrastructure changes when those are outside the scenario.

The existing Firecube cases cover known-plugin selection, template evidence, data acquisition boundaries, derived views, and public hooks. The other skills each have a focused boundary case. Preserve raw results separately from the distributed skill bundle and distinguish successful behavior from failed or unscored runs.
