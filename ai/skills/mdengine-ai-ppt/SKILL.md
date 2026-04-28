---
name: mdengine-ai-ppt
description: >-
  Documents pip-installed mdengine features for PowerPoint → Markdown: extras, CLIs, and
  public imports under md_generator.ppt. Use when the user mentions md-ppt, pptx, powerpoint, md_generator.ppt
  or needs this capability after installing mdengine from PyPI.
version: 0.7.0
---

# mdengine — PowerPoint → Markdown


## Examples

Concrete commands: [references/example.md](references/example.md).

## Install

```bash
pip install "mdengine[ppt]"
```

(Adjust extras in the `pip install` line to match the features you need.)

## Primary entry points

- **CLI:** `md-ppt`
- **Library:** Package: `md_generator.ppt`.

Use **`--help`** on each CLI for flags. Prefer CLIs for automation unless you are embedding Python APIs described in the upstream README.

## Capabilities

- Slide decks to Markdown; embedded assets and vendor bridges per flags.

## APIs / MCP

If this area ships `*-api` or `*-mcp` scripts, install the matching **`api`** / **`mcp`** extras and read **`--help`** or the upstream README for ports, routes, and tool names.

## See also

- Global install and extras summary: [Global skill](../mdengine-ai-global/SKILL.md)
- CLI cheat sheet: [CLI reference](../mdengine-reference/SKILL.md)
