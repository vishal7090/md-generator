---
name: mdengine-reference
description: >-
  Quick CLI versus extras mapping for mdengine after pip install.
  Use when matching commands (md-pdf, md-db, …) to pip extras.
version: 0.7.0
---

# mdengine — CLI and import reference (installed package)

Supplements [mdengine-ai-global/SKILL.md](../mdengine-ai-global/SKILL.md). Console scripts come from `[project.scripts]` in the installed distribution.

## CLI ↔ typical extras

| Command | Suggested `pip install` |
|---------|-------------------------|
| `md-pdf` | `mdengine[pdf]` |
| `md-word` | `mdengine[word]` |
| `md-ppt` | `mdengine[ppt]` |
| `md-xlsx` | `mdengine[xlsx]` |
| `md-image` | `mdengine[image]` or `[image-ocr]` |
| `md-text` | `mdengine[text]` |
| `md-zip` | `mdengine[archive]` (+ extras for nested formats) |
| `md-url` | `mdengine[url]` or `[url-full]` |
| `md-audio` / `md-video` / `md-youtube` | `mdengine[audio]` / `[video]` / `[youtube]` |
| `md-playwright` | `mdengine[playwright]` then `playwright install chromium` |
| `md-db` / `md-db-api` / `md-db-mcp` | `mdengine[db]` (+ `api` / `mcp` as needed) |
| `md-graph` / `*-api` / `*-mcp` | `mdengine[graph]` |
| `md-openapi` / `*-api` / `*-mcp` | `mdengine[openapi]` |
| `md-codeflow` / `codeflow` / `*-api` / `*-mcp` | `mdengine[codeflow]` (+ optional treesitter/clang extras) |
| `mdengine` | meta-router CLI |

## Python import root

All library code lives under **`md_generator`** (e.g. `md_generator.pdf`, `md_generator.db`, …). Prefer public CLIs and documented APIs in the upstream README when unsure.


## Examples

Concrete commands: [references/example.md](references/example.md).
