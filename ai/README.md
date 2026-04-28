# mdengine — distributable AI agents & skills

These folders are meant to be **copied or packaged for other teams**. They describe how to use the **`mdengine`** distribution **after `pip install`** — console scripts, extras, imports under **`md_generator`**, HTTP APIs, and MCP — **without requiring this repository’s source tree.**

## Layout

### Skills (`skills/`)

Each capability has its **own folder** with a fixed shape:

```text
skills/<skill-folder>/
  SKILL.md              # YAML frontmatter + instructions (what hosts usually load)
  references/
    example.md          # Copy-paste examples (install + CLI snippets)
```

| Folder | Role |
|--------|------|
| [`skills/mdengine-ai-global/`](skills/mdengine-ai-global/) | Global skill — install, extras, CLI overview |
| [`skills/mdengine-reference/`](skills/mdengine-reference/) | CLI ↔ extra cheat sheet |
| [`skills/mdengine-ai-<area>/`](skills/) | Area skills: `archive`, `codeflow`, `db`, … — same pattern |

Bind **`SKILL.md`** in your AI tool; point contributors to **`references/example.md`** for runnable snippets.

### Agents (`agents/`)

| Path | Role |
|------|------|
| [`agent/master-agent.md`](agent/master-agent.md) | **Master agent** — query routing, registry keywords, dependency-graph expansion, structured responses |
| [`agents/mdengine-global-agent.md`](agents/mdengine-global-agent.md) | Global agent profile |
| [`agents/mdengine-<area>-agent.md`](agents/) | Area agent — links to `../skills/mdengine-ai-<area>/SKILL.md` |

### Naming

- **Skill folders:** `mdengine-ai-<area>` (matches YAML `name:` e.g. `mdengine-ai-pdf`).
- **Agents:** `mdengine-<area>-agent.md` (matches YAML `name:`).

Hosts that require `skill-name/SKILL.md` only need each **`skills/<folder>/`** directory as-is.

### Registry ([`registry.json`](registry.json))

Machine-readable map of **skill ids** → `skillFile`, `exampleFile`, `directory`, and **agent ids** → `file` + `pairedSkill`. Use it to wire external AI hosts, code generators, or CI checks without hardcoding paths.

- **`schemaVersion`:** format of this file; bump when fields change.
- **`bundleVersion`:** should track the **mdengine** skills bundle (align with `mdengine` on PyPI when practical).
- **`skills`:** keyed by YAML `name` in each `SKILL.md` (e.g. `mdengine-ai-pdf`).
- **`referenceDocuments`** (optional, on `mdengine-reference`): every markdown file under `references/` for hosts that bundle **CLI + HTTP + MCP** docs (`entrypoints.md`, `http-api-mcp.md`, `example.md`).
- **`agents`:** keyed by YAML `name` in each agent file; `pairedSkill` links to a `skills` key.
- **`skillOrder`:** stable ordered list for UIs or batch registration.

### Schema 1.1.0 — routing and dependency graph

From **`schemaVersion` `1.1.0`**, [`registry.json`](registry.json) may include a top-level **`routing`** object used by the skill generator, the bundled SDK at [`../tools/mdengine_skill/`](../tools/mdengine_skill/) (import **`tools.mdengine_skill`**; console script **`mdengine-skill`** from **`pip install mdengine`**), and orchestration docs:

| Field | Meaning |
|-------|---------|
| **`globalSkillFile`** | Path relative to `ai/` for the system-level architecture skill (e.g. `skills/global-skill.md`). |
| **`dependencyGraphFile`** | Path relative to `ai/` for [`dependency-graph.json`](dependency-graph.json): `md_generator` top-level packages as **nodes**, import edges as **`edges`** (`source`, `target`, `weight`). |
| **`moduleSkillId`** | Map logical **area** name (package basename) → **`skills`** registry key (`mdengine-ai-pdf`, …). |
| **`keywordRouting`** | List of `{ "keyword", "areas", "priority" }` for query → area resolution (higher **priority** wins when sorting). |

Regenerate **`dependency-graph.json`**, skill bodies, and routing alignment from the repo with:

`python -m tools.skillgen` (from repository root; see `tools/skillgen/__main__.py`).

## Versioning

Bump **`version`** in each **`SKILL.md`** frontmatter, update **`registry.json`** `bundleVersion` if the bundle changes, and add a note in **[`CHANGELOG.md`](CHANGELOG.md)** when documented CLI flags, extras, or paths change.

## AI-SDLC (consumer teams)

| Phase | Notes |
|-------|--------|
| Discover | Read `skills/mdengine-ai-global/SKILL.md` + area folder |
| Plan | Choose extras: `pip install "mdengine[extra1,extra2]"` |
| Implement | Call CLIs / APIs |
| Verify | Same commands as production; check **references/example.md** |
