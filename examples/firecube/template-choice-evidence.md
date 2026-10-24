# Template Choice Without A Product File

## Prompt

```text
How do I create a Firecube plugin for <collection-id>? Which template should I use?
```

## Expected Agent Behavior

- Route to `plugin-development.md`; check the known public plugins table first, then apply "Evidence Required First".
- Do not infer the data shape from the collection ID, title, catalogue abstract, product filename, SIP or manifest listing, packaging, instrument, processing level, or a tutorial for another collection.
- Do not search the user's disks. Ask whether they have a product and where, or offer the `eumdac` skill for obtaining one or two granules, including one where the retrieval is expected to be present.
- Ask in plain terms what they will do with the product; do not expect them to name Parquet or Zarr. Ask what they already know about the product before opening any document; fetch the public collection metadata alongside the files; after inspection, list what two files did not answer and resolve each with the operator, the metadata, or a targeted spec page.
- Before recommending, decide the cube's time unit from the acquisition geometry and separate coverage sparsity from retrieval sparsity. For polar-orbiter swath data the first cube option is granules combined per orbit or half-orbit in native geometry with values untouched; Parquet is for point or event data, and regridding is aggregation that needs the data owner's decision.
- After inspecting a file the user supplied or authorised, recommend one template with the reason, name the alternative in one line, and ask whether to proceed. The user's choice is final; state implications of a mismatch once.
- Ask about the goal with a structured question when available (analysis pattern, time step, variables, scale), and ask again at each later decision point, including after explaining a constraint; offer the next step, the alternatives, and "something else" rather than closing with a yes-or-no sentence. Give the reasoning for and against each option and what would flip it; do not deliver a one-line verdict. No code blocks before the user has chosen. Do not explain the skill's rules or list what was not done.
- Skills and examples must not carry product-specific layout facts (dimensions, variable names, valid fractions). Those belong to the inspection at hand, not to the skill.

## Failures This Example Guards Against

- Reading the full product user guide instead of asking for data, recommending the append template because the operator said "test cube", staying silent for minutes on a long step, running a download from this skill instead of handing off to the `eumdac` skill, and keeping every decision only in the transcript instead of the plan file. The Plugin Design Procedure, the progress-line rule, the hand-off rule, and the plan file guard against exactly this.

- Running `plugins create --non-interactive` with an invented author, email, and licence, and without a confirmed design summary, right after the user picked the template. Identity and licence are the user's to give; the summary is theirs to confirm.

- Recommending a template from the collection abstract and a tutorial for a neighbouring product, with placeholder variable names presented as if known.
- Searching the user's home directories for a product without asking.
- Refusing to recommend after inspection, restating the skill's rules at length, and printing commands the user could not yet run.
- Concluding "swath with 2-D coordinates, varying shape, sparse retrievals, therefore rows": the time step was silently set to the granule, coverage sparsity was mistaken for a data property, and the only cube alternative offered was a regridded one. A data owner overruled it with a per-orbit native-geometry Zarr cube.
- Writing the inspected product's dimensions and variables into the skill, so later sessions answered from stale, product-specific text instead of the user's data.

## Safe Response Shape

```text
Question (structured): what will you do with the product; which time step; which variables; one-off or operational?
Recommendation: <template>, because <reasons from the inspected files and the stated goal>.
Why not <alternative>: <what it loses for this goal>; it becomes the better choice if <condition>.
What would change this: <the answer or finding that flips it>.
```
