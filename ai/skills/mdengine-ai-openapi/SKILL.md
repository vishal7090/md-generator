---
name: mdengine-ai-openapi
description: >-
  Documents pip-installed mdengine features for OpenAPI → Markdown / docs bundle: extras, CLIs, and
  public imports under md_generator.openapi. Use when the user mentions md-openapi, openapi, swagger, md_generator.openapi
  or needs this capability after installing mdengine from PyPI.
version: 0.7.0
---

# mdengine — OpenAPI → Markdown / docs bundle


## Examples

Concrete commands: [references/example.md](references/example.md).

## Install

```bash
pip install "mdengine[openapi,api,mcp]"
```

(Adjust extras in the `pip install` line to match the features you need.)

## Primary entry points

- **CLI:** `md-openapi`, `md-openapi-api`, `md-openapi-mcp`
- **Library:** Package: `md_generator.openapi`.

Use **`--help`** on each CLI for flags. Prefer CLIs for automation unless you are embedding Python APIs described in the upstream README.

## Capabilities

- Parse and validate OpenAPI; Swagger 2 may be converted to OAS3 in-process.
- Generate README-style Markdown and ZIP exports; MCP tools for validation and generation.

## APIs / MCP

`md-openapi-api` (**8015** / `OPENAPI_TO_MD_PORT`), `POST /openapi-to-md/generate`, `/health`, MCP at **`/mcp`**; standalone **`md-openapi-mcp`** tool names: [http-api-mcp.md](../mdengine-reference/references/http-api-mcp.md).

## See also

- Global install and extras summary: [Global skill](../mdengine-ai-global/SKILL.md)
- CLI cheat sheet: [CLI reference](../mdengine-reference/SKILL.md)
