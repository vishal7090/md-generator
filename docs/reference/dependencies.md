# Dependencies

`pyproject.toml` keeps the base dependency set empty and uses optional extras for feature dependencies.

Detected extras: `pdf`, `word`, `ppt`, `xlsx`, `image`, `image-ocr`, `text`, `archive`, `url`, `url-full`, `audio`, `video`, `youtube`, `playwright`, `db`, `graph`, `openapi`, `codeflow`, `codeflow-worker`, `codeflow-treesitter`, `codeflow-clang`, `codeflow-semantic`, `log`, `log-cluster`, `log-semantic`, `log-pretty`, `api`, `mcp`, `skill-openai`, `skill-rag-chroma`, `dev`, `all`, and `docs`.

## Recommended Install Strategy

- Use `.[docs]` for documentation builds.
- Use `.[dev]` for tests and development helpers.
- Use domain extras such as `.[db]`, `.[graph]`, `.[openapi]`, `.[codeflow]`, or `.[log]` only when needed.
- Avoid `.[all]` in slim production images unless every converter is required.
