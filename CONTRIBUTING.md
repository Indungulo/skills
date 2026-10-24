# Contributing

Thank you for contributing to EUMETSAT Agent Skills.

This repository accepts contributions through merge requests. This document
describes how to prepare a focused change, run the right checks, and get it
reviewed.

Please review and follow the [Code of Conduct](CODE_OF_CONDUCT.md).

## What A Contribution Is

Almost everything here is natural-language instruction for coding agents:
`skills/<name>/SKILL.md` and the `references/` beside it. A contribution is
usually a corrected fact, a missing boundary, a new reference page, or a
behaviour case under `evals/`. Read [AGENTS.md](AGENTS.md) for the structure
rules and [docs/skill-reference-boundaries.md](docs/skill-reference-boundaries.md)
for what belongs in `SKILL.md` and what belongs in a reference.

The firecube skill ships three helper scripts under `skills/firecube/scripts/`.
They are conveniences that accompany the skill, each documented in that
directory's README, and are not a software product. Changes to them follow the
same process as changes to the prose, plus the lint check below.

## Prerequisites

No build is needed to edit a skill. To run the validation cases or the helper
scripts you need Python 3.12, `uv`, and the tool the skill targets (`eumdac`,
`ewccli`, `firecube`) installed in an environment you control; see
[docs/validation.md](docs/validation.md).

## Branches And Scope

Create one branch per logical change. Use a short, conventional prefix:

```text
feat/
fix/
docs/
test/
refactor/
chore/
```

Keep merge requests focused. One skill per change unless the change is a rule
that spans all of them.

## Writing Rules

- Every fact about a tool is checked against the installed tool's `--help`,
  its source, or its official documentation before it goes in. Say which.
  A version-specific fact names the version.
- Keep `SKILL.md` concise. Detail, tables and worked examples go into
  `references/`; `SKILL.md` points at them.
- A rule is for the agent, not the end user: state what to do, not what the
  agent is forbidden to narrate.
- Commands are complete and runnable as written, with long flags spelled out.
- Do not add credentials, tokens, internal hostnames, or personal data. The
  skills describe how to obtain access; they never contain it.
- A performance or capacity number carries its measurement: machine, command,
  scale. Never extrapolate from a sample.

## Checks

For a prose change, run the behaviour cases that touch the skill you changed,
as described in [docs/validation.md](docs/validation.md), and record the result
in the merge request.

For a change to the helper scripts:

```bash
uv run --with ruff ruff check skills/firecube/scripts
```

`ruff.toml` at the repository root selects the rules. Then run the changed
script once against a real plugin and paste its output into the merge request.

## Merge Request Checklist

Before opening a merge request:

```bash
git status --short
git diff --stat
git diff --check
```

Use the description to explain:

- what changed;
- why it changed, with the evidence (help output, source line, documentation page);
- which skill and which agent behaviour is affected;
- which checks or cases you ran;
- any known follow-up work.

Add a line under `[Unreleased]` in [CHANGELOG.md](CHANGELOG.md) for any change
a user of the skills would notice.

Do not include local virtual environments, caches, downloaded products, logs,
credentials, or scratch directories in a merge request.

## Sign Your Work

Sign every commit with your real name and a reachable email address. The
sign-off is a line at the end of the commit message certifying that you wrote
the contribution or otherwise have the right to submit it under this
repository's licences.

If your Git identity is configured, `git commit -s` adds the sign-off
automatically:

```bash
git config --global user.name "Jane Smith"
git config --global user.email "jane.smith@example.com"
git commit -s -m "fix(firecube): correct the list option syntax"
```

The commit log should include matching author and sign-off identity:

```text
Author: Jane Smith <jane.smith@example.com>
Date:   Thu Feb 2 11:41:15 2026 +0000

fix(firecube): correct the list option syntax

Signed-off-by: Jane Smith <jane.smith@example.com>
```

## AI-Assisted Contributions

These skills are written for AI agents, and AI tools may help draft or review a
change. The contributor remains responsible for the submitted work: review
every change yourself, verify every tool fact against the installed tool, run
the relevant checks, and be ready to explain the change.

If AI assistance materially shaped the change, disclose that in the merge
request description and record it with an `Assisted-by` trailer in the commit
message. Keep your own `Signed-off-by` line as the final certification that you
have the right to submit the work.

```bash
git commit -s -m "docs(firecube): add the hook order table

Assisted-by: GitHub Copilot <copilot@github.com>"
```

## Commit Messages

Use clear conventional-commit-style subjects, scoped by skill where one applies:

```text
feat(eumdac): add Data Tailor chain examples
fix(firecube): correct the list option syntax
docs: add contributing guide
test(ewccli): cover profile switching
chore: regenerate SBOM artifacts
```

Each commit should represent one logical unit. Maintainers may squash or ask
for cleanup before merge.

## Licensing Of Contributions

By contributing you agree that your contribution is licensed under the
licence that covers the part of the repository you change: the skill content
under CC BY 4.0 ([LICENSE](LICENSE)), the helper scripts under the MIT licence
([LICENSE-MIT](LICENSE-MIT)). See [README.md](README.md#copyright-and-license) for which
applies where. Add yourself to [AUTHORS.md](AUTHORS.md) with your first
substantial contribution if you wish to be listed.
