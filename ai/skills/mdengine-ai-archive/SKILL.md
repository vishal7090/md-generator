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

FastAPI apps, **`/convert/sync`** job pattern, MCP on **`/mcp`**, and standalone MCP module invocations for this format are listed in [http-api-mcp.md](../mdengine-reference/references/http-api-mcp.md). Install **`mdengine[api,mcp]`** plus this area's extra; use **`--help`** on the API process you start.

## See also

- Global install and extras summary: [Global skill](../mdengine-ai-global/SKILL.md)
- CLI cheat sheet: [CLI reference](../mdengine-reference/SKILL.md)
