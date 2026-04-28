---
name: mdengine-ai-text
description: >-
  Documents pip-installed mdengine features for Text / JSON / XML → Markdown: extras, CLIs, and
  public imports under md_generator.text. Use when the user mentions md-text, json to markdown, xml, md_generator.text
  or needs this capability after installing mdengine from PyPI.
version: 0.7.0
---

# mdengine — Text / JSON / XML → Markdown


## Examples

Concrete commands: [references/example.md](references/example.md).

## Install

```bash
pip install "mdengine[text]"
```

(Adjust extras in the `pip install` line to match the features you need.)

## Primary entry points

- **CLI:** `md-text`
- **Library:** Package: `md_generator.text`.

Use **`--help`** on each CLI for flags. Prefer CLIs for automation unless you are embedding Python APIs described in the upstream README.

## Capabilities

- Structured plain-text formats to Markdown emit paths.

## APIs / MCP

If this area ships `*-api` or `*-mcp` scripts, install the matching **`api`** / **`mcp`** extras and read **`--help`** or the upstream README for ports, routes, and tool names.

## See also

- Global install and extras summary: [Global skill](../mdengine-ai-global/SKILL.md)
- CLI cheat sheet: [CLI reference](../mdengine-reference/SKILL.md)
