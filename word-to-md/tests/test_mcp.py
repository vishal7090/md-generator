from __future__ import annotations

import asyncio

import pytest

fastmcp = pytest.importorskip("fastmcp")


def test_mcp_server_defines_tools() -> None:
    from md_generator.word.api import mcp_server

    async def _names() -> set[str]:
        tools = await mcp_server.mcp.get_tools()
        return set(tools.keys())

    found = asyncio.run(_names())
    assert "convert_docx_to_artifact_zip" in found
    assert "convert_docx_base64_to_artifact_zip" in found
