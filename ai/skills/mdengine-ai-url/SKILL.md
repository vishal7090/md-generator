---
name: mdengine-ai-url
description: >-
  Documents pip-installed mdengine features for URL (HTML) → Markdown: extras, CLIs, and
  public imports under md_generator.url. Use when the user mentions md-url, html to markdown, readability, md_generator.url
  or needs this capability after installing mdengine from PyPI.
version: 0.7.0
---

# mdengine — URL (HTML) → Markdown


## Examples

Concrete commands: [references/example.md](references/example.md).

## Install

```bash
pip install "mdengine[url]"  # or mdengine[url-full]
```

(Adjust extras in the `pip install` line to match the features you need.)

## Primary entry points

- **CLI:** `md-url`
- **Library:** Package: `md_generator.url`.

Use **`--help`** on each CLI for flags. Prefer CLIs for automation unless you are embedding Python APIs described in the upstream README.

## Capabilities

- Fetch and readability-style extraction to Markdown bundles.
- Optional deep conversion of linked assets with `url-full`.

## APIs / MCP

URL FastAPI follows the shared **`/convert/sync`** job pattern (JSON `url` / `urls`); MCP via `python -m md_generator.url.api.mcp_server`; env prefix `URL_TO_MD_*`: [http-api-mcp.md](../mdengine-reference/references/http-api-mcp.md). See **url-to-md** README for request bodies.

## See also

- Global install and extras summary: [Global skill](../mdengine-ai-global/SKILL.md)
- CLI cheat sheet: [CLI reference](../mdengine-reference/SKILL.md)
