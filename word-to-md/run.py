"""Unified runner: cli | api | mcp subcommands."""

from __future__ import annotations

import argparse
import sys


def _run_cli(remainder: list[str]) -> int:
    from md_generator.word.converter import main

    if remainder and remainder[0] == "--":
        remainder = remainder[1:]
    return main(remainder)


def _run_api(host: str, port: int) -> None:
    import uvicorn

    uvicorn.run("md_generator.word.api.main:app", host=host, port=port, factory=False)


def _run_mcp(transport: str, host: str, port: int) -> None:
    from md_generator.word.api.mcp_server import mcp

    kwargs: dict = {}
    if transport in ("http", "sse", "streamable-http"):
        kwargs["host"] = host
        kwargs["port"] = port
    mcp.run(transport=transport, **kwargs)


def main() -> int:
    parser = argparse.ArgumentParser(description="word-to-md runner")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_cli = sub.add_parser("cli", help="Run CLI converter (pass args after --)")
    p_cli.add_argument(
        "remainder",
        nargs=argparse.REMAINDER,
        help="e.g. -- input.docx output.md -v",
    )

    p_api = sub.add_parser("api", help="Run FastAPI + MCP on /mcp")
    p_api.add_argument("--host", default="127.0.0.1")
    p_api.add_argument("--port", type=int, default=8002)

    p_mcp = sub.add_parser("mcp", help="Run standalone MCP server")
    p_mcp.add_argument(
        "--transport",
        default="stdio",
        choices=("stdio", "http", "sse", "streamable-http"),
    )
    p_mcp.add_argument("--host", default="127.0.0.1")
    p_mcp.add_argument("--port", type=int, default=8002)

    args = parser.parse_args()
    if args.cmd == "cli":
        return _run_cli(args.remainder)
    if args.cmd == "api":
        _run_api(args.host, args.port)
        return 0
    if args.cmd == "mcp":
        _run_mcp(args.transport, args.host, args.port)
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
