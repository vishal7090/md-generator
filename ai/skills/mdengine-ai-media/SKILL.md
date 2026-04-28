---
name: mdengine-ai-media
description: >-
  Documents pip-installed mdengine features for Audio, video, YouTube → Markdown: extras, CLIs, and
  public imports under md_generator.media. Use when the user mentions md-audio, md-video, md-youtube, whisper, transcript, md_generator.media
  or needs this capability after installing mdengine from PyPI.
version: 0.7.0
---

# mdengine — Audio, video, YouTube → Markdown


## Examples

Concrete commands: [references/example.md](references/example.md).

## Install

```bash
pip install "mdengine[audio,video,youtube,api,mcp]"
```

(Adjust extras in the `pip install` line to match the features you need.)

## Primary entry points

- **CLI:** `md-audio`, `md-video`, `md-youtube`, matching `*-api` and `*-mcp` scripts
- **Library:** Packages under `md_generator.media` (audio, video, youtube).

Use **`--help`** on each CLI for flags. Prefer CLIs for automation unless you are embedding Python APIs described in the upstream README.

## Capabilities

- Transcribe audio/video with Whisper; YouTube captions/transcripts and metadata.
- Optional FastAPI and MCP services for each media type.

## APIs / MCP

If this area ships `*-api` or `*-mcp` scripts, install the matching **`api`** / **`mcp`** extras and read **`--help`** or the upstream README for ports, routes, and tool names.

## See also

- Global install and extras summary: [Global skill](../mdengine-ai-global/SKILL.md)
- CLI cheat sheet: [CLI reference](../mdengine-reference/SKILL.md)
