# Environment Setup

The repository does not include a single root `.env.example`. Runtime configuration is module-specific and exposed through CLI flags, YAML configuration, or service-specific environment variables.

## Common Patterns

- API ports use module-specific variables such as `DB_TO_MD_PORT`, `GRAPH_TO_MD_PORT`, or `OPENAPI_TO_MD_PORT` where implemented.
- Upload and ZIP limits are enforced by API modules such as `db-to-md` through variables like `DB_TO_MD_MAX_SQLITE_UPLOAD_MB`.
- Graphviz can be configured with `GRAPHVIZ_DOT` when `dot` is not on `PATH`.
- Mermaid image rendering can use `MERMAID_INK_SERVER` for DB ERD generation when `mermaid-py` is used.

## Recommended Local Practice

Keep local secrets outside git, document service-specific variables in deployment manifests, and prefer YAML configs for database, graph, OpenAPI, and log workflows where the module provides packaged defaults.
