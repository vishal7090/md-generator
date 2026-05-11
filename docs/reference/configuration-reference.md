# Configuration Reference

Configuration is domain-specific:

- Database, graph, OpenAPI, and log modules include packaged YAML defaults or config-driven CLI/API flows.
- Converter modules expose CLI flags and API request fields for input/output options.
- Docker gateway path configuration lives in `deploy/nginx/default.conf`.
- Python packaging, scripts, extras, and tests are centralized in `pyproject.toml`.
