# Docker Deployment

The checked-in Docker deployment is `deploy/docker-compose.yml`. It builds service images from per-module `Dockerfile.api` files and exposes them through nginx on port `8080`.

```bash
docker compose -f deploy/docker-compose.yml up --build
```

The gateway currently lists Swagger UI routes for ZIP, PDF, PPT, Word, image, text, and XLSX services.
