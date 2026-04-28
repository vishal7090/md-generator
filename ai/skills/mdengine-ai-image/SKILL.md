---
name: mdengine-ai-image
description: >-
  Documents pip-installed mdengine features for Image OCR → Markdown: extras, CLIs, and
  public imports under md_generator.image. Use when the user mentions md-image, OCR, tesseract, md_generator.image
  or needs this capability after installing mdengine from PyPI.
version: 0.7.0
---

# mdengine — Image OCR → Markdown


## Examples

Concrete commands: [references/example.md](references/example.md).

## Install

```bash
pip install "mdengine[image]"  # or mdengine[image-ocr]
```

(Adjust extras in the `pip install` line to match the features you need.)

## Primary entry points

- **CLI:** `md-image`
- **Library:** Package: `md_generator.image`.

Use **`--help`** on each CLI for flags. Prefer CLIs for automation unless you are embedding Python APIs described in the upstream README.

## Capabilities

- Raster and OCR pipelines with configurable engines/strategies (`--help`).

## APIs / MCP

If this area ships `*-api` or `*-mcp` scripts, install the matching **`api`** / **`mcp`** extras and read **`--help`** or the upstream README for ports, routes, and tool names.

## See also

- Global install and extras summary: [Global skill](../mdengine-ai-global/SKILL.md)
- CLI cheat sheet: [CLI reference](../mdengine-reference/SKILL.md)
