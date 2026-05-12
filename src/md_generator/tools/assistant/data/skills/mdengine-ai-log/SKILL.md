---
name: mdengine-ai-log
description: "Documents pip-installed mdengine features for Log → Markdown: extras, CLIs, and public imports under md_generator.log. Use when the user mentions `md-log`, `md-log-api`, `md-log-mcp`, log normalization, or needs this capability after installing mdengine from PyPI. Package summary: log-to-md — normalize logs to AI-oriented Markdown (presets, clustering, API/MCP)."
version: 0.8.0
---
# mdengine — Log → Markdown (log-to-md)

<!-- Prefer editing references/example.md for copy-paste snippets. -->

## Purpose

log-to-md: parse and normalize application logs into structured Markdown (timelines, incidents, clustering when optional extras are installed).

## Input / output

- **Inputs:** Log files or directories (`--input`), YAML `--config`, optional `--preset` (e.g. `generic`, `springboot`). Async: `--async` with SQLite job store.
- **Outputs:** Markdown bundle / ZIP per config; **`md-log --help`** for full flags.

## Examples

Concrete commands: [references/example.md](references/example.md).

## Install

```bash
pip install "mdengine[log]"
```

Optional capability extras (large installs where noted):

- **`log-cluster`** — scikit-learn clustering helpers.
- **`log-semantic`** — SentenceTransformers / semantic grouping (heavy).
- **`log-pretty`** — loguru for pretty-print paths.

```bash
pip install "mdengine[log,log-cluster,api,mcp]"
```

## Primary entry points (from pyproject)

- `md-log` — CLI (`md_generator.log.cli.main:main`)
- `md-log-api` — FastAPI (`md_generator.log.api.run:main`)
- `md-log-mcp` — MCP (`md_generator.log.api.mcp_server:main`)

## Core layout

- **Package:** `md_generator.log`
- **Notable areas:** `cli`, `api` (FastAPI + MCP mount `/mcp`), `core` (pipeline, jobs, zip export), `parser`, `config` (YAML presets under packaged `*.yaml`)

## HTTP API (summary)

Env prefix **`LOG_TO_MD_`** (see `LogApiSettings`): `LOG_TO_MD_HOST`, `LOG_TO_MD_PORT` (default **8012** — change if colliding with **graph** API on the same host), `LOG_TO_MD_MAX_SYNC_ZIP_MB`, `LOG_TO_MD_MAX_LOG_UPLOAD_MB`, job SQLite / workspace paths.

Routes (FastAPI app `md_generator.log.api.main:app`):

- `GET /health`
- `POST /log-to-md/run` — JSON body → sync ZIP
- `POST /log-to-md/run/upload` — multipart log + optional `config` JSON
- `POST /log-to-md/job` — async job from JSON body
- `POST /log-to-md/job/upload` — async job from uploaded log file
- `GET /log-to-md/job/{job_id}` — status
- `GET /log-to-md/job/{job_id}/download` — ZIP when complete
- `GET /log-to-md/job/{job_id}/events` — SSE progress
- MCP mounted at **`/mcp`** when using the HTTP app

Full tables alongside other services: [http-api-mcp.md](../mdengine-reference/references/http-api-mcp.md).

## APIs / MCP

See [http-api-mcp.md](../mdengine-reference/references/http-api-mcp.md). Install **`mdengine[api,mcp]`** plus **`mdengine[log]`** (and optional log extras).

## See also

- [Global architecture skill](../global-skill.md)
- [Consumer global skill](../mdengine-ai-global/SKILL.md)
- [CLI reference](../mdengine-reference/SKILL.md)
