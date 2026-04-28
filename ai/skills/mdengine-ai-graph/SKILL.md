---
name: mdengine-ai-graph
description: >-
  Documents pip-installed mdengine features for Graph (Neo4j / NetworkX) → Markdown: extras, CLIs, and
  public imports under md_generator.graph. Use when the user mentions md-graph, neo4j, graphml, networkx, md_generator.graph
  or needs this capability after installing mdengine from PyPI.
version: 0.7.0
---

# mdengine — Graph (Neo4j / NetworkX) → Markdown


## Examples

Concrete commands: [references/example.md](references/example.md).

## Install

```bash
pip install "mdengine[graph,api,mcp]"
```

(Adjust extras in the `pip install` line to match the features you need.)

## Primary entry points

- **CLI:** `md-graph`, `md-graph-api`, `md-graph-mcp`
- **Library:** Package: `md_generator.graph`.

Use **`--help`** on each CLI for flags. Prefer CLIs for automation unless you are embedding Python APIs described in the upstream README.

## Capabilities

- Import GraphML/GML or query Neo4j; emit Markdown summaries and optional Mermaid/Graphviz diagrams.

## APIs / MCP

If this area ships `*-api` or `*-mcp` scripts, install the matching **`api`** / **`mcp`** extras and read **`--help`** or the upstream README for ports, routes, and tool names.

## See also

- Global install and extras summary: [Global skill](../mdengine-ai-global/SKILL.md)
- CLI cheat sheet: [CLI reference](../mdengine-reference/SKILL.md)
