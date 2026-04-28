---
name: mdengine-ai-word
description: >-
  Documents pip-installed mdengine features for Word (DOCX) → Markdown: extras, CLIs, and
  public imports under md_generator.word. Use when the user mentions md-word, docx, mammoth, md_generator.word
  or needs this capability after installing mdengine from PyPI.
version: 0.7.0
---

# mdengine — Word (DOCX) → Markdown


## Examples

Concrete commands: [references/example.md](references/example.md).

## Install

```bash
pip install "mdengine[word]"
```

(Adjust extras in the `pip install` line to match the features you need.)

## Primary entry points

- **CLI:** `md-word`
- **Library:** Package: `md_generator.word`.

Use **`--help`** on each CLI for flags. Prefer CLIs for automation unless you are embedding Python APIs described in the upstream README.

## Capabilities

- DOCX to Markdown with image extraction options.

## APIs / MCP

FastAPI apps, **`/convert/sync`** job pattern, MCP on **`/mcp`**, and standalone MCP module invocations for this format are listed in [http-api-mcp.md](../mdengine-reference/references/http-api-mcp.md). Install **`mdengine[api,mcp]`** plus this area's extra; use **`--help`** on the API process you start.

## See also

- Global install and extras summary: [Global skill](../mdengine-ai-global/SKILL.md)
- CLI cheat sheet: [CLI reference](../mdengine-reference/SKILL.md)
