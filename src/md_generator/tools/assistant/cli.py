from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .adapters import to_claude_project_prompt, to_cursor_rules_markdown, to_openai_messages
from .agent import MasterAgent
from .registry import Registry


def _configure_stdout() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except (OSError, ValueError):
            pass


def _apply_ai_root(ai_root: str | None) -> None:
    if ai_root:
        import os

        os.environ["MDENGINE_SKILL_AI_ROOT"] = ai_root


def run_assist(argv: list[str] | None, *, prog: str | None = None) -> int:
    """Assemble skill context for a natural-language query (stdout). Used by ``mdengine ai assist``."""
    _configure_stdout()
    p = argparse.ArgumentParser(prog=prog or "mdengine ai assist")
    p.add_argument("query", nargs="+", help="Natural language query")
    p.add_argument("--rag", action="store_true", help="Use Chroma RAG when installed.")
    p.add_argument("--ai-root", type=str, default=None, help="Override MDENGINE_SKILL_AI_ROOT for this run.")
    args = p.parse_args(argv)
    _apply_ai_root(args.ai_root)
    reg = Registry.load_default()
    agent = MasterAgent(reg)
    q = " ".join(args.query)
    res = agent.ask(q, use_rag=args.rag)
    sys.stdout.write(res.context_markdown)
    if not res.context_markdown.endswith("\n"):
        sys.stdout.write("\n")
    return 0


def run_export(argv: list[str] | None, *, prog: str | None = None) -> int:
    """Export assembled context for OpenAI / Claude / Cursor. Used by ``mdengine ai export``."""
    _configure_stdout()
    p = argparse.ArgumentParser(prog=prog or "mdengine ai export")
    p.add_argument("--format", choices=("openai", "claude", "cursor"), required=True)
    p.add_argument("--query", required=True, help="Natural language query")
    p.add_argument("--output", "-o", type=str, default=None, help="Write to file instead of stdout.")
    p.add_argument("--rag", action="store_true", help="Use Chroma RAG when installed.")
    p.add_argument("--ai-root", type=str, default=None, help="Override MDENGINE_SKILL_AI_ROOT for this run.")
    args = p.parse_args(argv)
    _apply_ai_root(args.ai_root)
    reg = Registry.load_default()
    agent = MasterAgent(reg)
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


def main(argv: list[str] | None = None) -> int:
    """Legacy entry point for ``mdengine-skill`` (``ask`` / ``export``). Prefer ``mdengine ai assist`` / ``mdengine ai export``."""
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        print(
            "Usage: mdengine-skill ask … | mdengine-skill export …",
            file=sys.stderr,
        )
        print("Prefer: mdengine ai assist … | mdengine ai export …", file=sys.stderr)
        return 2
    cmd, rest = argv[0], argv[1:]
    if cmd == "ask":
        return run_assist(rest, prog="mdengine-skill ask")
    if cmd == "export":
        return run_export(rest, prog="mdengine-skill export")
    print(f"Unknown command {cmd!r}. Expected 'ask' or 'export'.", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
