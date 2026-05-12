# API Examples

## Run The Docker Gateway

```bash
docker compose -f deploy/docker-compose.yml up --build
```

Open `http://localhost:8080/` to see the gateway index. Swagger UI paths include `/pdf-to-md/docs`, `/word-to-md/docs`, `/ppt-to-md/docs`, `/image-to-md/docs`, `/txt-json-xml-to-md/docs`, `/zip-to-md/docs`, and `/xlsx-to-md/docs`.

## Direct Uvicorn Example

```bash
pip install -e ".[pdf,api]"
uvicorn md_generator.pdf.api.main:app --host 0.0.0.0 --port 8000
```

Then open `http://localhost:8000/docs`.
