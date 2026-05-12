# Introduction

`mdengine` converts heterogeneous technical inputs into Markdown and related assets. It is not a single web application; it is a Python distribution with many optional feature areas.

## Primary Use Cases

- Convert office, PDF, image, archive, URL, audio, video, and YouTube inputs to Markdown.
- Generate database, graph, OpenAPI, source-code, and log documentation.
- Run converters locally through CLI commands or expose them through FastAPI services.
- Package Markdown output for downstream review, search, or static publishing.

## Architectural Shape

The repository is best described as a modular monolith: one package, many feature modules, optional dependencies, consistent CLI/API surfaces, and no separately versioned Python packages.
