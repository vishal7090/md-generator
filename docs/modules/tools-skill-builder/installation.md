# Skill Builder Installation

```bash
pip install "mdengine"
```

For local development from a clone:

```bash
pip install -e ".[dev]"
```

This module does not expose a FastAPI service. Install `docs` only when you are building the MkDocs site:

```bash
pip install -e ".[dev,docs]"
```
