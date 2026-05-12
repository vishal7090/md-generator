# OpenAPI Deployment

Deploy the API surface only when HTTP access is required. Install the smallest dependency extra set and add `api` for FastAPI runtime.

For Dockerized services, follow the existing `Dockerfile.api` and Compose gateway pattern used by top-level converter folders.
