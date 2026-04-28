from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .adapters import to_claude_project_prompt, to_cursor_rules_markdown, to_openai_messages
from .agent import MasterAgent
from .registry import Registry


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except (OSError, ValueError):
            pass
    p = argparse.ArgumentParser(prog="mdengine-skill")
    sub = p.add_subparsers(dest="cmd", required=True)

    ask_p = sub.add_parser("ask", help="Print assembled context for a query (stdout).")
    ask_p.add_argument("query", nargs="+", help="Natural language query")
    ask_p.add_argument("--rag", action="store_true", help="Use Chroma RAG when installed.")
    ask_p.add_argument("--ai-root", type=str, default=None, help="Override MDENGINE_SKILL_AI_ROOT for this run.")

    ex_p = sub.add_parser("export", help="Export assembled context in a host-specific shape.")
    ex_p.add_argument("--format", choices=("openai", "claude", "cursor"), required=True)
    ex_p.add_argument("--query", required=True, help="Natural language query")
    ex_p.add_argument("--output", "-o", type=str, default=None, help="Write to file instead of stdout.")
    ex_p.add_argument("--rag", action="store_true", help="Use Chroma RAG when installed.")

    args = p.parse_args(argv)

    if getattr(args, "ai_root", None):
        import os

        os.environ["MDENGINE_SKILL_AI_ROOT"] = args.ai_root

    reg = Registry.load_default()
    agent = MasterAgent(reg)

    if args.cmd == "ask":
        q = " ".join(args.query)
        res = agent.ask(q, use_rag=args.rag)
        sys.stdout.write(res.context_markdown)
        if not res.context_markdown.endswith("\n"):
            sys.stdout.write("\n")
        return 0

    if args.cmd == "export":
        res = agent.ask(args.query, use_rag=args.rag)
        if args.format == "openai":
            out = json.dumps(to_openai_messages(res), indent=2, ensure_ascii=False)
        elif args.format == "claude":
            out = to_claude_project_prompt(res)
        else:
            out = to_cursor_rules_markdown(res)
        if args.output:
            Path(args.output).write_text(out + ("\n" if not out.endswith("\n") else ""), encoding="utf-8")
        else:
            sys.stdout.write(out)
            if not out.endswith("\n"):
                sys.stdout.write("\n")
        return 0

    return 2
