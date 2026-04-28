---
name: mdengine-ai-pdf
description: >-
  Documents pip-installed mdengine features for PDF → Markdown: extras, CLIs, and
  public imports under md_generator.pdf. Use when the user mentions md-pdf, pymupdf, pdfplumber, md_generator.pdf
  or needs this capability after installing mdengine from PyPI.
version: 0.7.0
---

# mdengine — PDF → Markdown


## Examples

Concrete commands: [references/example.md](references/example.md).

## Install

```bash
pip install "mdengine[pdf]"
```

(Adjust extras in the `pip install` line to match the features you need.)

## Primary entry points

- **CLI:** `md-pdf`
- **Library:** Package: `md_generator.pdf`.

Use **`--help`** on each CLI for flags. Prefer CLIs for automation unless you are embedding Python APIs described in the upstream README.

## Capabilities

- Extract text and layout-oriented Markdown from PDFs; artifact layouts and tuning via CLI flags.

## APIs / MCP

FastAPI apps, **`/convert/sync`** job pattern, MCP on **`/mcp`**, and standalone MCP module invocations for this format are listed in [http-api-mcp.md](../mdengine-reference/references/http-api-mcp.md). Install **`mdengine[api,mcp]`** plus this area's extra; use **`--help`** on the API process you start.

## See also

- Global install and extras summary: [Global skill](../mdengine-ai-global/SKILL.md)
- CLI cheat sheet: [CLI reference](../mdengine-reference/SKILL.md)
