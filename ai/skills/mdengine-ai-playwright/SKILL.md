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

If this area ships `*-api` or `*-mcp` scripts, install the matching **`api`** / **`mcp`** extras and read **`--help`** or the upstream README for ports, routes, and tool names.

## See also

- Global install and extras summary: [Global skill](../mdengine-ai-global/SKILL.md)
- CLI cheat sheet: [CLI reference](../mdengine-reference/SKILL.md)
