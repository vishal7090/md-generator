# Production Checklist

- Install only required extras in each runtime image.
- Put authentication and rate limiting in front of FastAPI services.
- Enforce request body, output ZIP, and workspace size limits.
- Scan untrusted uploads before conversion where policy requires it.
- Configure structured logs and central retention.
- Run `mkdocs build --strict` before publishing docs.
- Document every externally supplied environment variable.
- Validate Graphviz, ffmpeg, OCR, Playwright, and database drivers during image build or startup.
