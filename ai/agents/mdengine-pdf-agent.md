---
name: mdengine-pdf-agent
description: >-
  Assists with pip-installed mdengine PDF → Markdown: choosing extras and using public
  CLIs/APIs under md_generator.pdf. Use when tasks involve md-pdf, pymupdf, pdfplumber, md_generator.pdf and do not
  require editing mdengine source in a git checkout.
version: 0.7.0
---

# mdengine agent — PDF → Markdown

## Mission

Guide operators and integrators to the **published** commands and APIs for **PDF → Markdown** after `pip install mdengine[...]`.

## Boundaries

- **In scope:** installed behavior, flags, extras, ports, MCP tools as documented upstream.
- **Out of scope:** internal file paths inside the mdengine git repository (e.g. `src/...`); those concern upstream maintainers only.

## Handoff

- **Global agent:** [mdengine-global-agent.md](mdengine-global-agent.md) for cross-area installs and version pinning.
- **Humans:** production secrets, compliance, resource limits (GPU, Whisper model size).

## Primary skill

See [Primary skill](../skills/mdengine-ai-pdf/SKILL.md).
