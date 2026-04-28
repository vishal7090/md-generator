---
name: mdengine-ai-playwright
description: >-
  Documents pip-installed mdengine features for Playwright URL → Markdown: extras, CLIs, and
  public imports under md_generator.playwright. Use when the user mentions md-playwright, playwright, SPA, headless, md_generator.playwright
  or needs this capability after installing mdengine from PyPI.
version: 0.7.0
---

# mdengine — Playwright URL → Markdown


## Examples

Concrete commands: [references/example.md](references/example.md).

## Install

```bash
pip install "mdengine[playwright]" && playwright install chromium
```

(Adjust extras in the `pip install` line to match the features you need.)

## Primary entry points

- **CLI:** `md-playwright`, `md-playwright-api`, `md-playwright-mcp`
- **Library:** Package: `md_generator.playwright`.

Use **`--help`** on each CLI for flags. Prefer CLIs for automation unless you are embedding Python APIs described in the upstream README.

## Capabilities

- Render SPA pages and convert to Markdown with tunable waits and chunking.
- Optional HTTP and MCP automation.

## APIs / MCP

`md-playwright-api` (default **8014** / `PLAYWRIGHT_TO_MD_API_PORT`), `md-playwright-mcp`, HTTP MCP mount **`/mcp`**, and env prefix `PLAYWRIGHT_TO_MD_*`: [http-api-mcp.md](../mdengine-reference/references/http-api-mcp.md).

## See also

- Global install and extras summary: [Global skill](../mdengine-ai-global/SKILL.md)
- CLI cheat sheet: [CLI reference](../mdengine-reference/SKILL.md)
