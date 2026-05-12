# API Overview

FastAPI services are detected under `src/md_generator/**/api`. Most file converters expose a consistent conversion contract, while richer domains expose job-specific APIs.

| Service | Source | CLI | Endpoints |
|---------|--------|-----|-----------|
| pdf-to-md | `src/md_generator/pdf` | `md-pdf` | `/convert/sync, /convert/jobs, /convert/jobs/{job_id}, /convert/jobs/{job_id}/download` |
| word-to-md | `src/md_generator/word` | `md-word` | `/convert/sync, /convert/jobs, /convert/jobs/{job_id}, /convert/jobs/{job_id}/download` |
| ppt-to-md | `src/md_generator/ppt` | `md-ppt` | `/convert/sync, /convert/jobs, /convert/jobs/{job_id}, /convert/jobs/{job_id}/download` |
| xlsx-to-md | `src/md_generator/xlsx` | `md-xlsx` | `/convert/sync, /convert/jobs, /convert/jobs/{job_id}, /convert/jobs/{job_id}/download` |
| image-to-md | `src/md_generator/image` | `md-image` | `/convert/sync, /convert/jobs, /convert/jobs/{job_id}, /convert/jobs/{job_id}/download` |
| txt-json-xml-to-md | `src/md_generator/text` | `md-text` | `/convert/sync, /convert/jobs, /convert/jobs/{job_id}, /convert/jobs/{job_id}/download` |
| zip-to-md | `src/md_generator/archive` | `md-zip` | `/convert/sync, /convert/jobs, /convert/jobs/{job_id}, /convert/jobs/{job_id}/download` |
| url-to-md | `src/md_generator/url` | `md-url` | `/convert/sync, /convert/jobs, /convert/jobs/{job_id}, /convert/jobs/{job_id}/download` |
| audio-to-md | `src/md_generator/media/audio` | `md-audio` | `/convert/sync, /convert/jobs, /convert/jobs/{job_id}, /convert/jobs/{job_id}/download` |
| video-to-md | `src/md_generator/media/video` | `md-video` | `/convert/sync, /convert/jobs, /convert/jobs/{job_id}, /convert/jobs/{job_id}/download` |
| youtube-to-md | `src/md_generator/media/youtube` | `md-youtube` | `/convert/sync, /convert/jobs, /convert/jobs/{job_id}, /convert/jobs/{job_id}/download` |
| playwright-to-md | `src/md_generator/playwright` | `md-playwright` | `/convert/sync, /convert/jobs, /convert/jobs/{job_id}, /convert/jobs/{job_id}/download` |
| db-to-md | `src/md_generator/db` | `md-db` | `/health, /db-to-md/run, /db-to-md/run/sqlite, /db-to-md/job, /db-to-md/job/sqlite, /db-to-md/job/{job_id}, /download, /events, /stream` |
| graph-to-md | `src/md_generator/graph` | `md-graph` | `/health, /graph-to-md/run, /graph-to-md/job, /graph-to-md/job/{job_id}, /download, /events, /stream` |
| openapi-to-md | `src/md_generator/openapi` | `md-openapi` | `/health, /openapi-to-md/generate, /mcp` |
| codeflow-to-md | `src/md_generator/codeflow` | `md-codeflow or codeflow` | `/health, /analyze, /analyze/sync, /status/{job_id}, /result/{job_id}, /analyze/job/{job_id}/events` |
| log-to-md | `src/md_generator/log` | `md-log` | `/health, /log-to-md/run, /log-to-md/run/upload, /log-to-md/job, /log-to-md/job/upload, /log-to-md/job/{job_id}, /download, /events, /stream` |
| No FastAPI app detected | `src/md_generator/tools/assistant` | `mdengine ai assist / mdengine ai export` | `No HTTP API route set was detected for this module.` |
| No FastAPI app detected | `src/md_generator/tools/skill_builder` | `mdengine skill build` | `No HTTP API route set was detected for this module.` |

Each FastAPI app also serves OpenAPI JSON and Swagger UI through FastAPI defaults when running without a custom gateway path.
