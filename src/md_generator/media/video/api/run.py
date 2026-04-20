"""Run the video REST + MCP FastAPI app with uvicorn."""

from __future__ import annotations

import argparse


def main(argv: list[str] | None = None) -> int:
    import uvicorn

    from md_generator.media.video.api.settings import VideoApiSettings

    p = argparse.ArgumentParser(description="video-to-md HTTP API (REST + MCP at /mcp)")
    p.add_argument("--host", default=None)
    p.add_argument("--port", type=int, default=None)
    ns = p.parse_args(argv)
    s = VideoApiSettings()
    host = ns.host or s.api_host
    port = ns.port if ns.port is not None else s.api_port
    uvicorn.run(
        "md_generator.media.video.api.main:create_app",
        host=host,
        port=port,
        factory=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
