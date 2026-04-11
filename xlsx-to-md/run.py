from __future__ import annotations

import argparse
import sys


def _strip_leading_ddash(args: list[str]) -> list[str]:
    while args and args[0] == "--":
        args = args[1:]
    return args


def main() -> None:
    p = argparse.ArgumentParser(description="xlsx-to-md runner")
    sub = p.add_subparsers(dest="command", required=True)

    cli_p = sub.add_parser("cli", help="Run CLI (pass flags after -- )")
    cli_p.add_argument("cli_args", nargs=argparse.REMAINDER, default=[])

    api_p = sub.add_parser("api", help="Start FastAPI server")
    api_p.add_argument("--host", default="127.0.0.1")
    api_p.add_argument("--port", type=int, default=8003)

    mcp_p = sub.add_parser("mcp", help="Run MCP server")
    mcp_p.add_argument(
        "--transport",
        choices=("stdio", "streamable-http", "sse"),
        default="stdio",
    )

    ns = p.parse_args()

    if ns.command == "cli":
        from md_generator.xlsx.converter import main as cli_main

        sys.exit(cli_main(_strip_leading_ddash(list(ns.cli_args))))

    if ns.command == "api":
        try:
            import uvicorn
        except ImportError as e:
            print("Install API deps: pip install md-generator[xlsx,api]", file=sys.stderr)
            raise SystemExit(1) from e
        from md_generator.xlsx.api.app import app as api_app

        uvicorn.run(api_app, host=ns.host, port=ns.port)

    elif ns.command == "mcp":
        try:
            from md_generator.xlsx.mcp_server import build_mcp_server
        except ImportError as e:
            print("Install MCP deps: pip install md-generator[mcp]", file=sys.stderr)
            raise SystemExit(1) from e
        mcp = build_mcp_server()
        mcp.run(transport=ns.transport)


if __name__ == "__main__":
    main()
