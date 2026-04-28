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

If this area ships `*-api` or `*-mcp` scripts, install the matching **`api`** / **`mcp`** extras and read **`--help`** or the upstream README for ports, routes, and tool names.

## See also

- Global install and extras summary: [Global skill](../mdengine-ai-global/SKILL.md)
- CLI cheat sheet: [CLI reference](../mdengine-reference/SKILL.md)
