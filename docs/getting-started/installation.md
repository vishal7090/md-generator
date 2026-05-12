# Installation

## From PyPI

```bash
pip install "mdengine[pdf,word]"
pip install "mdengine[all]"
```

## From A Clone

```bash
git clone https://github.com/vishal7090/md-generator.git
cd md-generator
python -m venv .venv
. .venv/bin/activate
python -m pip install -U pip
pip install -e ".[dev,docs]"
```

On Windows PowerShell, activate with:

```powershell
.\.venv\Scripts\Activate.ps1
```

## Optional Extras

The repository uses optional dependency extras instead of installing every converter dependency by default. Detected extras include `pdf`, `word`, `ppt`, `xlsx`, `image`, `image-ocr`, `text`, `archive`, `url`, `url-full`, `audio`, `video`, `youtube`, `playwright`, `db`, `graph`, `openapi`, `codeflow`, `codeflow-worker`, `codeflow-treesitter`, `codeflow-clang`, `codeflow-semantic`, `log`, `log-cluster`, `log-semantic`, `log-pretty`, `api`, `mcp`, `skill-openai`, `skill-rag-chroma`, `dev`, `all`, and `docs`.

Install the smallest set required for the workflow. For example, database exports need `db`; FastAPI services need `api`; MCP servers need `mcp`.
