"""Standalone MCP server for codeflow (stdio)."""

from __future__ import annotations

import asyncio


def main() -> None:
    from md_generator.codeflow.mcp.server import build_mcp_stack

    mcp, _ = build_mcp_stack(mount_under_fastapi=False)
    asyncio.run(mcp.run_stdio_async())


if __name__ == "__main__":
    main()
