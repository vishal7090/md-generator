# Scaling

Scale API services by workload type. CPU-heavy OCR, Whisper, browser rendering, and source-code analysis should not share resource limits with lightweight text or OpenAPI conversion.

## Guidance

- Separate heavy services into dedicated containers or node pools.
- Prefer async job endpoints for large inputs.
- Put upload, processing, and output size limits at the API and gateway layers.
- Use queue-backed workers for codeflow when `codeflow-worker` and Redis/Celery are intentionally deployed.
