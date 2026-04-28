# Console entry points (`[project.scripts]`)

Source: **`mdengine`** `pyproject.toml` — every script installed on `PATH` after `pip install mdengine[…]`.

| Command | Entry point |
|---------|----------------|
| `md-pdf` | `md_generator.pdf.converter:main` |
| `md-word` | `md_generator.word.converter:main` |
| `md-ppt` | `md_generator.ppt.converter:main` |
| `md-xlsx` | `md_generator.xlsx.converter:main` |
| `md-image` | `md_generator.image.converter:main` |
| `md-text` | `md_generator.text.converter:main` |
| `md-zip` | `md_generator.archive.converter:main` |
| `md-url` | `md_generator.url.converter:main` |
| `md-audio` | `md_generator.media.audio.converter:main` |
| `md-video` | `md_generator.media.video.converter:main` |
| `md-audio-api` | `md_generator.media.audio.api.run:main` |
| `md-video-api` | `md_generator.media.video.api.run:main` |
| `md-audio-mcp` | `md_generator.media.audio.api.mcp_server:main` |
| `md-video-mcp` | `md_generator.media.video.api.mcp_server:main` |
| `md-youtube` | `md_generator.media.youtube.converter:main` |
| `md-youtube-api` | `md_generator.media.youtube.api.run:main` |
| `md-youtube-mcp` | `md_generator.media.youtube.api.mcp_server:main` |
| `md-playwright` | `md_generator.playwright.cli:main` |
| `md-playwright-api` | `md_generator.playwright.api.run:main` |
| `md-playwright-mcp` | `md_generator.playwright.api.mcp_server:main` |
| `md-db` | `md_generator.db.cli.main:main` |
| `md-db-api` | `md_generator.db.api.run:main` |
| `md-db-mcp` | `md_generator.db.api.mcp_server:main` |
| `md-graph` | `md_generator.graph.cli.main:main` |
| `md-graph-api` | `md_generator.graph.api.run:main` |
| `md-graph-mcp` | `md_generator.graph.api.mcp_server:main` |
| `md-openapi` | `md_generator.openapi.cli.main:main` |
| `md-openapi-api` | `md_generator.openapi.api.run:main` |
| `md-openapi-mcp` | `md_generator.openapi.api.mcp_server:main` |
| `md-codeflow` | `md_generator.codeflow.cli.main:main` |
| `codeflow` | `md_generator.codeflow.cli.main:main` |
| `md-codeflow-api` | `md_generator.codeflow.api.run:main` |
| `md-codeflow-mcp` | `md_generator.codeflow.api.mcp_server:main` |
| `mdengine` | `md_generator.engine_cli:main` |

**Note:** Format converters also expose **Uvicorn `app`** targets and **`python -m …mcp_server`** runners that are not separate `project.scripts` rows — see [http-api-mcp.md](http-api-mcp.md).
