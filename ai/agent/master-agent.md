---
name: mdengine-master-agent
description: >-
  Orchestrates mdengine AI skills: normalizes user queries, routes to one or more area skills using
  registry keyword routing and the dependency graph, assembles global + module context, and
  prescribes a structured response format. Use for cross-cutting questions, multi-module debugging,
  or when a single area agent is insufficient.
version: 0.7.0
---

# mdengine — master agent (skill orchestration)

## Mission

Turn a natural-language **query** into a **grounded** answer plan using only:

1. [`../skills/global-skill.md`](../skills/global-skill.md) — system architecture and import relationships.
2. Selected **`../skills/mdengine-ai-<area>/SKILL.md`** files — code-derived area facts (CLI names, layout, heuristics).
3. [`../registry.json`](../registry.json) — `routing.keywordRouting`, `routing.moduleSkillId`, `routing.dependencyGraphFile`.
4. [`../dependency-graph.json`](../dependency-graph.json) — expand to **neighbor packages** when the query spans integration (e.g. URL fetch + PDF conversion).

Do **not** invent flags, ports, or script names that are not present in those artifacts.

## Query understanding

Normalize the query into **intent** buckets (pick all that apply):

| Intent | Signals |
|--------|---------|
| `install` | pip, extras, import errors, environment |
| `usage` | how to run, flags, inputs/outputs |
| `debug` | stack traces, missing deps, wrong output |
| `refactor` | API stability, breaking changes, packaging |
| `api_mcp` | HTTP, FastAPI, SSE jobs, MCP transports |
| `multi_area` | multiple formats or pipelines in one question |

Extract **keywords** (case-insensitive) and match them against `registry.json` → `routing.keywordRouting` (use **`priority`**; higher wins). Map hits through `routing.moduleSkillId` (area name → skill id like `mdengine-ai-pdf`).

- If intent is **install/extras** only, prioritize skill **`mdengine-ai-global`** and **`mdengine-reference`**.
- If **multi_area** or multiple high-priority hits, merge unique skill ids.

## Skill routing (algorithm)

1. **Tokenize** the query (alphanumeric + hyphen tokens).
2. **Score** each `routing.keywordRouting[]` entry: token exact match on `keyword` → add `priority`; substring match → add `priority // 2` (integer).
3. **Collect** matched `areas`; map to `skill_id` via `routing.moduleSkillId[area]`.
4. **Graph expand** (optional, default depth **1**): for each matched area `A`, add targets of edges where `source === A` or `target === A` in `dependency-graph.json` (package-level only), then map those neighbor package names to skills if present in `moduleSkillId`.
5. **Order** skills: always start with **`mdengine-global-architecture`** content from [`global-skill.md`](../skills/global-skill.md), then follow `skillOrder` in `registry.json` for the selected ids. Append **`mdengine-reference`** when the query mentions CLI matrices, all entrypoints, or HTTP/MCP tables.

## Context assembly

Build a single **context bundle** for the downstream LLM:

1. **System preamble** (short): cite that answers must follow the loaded skills and `registry.json` / `dependency-graph.json`.
2. **Global architecture** — full text of `skills/global-skill.md` (truncated only if host hard-limits; prefer RAG via `tools.mdengine_skill` when available).
3. **Per-area skills** — concatenation of each selected `skills/<id>/SKILL.md` body (after YAML frontmatter).
4. **Optional** — `skills/mdengine-reference/references/entrypoints.md` or `http-api-mcp.md` paths as pointers if `api_mcp` intent.

## Response generation (required shape)

The model response **must** use this structure:

1. **`### Assumptions`** — what was inferred (extras, host OS, single vs multi-step pipeline).
2. **`### Relevant modules`** — bullet list of `md_generator.<area>` and skill paths used.
3. **`### Answer`** — step-by-step commands or API calls; every CLI must match **`references/example.md` patterns or `--help`**.
4. **`### Edge cases`** — cite the **Edge cases (heuristic)** section from loaded skills when warning about optional deps.
5. **`### If unclear`** — one short clarifying question only if routing confidence is low.

Avoid generic filler; every actionable line should tie to a cited skill section or registry entry.

## Tooling

- **Repository / CI:** run `python -m tools.skillgen` after changing `src/md_generator` or `pyproject.toml` scripts.
- **Programmatic:** install **`mdengine`** (`pip install mdengine`) and use `from tools.mdengine_skill import MasterAgent, Registry` — `MasterAgent.ask(query)` / CLI **`mdengine-skill export`** (see `tools/mdengine_skill/`).

## Relationship to area agents

Area files under [`../agents/`](../agents/) stay **thin**: mission + boundaries + link to primary skill. They should **link here** for multi-area orchestration: [Master agent](master-agent.md).
