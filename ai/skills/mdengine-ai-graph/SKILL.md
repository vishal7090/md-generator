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

`md-graph-api` (**8012** / `GRAPH_TO_MD_PORT`), `md-graph-mcp`, job + SSE paths: [http-api-mcp.md](../mdengine-reference/references/http-api-mcp.md). Port clash with **`md-video-api`** — set env vars if both run on one host.

## See also

- Global install and extras summary: [Global skill](../mdengine-ai-global/SKILL.md)
- CLI cheat sheet: [CLI reference](../mdengine-reference/SKILL.md)
