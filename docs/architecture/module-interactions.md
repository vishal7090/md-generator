# Module Interactions

## Interface To Core Mapping

| `md-pdf` | `md_generator.pdf` | `pdf` | PDF documents |
| `md-word` | `md_generator.word` | `word` | DOCX documents |
| `md-ppt` | `md_generator.ppt` | `ppt` | PPTX slide decks |
| `md-xlsx` | `md_generator.xlsx` | `xlsx` | XLSX, XLSM, and CSV files |
| `md-image` | `md_generator.image` | `image or image-ocr` | Image files or directories |
| `md-text` | `md_generator.text` | `text` | Plain text, JSON, and XML files |
| `md-zip` | `md_generator.archive` | `archive plus nested format extras` | ZIP archives |
| `md-url` | `md_generator.url` | `url or url-full` | HTTP and HTTPS web pages |
| `md-audio` | `md_generator.media.audio` | `audio` | Audio files |
| `md-video` | `md_generator.media.video` | `video` | Video files |
| `md-youtube` | `md_generator.media.youtube` | `youtube` | YouTube URLs |
| `md-playwright` | `md_generator.playwright` | `playwright` | Rendered web pages and SPAs |
| `md-db` | `md_generator.db` | `db` | Postgres, MySQL, Oracle, SQLite, and Mongo metadata sources |
| `md-graph` | `md_generator.graph` | `graph` | Neo4j and NetworkX graph sources |
| `md-openapi` | `md_generator.openapi` | `openapi` | OpenAPI 3.x or Swagger 2.0 specifications |
| `md-codeflow or codeflow` | `md_generator.codeflow` | `codeflow` | Source repositories and code trees |
| `md-log` | `md_generator.log` | `log` | Log files and uploaded log content |
| `mdengine ai assist / mdengine ai export` | `md_generator.tools.assistant` | `skill-openai or skill-rag-chroma for optional providers` | Skill markdown bundles and prompts |
| `mdengine skill build` | `md_generator.tools.skill_builder` | `base package` | Project metadata and skill sources |

## Cross-Module Relationships

- `archive` can call nested converters when the relevant extras are installed.
- `url-full` combines URL fetching with document conversion stacks.
- API and MCP modules delegate to the same core conversion logic used by CLIs.
- `db`, `graph`, `openapi`, `codeflow`, and `log` use packaged YAML/configuration patterns for richer generation workflows.
