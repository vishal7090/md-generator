---
name: mdengine-ai-xlsx
description: >-
  Documents pip-installed mdengine features for Excel / CSV → Markdown: extras, CLIs, and
  public imports under md_generator.xlsx. Use when the user mentions md-xlsx, excel, openpyxl, csv, md_generator.xlsx
  or needs this capability after installing mdengine from PyPI.
version: 0.7.0
---

# mdengine — Excel / CSV → Markdown


## Examples

Concrete commands: [references/example.md](references/example.md).

## Install

```bash
pip install "mdengine[xlsx]"
```

(Adjust extras in the `pip install` line to match the features you need.)

## Primary entry points

- **CLI:** `md-xlsx`
- **Library:** Package: `md_generator.xlsx`.

Use **`--help`** on each CLI for flags. Prefer CLIs for automation unless you are embedding Python APIs described in the upstream README.

## Capabilities

- Spreadsheets and CSV to Markdown; splitting and layout flags via `--help`.

## APIs / MCP

If this area ships `*-api` or `*-mcp` scripts, install the matching **`api`** / **`mcp`** extras and read **`--help`** or the upstream README for ports, routes, and tool names.

## See also

- Global install and extras summary: [Global skill](../mdengine-ai-global/SKILL.md)
- CLI cheat sheet: [CLI reference](../mdengine-reference/SKILL.md)
