# Examples — log → Markdown

## CLI (sync)

```bash
pip install "mdengine[log]"
md-log --input ./app.log --output ./log-md-out --preset generic
```

With explicit config:

```bash
md-log --config ./my-log-to-md.yaml --output ./out
```

## CLI (async job — prints `job_id`)

```bash
md-log --input ./big.log --output ./out --async
```

## API + MCP

```bash
pip install "mdengine[log,api,mcp]"
export LOG_TO_MD_PORT=8020
md-log-api --host 127.0.0.1 --port 8020
```

Then: `GET /health`, `POST /log-to-md/run` (JSON) or `POST /log-to-md/run/upload` (multipart). MCP client: `http://127.0.0.1:8020/mcp`.

Standalone MCP:

```bash
md-log-mcp --transport stdio
```

## Optional clustering / semantic extras

```bash
pip install "mdengine[log,log-cluster]"
# or (large): pip install "mdengine[log,log-semantic]"
```
