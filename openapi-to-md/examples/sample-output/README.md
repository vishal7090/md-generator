# Sample `openapi-to-md` output layout

Regenerate locally (deterministic, no LLM):

```bash
pip install -e ".[openapi]"
md-openapi generate --file openapi-to-md/examples/minimal_openapi.yaml --output ./api-md-out --formats md,html,mermaid
```

Typical directories and files:

- `README.md` — index of endpoints and embedded dependency Mermaid
- `api_summary.json` — machine-readable endpoint index
- `endpoints/` — one Markdown (and optional `.html`) per operation
- `schemas/` — one Markdown per `components.schemas` entry
- `diagrams/sequence/` — per-endpoint sequence `.mmd` when `--formats` includes `mermaid`
- `graphs/api_dependency.mmd` and `graphs/api_dependency.dot` — cross-operation dependency graph
