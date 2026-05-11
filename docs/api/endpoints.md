# Endpoints

## Converter Pattern

Most converter APIs expose:

- `POST /convert/sync`: run conversion immediately and return the generated result or bundle.
- `POST /convert/jobs`: create an asynchronous conversion job.
- `GET /convert/jobs/{job_id}`: inspect job status.
- `GET /convert/jobs/{job_id}/download`: download output.

## Domain APIs

- `db-to-md`: `/db-to-md/run`, `/db-to-md/run/sqlite`, `/db-to-md/job`, `/db-to-md/job/sqlite`, event and stream endpoints.
- `graph-to-md`: `/graph-to-md/run`, `/graph-to-md/job`, event and stream endpoints.
- `log-to-md`: sync, upload, async job, event, and stream endpoints.
- `codeflow-to-md`: `/analyze`, `/analyze/sync`, status, result, and events endpoints.
- `openapi-to-md`: `/openapi-to-md/generate` plus `/health`.

## Full Detected Route Summary

| Service | Endpoints |
|---------|-----------|
| pdf-to-md | `/convert/sync, /convert/jobs, /convert/jobs/{job_id}, /convert/jobs/{job_id}/download` |
| word-to-md | `/convert/sync, /convert/jobs, /convert/jobs/{job_id}, /convert/jobs/{job_id}/download` |
| ppt-to-md | `/convert/sync, /convert/jobs, /convert/jobs/{job_id}, /convert/jobs/{job_id}/download` |
| xlsx-to-md | `/convert/sync, /convert/jobs, /convert/jobs/{job_id}, /convert/jobs/{job_id}/download` |
| image-to-md | `/convert/sync, /convert/jobs, /convert/jobs/{job_id}, /convert/jobs/{job_id}/download` |
| txt-json-xml-to-md | `/convert/sync, /convert/jobs, /convert/jobs/{job_id}, /convert/jobs/{job_id}/download` |
| zip-to-md | `/convert/sync, /convert/jobs, /convert/jobs/{job_id}, /convert/jobs/{job_id}/download` |
| url-to-md | `/convert/sync, /convert/jobs, /convert/jobs/{job_id}, /convert/jobs/{job_id}/download` |
| audio-to-md | `/convert/sync, /convert/jobs, /convert/jobs/{job_id}, /convert/jobs/{job_id}/download` |
| video-to-md | `/convert/sync, /convert/jobs, /convert/jobs/{job_id}, /convert/jobs/{job_id}/download` |
| youtube-to-md | `/convert/sync, /convert/jobs, /convert/jobs/{job_id}, /convert/jobs/{job_id}/download` |
| playwright-to-md | `/convert/sync, /convert/jobs, /convert/jobs/{job_id}, /convert/jobs/{job_id}/download` |
| db-to-md | `/health, /db-to-md/run, /db-to-md/run/sqlite, /db-to-md/job, /db-to-md/job/sqlite, /db-to-md/job/{job_id}, /download, /events, /stream` |
| graph-to-md | `/health, /graph-to-md/run, /graph-to-md/job, /graph-to-md/job/{job_id}, /download, /events, /stream` |
| openapi-to-md | `/health, /openapi-to-md/generate, /mcp` |
| codeflow-to-md | `/health, /analyze, /analyze/sync, /status/{job_id}, /result/{job_id}, /analyze/job/{job_id}/events` |
| log-to-md | `/health, /log-to-md/run, /log-to-md/run/upload, /log-to-md/job, /log-to-md/job/upload, /log-to-md/job/{job_id}, /download, /events, /stream` |
| No FastAPI app detected | `No HTTP API route set was detected for this module.` |
| No FastAPI app detected | `No HTTP API route set was detected for this module.` |
