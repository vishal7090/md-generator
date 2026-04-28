# Changelog — `ai/`

All versions align with **mdengine** package versioning in `pyproject.toml` unless noted.

## 0.7.0 — 2026-04-28

- Bootstrap `ai/` tree: `README.md`, `global/` (`AGENT.md`, `SKILL.md`, `reference.md`), and `modules/*` for each top-level package under `src/md_generator/` (`archive`, `codeflow`, `db`, `graph`, `image`, `media`, `openapi`, `pdf`, `playwright`, `ppt`, `text`, `url`, `word`, `xlsx`).
- **Consumer focus:** Reworked `README`, `global/*`, and all `modules/*` to target teams using **`pip install mdengine[...]`** (console scripts, extras, `md_generator.*` imports, APIs/MCP). Monorepo paths like `src/md_generator/...` are no longer the primary frame; skills are meant to be **shared without binding** upstream source into other teams’ AI tools.
- **Layout:** Replaced `global/` + `modules/<area>/` with **`ai/agents/`** (named `mdengine-*-agent.md`) and **`ai/skills/`** (named `mdengine-ai-*.md`, plus `mdengine-reference.md`). Cross-links updated.
- **Skills layout:** Each skill is a folder **`skills/<name>/`** containing **`SKILL.md`** and **`references/example.md`** (copy-paste install + CLI examples). Flat `*.md` files under `skills/` removed.
- **`registry.json`:** Added at `ai/registry.json` — maps skill and agent ids to relative paths and agent↔skill pairing for host integration.
- **Full functionality docs:** `skills/mdengine-reference/references/entrypoints.md` (all console scripts from `pyproject.toml`) and `http-api-mcp.md` (REST job pattern, Uvicorn targets, `md-db-api` / graph / openapi / media routes, MCP tools & transports, env prefixes — from README). Linked from `mdengine-reference/SKILL.md`, `mdengine-ai-global/SKILL.md`, and area skills’ **APIs / MCP** sections.
