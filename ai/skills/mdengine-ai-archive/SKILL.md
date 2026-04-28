---
name: mdengine-ai-archive
description: >-
  Documents pip-installed mdengine features for Archive (ZIP) conversion: extras, CLIs, and
  public imports under md_generator.archive. Use when the user mentions md-zip, zip archive, md_generator.archive, mdengine archive extra
  or needs this capability after installing mdengine from PyPI.
version: 0.7.0
---

# mdengine — Archive (ZIP) conversion


## Examples

Concrete commands: [references/example.md](references/example.md).

## Install

```bash
pip install "mdengine[archive]"
```

(Adjust extras in the `pip install` line to match the features you need.)

## Primary entry points

- **CLI:** `md-zip`
- **Library:** Package: `md_generator.archive` (invoked via `md-zip` for normal use).

Use **`--help`** on each CLI for flags. Prefer CLIs for automation unless you are embedding Python APIs described in the upstream README.

## Capabilities

- Extract ZIP and nested documents to a Markdown-oriented layout.
- Optional OCR on embedded images when extras and flags allow.

## APIs / MCP

If this area ships `*-api` or `*-mcp` scripts, install the matching **`api`** / **`mcp`** extras and read **`--help`** or the upstream README for ports, routes, and tool names.

## See also

- Global install and extras summary: [Global skill](../mdengine-ai-global/SKILL.md)
- CLI cheat sheet: [CLI reference](../mdengine-reference/SKILL.md)
