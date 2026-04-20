"""Standalone MCP server: stdio, SSE, or streamable HTTP."""

from __future__ import annotations

import argparse
import asyncio


def main() -> None:
    parser = argparse.ArgumentParser(description="youtube-to-md MCP server")
    parser.add_argument(
        "--transport",
        choices=("stdio", "sse", "streamable-http"),
        default="stdio",
    )
    args = parser.parse_args()

    from md_generator.media.youtube.api.mcp_setup import build_mcp_stack

    mcp, _ = build_mcp_stack(mount_under_fastapi=False)

    if args.transport == "stdio":
        asyncio.run(mcp.run_stdio_async())
    elif args.transport == "sse":
        asyncio.run(mcp.run_sse_async())
    else:
        asyncio.run(mcp.run_streamable_http_async())


if __name__ == "__main__":
    main()
