from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

pytest = __import__("pytest")
fastmcp = pytest.importorskip("fastmcp")


def test_mcp_server_defines_tools() -> None:
    import asyncio

    from api import mcp_server

    async def _names() -> set[str]:
        tools = await mcp_server.mcp.get_tools()
        return set(tools.keys())

    found = asyncio.run(_names())
    assert "convert_docx_to_artifact_zip" in found
    assert "convert_docx_base64_to_artifact_zip" in found
