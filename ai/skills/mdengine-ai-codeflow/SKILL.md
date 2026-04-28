---
name: mdengine-ai-codeflow
description: >-
  Documents pip-installed mdengine features for Code → Markdown (codeflow): extras, CLIs, and
  public imports under md_generator.codeflow. Use when the user mentions codeflow, md-codeflow, code to markdown, architecture from code, md_generator.codeflow
  or needs this capability after installing mdengine from PyPI.
version: 0.7.0
---

# mdengine — Code → Markdown (codeflow)


## Examples

Concrete commands: [references/example.md](references/example.md).

## Install

```bash
pip install "mdengine[codeflow]"  # optional: [codeflow-treesitter] or [codeflow-clang]
```

(Adjust extras in the `pip install` line to match the features you need.)

## Primary entry points

- **CLI:** `md-codeflow`, `codeflow`, `md-codeflow-api`, `md-codeflow-mcp`; `mdengine` CLI may expose codeflow subcommands
- **Library:** Package: `md_generator.codeflow` — use CLIs above unless embedding the library API per upstream docs.

Use **`--help`** on each CLI for flags. Prefer CLIs for automation unless you are embedding Python APIs described in the upstream README.

## Capabilities

- Build graphs and Markdown docs from source trees (multi-language; extras extend parsers).
- HTTP and MCP surfaces for automation.

## APIs / MCP

If this area ships `*-api` or `*-mcp` scripts, install the matching **`api`** / **`mcp`** extras and read **`--help`** or the upstream README for ports, routes, and tool names.

## See also

- Global install and extras summary: [Global skill](../mdengine-ai-global/SKILL.md)
- CLI cheat sheet: [CLI reference](../mdengine-reference/SKILL.md)
