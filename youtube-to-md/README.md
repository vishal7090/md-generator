# youtube-to-md

Convert a **YouTube URL** to Markdown (title, metadata, description, timestamped transcript).

## Install

```bash
pip install "mdengine[youtube]"
# optional: captions fallback via Whisper + yt-dlp
pip install "mdengine[audio]"
# yt-dlp on PATH, or set MD_YOUTUBE_YTDLP to the executable
```

## CLI

```bash
md-youtube "https://www.youtube.com/watch?v=VIDEO_ID" out.md --transcript-lang en -v
```

Same entrypoint as `python youtube-to-md/converter.py …` with `PYTHONPATH=../src` from this folder.

## HTTP + MCP

```bash
pip install "mdengine[youtube,api,mcp]"
md-youtube-api --port 8013
```

- `POST /convert/sync` — JSON body `{ "url": "https://…" }` → Markdown response.
- `POST /convert/jobs` — same JSON → `{ "job_id", "status" }`; poll then `GET /convert/jobs/{id}/download`.
- MCP: `youtube_url_to_markdown` (see root README).

## Tests

From repo root (with dev deps):

```bash
pytest youtube-to-md/tests
```
