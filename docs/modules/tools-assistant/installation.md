# AI Assistant Tools Installation

```bash
pip install "mdengine[skill-openai]"
```

For local development from a clone:

```bash
pip install -e ".[skill-openai,dev]"
```

If the module also runs as HTTP API, include `api`:

```bash
pip install -e ".[skill-openai,api]"
```
