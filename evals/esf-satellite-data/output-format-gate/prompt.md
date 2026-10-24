---
name: output-format-gate
description: ESF satellite dataset planning must ask for output format before choosing stream, conversion or download access routes. Fixture: esf MCP is connected and the feature type is already confirmed; classification and output format are still open.
tags: [esf-satellite-data, routing, format-gate]
runs: 3
max_turns: 8
timeout_seconds: 300
---

The esf MCP tools are connected, and we already confirmed the feature type (deep convective systems)
and its identity key in an earlier turn. Now build me a satellite imagery dataset, balanced across
weak, moderate, severe and extreme classes, across Europe in 2024. Keep it efficient and under 10 TB.
