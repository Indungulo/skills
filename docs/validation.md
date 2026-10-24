# Validation

Run validation before handing off changes, from the repository root, with
an available `skills-bench` installation:

```bash
skills-bench validate . --strict
```

`skills-bench` is not publicly available yet. External contributors can skip it; maintainers run it before
merge. Without it, a contributor can check by hand: frontmatter uses only the specification's fields (`name`, `description`, `license`, `compatibility`, `metadata`), every
reference file is linked from `SKILL.md`, relative links resolve, no credentials or local paths appear
anywhere, and `SKILL.md` stays under 500 lines.

The checks and their thresholds come from `skills-bench.yaml` in this repository (required skills, portable
frontmatter keys, expected reference files per skill, installed-CLI surfaces, and size budgets) on top of
the Agent Skills specification rules (name, description, links). Strict mode fails on errors and warnings,
including size budgets. `--json` gives a machine-readable report, `--no-cli` skips the installed-CLI checks.

Behaviour evals live under `evals/<skill>/<mechanism>/` and run with `skills-bench eval evals/<skill>`; see
`evals/README.md`. End-to-end benchmarks with a scripted operator are not kept in this repository.

Static validation does not call live EUMETSAT, European Weather Cloud, or object storage services and does not require EUMETSAT or EWC credentials.

The installed-CLI checks look for `eumdac`, `ewc`, and `firecube` on `PATH` (a repo-relative path is tried first)
and skip any tool that is absent, so a fresh clone or CI without them still validates. To make a check run, install
the tool so that it is on `PATH`, for example `uv tool install 'eumdac==3.1.1'`, `uv tool install 'ewccli==0.3.1'`,
`uv tool install 'firecube==0.1.7'`; `skills-bench validate .` then prints `[cli ] <name>: passed` per tool.

Run optional helper checks in the target plugin project's environment. See [helper prerequisites](../skills/firecube/scripts/README.md).

## Adding A New EUMETSAT Skill

Create a new folder under `skills/`:

```text
skills/<skill-name>/SKILL.md
```

Skill names should be lowercase kebab-case and must match the folder name. Keep frontmatter portable across Codex, Claude Code, and OpenCode:

```yaml
---
name: <skill-name>
description: Explain what the skill does and when agents should use it.
---
```

Do not use platform-specific frontmatter in shared skills unless the repo intentionally drops cross-agent portability for that skill.
