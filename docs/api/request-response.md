# Request And Response Patterns

## Sync Conversion

```bash
curl -X POST http://localhost:8000/convert/sync   -F "file=@input.pdf"
```

A sync endpoint returns the generated artifact immediately when the output is small enough and the conversion completes inside request limits.

## Async Conversion

```bash
curl -X POST http://localhost:8000/convert/jobs   -F "file=@input.pdf"
```

The response includes a `job_id`. Poll the status endpoint and then call the download endpoint when complete.

## Domain Configuration Request

Database, graph, OpenAPI, codeflow, and log endpoints accept structured JSON or multipart payloads depending on the operation. These payloads mirror each domain CLI/YAML configuration rather than a single global schema.
