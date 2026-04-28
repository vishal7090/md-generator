---
name: mdengine-ai-db
description: >-
  Documents pip-installed mdengine features for Database → Markdown: extras, CLIs, and
  public imports under md_generator.db. Use when the user mentions md-db, database to markdown, ERD, SQL metadata, md_generator.db
  or needs this capability after installing mdengine from PyPI.
version: 0.7.0
---

# mdengine — Database → Markdown


## Examples

Concrete commands: [references/example.md](references/example.md).

## Install

```bash
pip install "mdengine[db,api,mcp]"
```

(Adjust extras in the `pip install` line to match the features you need.)

## Primary entry points

- **CLI:** `md-db`, `md-db-api`, `md-db-mcp`
- **Library:** Entry: `md_generator.db` (CLI `md-db`).

Use **`--help`** on each CLI for flags. Prefer CLIs for automation unless you are embedding Python APIs described in the upstream README.

## Capabilities

- Export SQL and Mongo metadata, ERD, and feature bundles to Markdown/ZIP.
- YAML/CLI config; async jobs and SQLite upload routes on the API (see upstream README).

## APIs / MCP

`md-db-api` (default port **8010**, `DB_TO_MD_PORT`), `md-db-mcp`, SQLite upload routes, and SSE job paths are summarized in [http-api-mcp.md](../mdengine-reference/references/http-api-mcp.md). Install **`mdengine[db,api,mcp]`**; use `md-db-api --help` / `md-db-mcp --help` for the exact build you have.

## See also

- Global install and extras summary: [Global skill](../mdengine-ai-global/SKILL.md)
- CLI cheat sheet: [CLI reference](../mdengine-reference/SKILL.md)
