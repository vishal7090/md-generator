# System Design

## Design Goals

- Keep default installs lightweight by using extras.
- Reuse converter code across CLI, API, and MCP surfaces.
- Make generated Markdown deterministic enough for version control and review.
- Support both local developer workflows and containerized HTTP services.

## Architectural Pattern

The repository is not a microservice repository in packaging terms. It is a modular monolith with optional independently runnable FastAPI services. Docker Compose turns selected modules into service containers behind nginx, but the Python release remains unified.
