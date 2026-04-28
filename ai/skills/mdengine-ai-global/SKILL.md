---
name: mdengine-ai-global
description: >-
  Teaches use of the mdengine PyPI package after pip install: optional extras,
  console scripts (md-pdf, md-url, md-db, …), FastAPI and MCP entry points, and
  Python imports under md_generator. Use when the user installed mdengine from
  pip, asks how to convert formats to Markdown, which extras to pick, or how to
  call HTTP/MCP services — not when navigating a specific git clone of the
  upstream repository.
version: 0.7.0
---

# mdengine — global skill (pip-installed library)


## Examples

Concrete commands: [references/example.md](references/example.md).

## Install

```bash
pip install "mdengine[pdf,word]"   # pick extras you need; see table below
python -c "import md_generator; print('ok')"
```

Python **3.10+**. Distribution name on PyPI: **`mdengine`**. Import package: **`md_generator`**.

### Optional extras (summary)

| Extra | Enables |
|-------|---------|
| `pdf` | PDF → Markdown (`md-pdf`) |
| `word` | DOCX → Markdown (`md-word`) |
| `ppt` | PPTX → Markdown (`md-ppt`) |
| `xlsx` | Excel/CSV → Markdown (`md-xlsx`) |
| `image` / `image-ocr` | Raster OCR (`md-image`) |
| `text` | TXT / JSON / XML (`md-text`) |
| `archive` | ZIP extraction pipeline (`md-zip`) |
| `url` / `url-full` | URL → Markdown (`md-url`; `url-full` adds post-convert for downloads) |
| `audio` / `video` / `youtube` | Media transcription / YouTube (`md-audio`, `md-video`, `md-youtube` + APIs/MCP) |
| `playwright` | Headless browser capture (`md-playwright` + API/MCP); run `playwright install chromium` |
| `db` | DB metadata → Markdown (`md-db`, `md-db-api`, `md-db-mcp`) |
| `graph` | Neo4j / NetworkX → Markdown (`md-graph`, …) |
| `openapi` | OpenAPI → docs (`md-openapi`, …) |
| `codeflow` | Code → architecture Markdown (`md-codeflow`, …); optional `codeflow-treesitter`, `codeflow-clang` |
| `api` / `mcp` | Shared HTTP / MCP stacks where those entry points exist |
| `all` | Large superset — avoid unless truly needed |

Full matrix and behavior: upstream **README** on PyPI / repository.

## Command-line tools

Every installed command exposes **`--help`**. Common pattern:

```bash
md-pdf input.pdf output.md
md-url https://example.com/page ./out --artifact-layout
```

Aggregated **`mdengine`** CLI routes subcommands (e.g. `mdengine db-to-md …`, `mdengine graph-to-md …`, `mdengine openapi-to-md generate …`). Prefer **`md-*`** aliases when documented for your scenario.

See [CLI reference](../mdengine-reference/SKILL.md) for CLI ↔ extra mapping. That skill also ships **[entrypoints.md](../mdengine-reference/references/entrypoints.md)** (all `project.scripts`) and **[http-api-mcp.md](../mdengine-reference/references/http-api-mcp.md)** (REST patterns, `md-db-api` / graph / openapi / media routes, MCP tools, env prefixes).

## HTTP APIs and MCP

Many areas ship **FastAPI** apps (`*-api` scripts) and **MCP** servers (`*-mcp`). Default ports and routes vary by area — check **`--help`** on the installed script or upstream README for `POST` paths, SSE jobs, and MCP tool names.

## Area-specific skills

For deep behavior (flags, APIs, ports), open the matching **sibling folder**, e.g. [PDF](../mdengine-ai-pdf/SKILL.md), [DB](../mdengine-ai-db/SKILL.md), … (`skills/mdengine-ai-<area>/SKILL.md`).

## Contributors (optional)

If you maintain **mdengine** from a git clone, editable install and tests live in the upstream repository — they are **out of scope** for consumer-focused skills. Do not treat `src/...` paths as requirements for end users.

## Additional resources

- [CLI reference](../mdengine-reference/SKILL.md) — CLI and import cheat sheet + full **entrypoints** / **HTTP+MCP** reference files
