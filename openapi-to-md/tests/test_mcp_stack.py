from __future__ import annotations

from md_generator.openapi.mcp.server import build_mcp_stack


def test_build_mcp_stack_returns_fastmcp() -> None:
    mcp, _http = build_mcp_stack(mount_under_fastapi=False)
    assert mcp.name == "openapi-to-md"
