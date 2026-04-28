from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Repository root (parent of tools/)
_REPO_ROOT = Path(__file__).resolve().parents[2]


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Generate AI skills, dependency graph, and registry routing.")
    p.add_argument(
        "--since",
        metavar="GIT_REF",
        default=None,
        help="Only regenerate area skills touched under src/md_generator since GIT_REF (global/graph/registry still refresh).",
    )
    p.add_argument(
        "--root",
        type=Path,
        default=_REPO_ROOT,
        help="Repository root (default: inferred from this file).",
    )
    args = p.parse_args(argv)
    sys.path.insert(0, str(args.root))
    from tools.skillgen.generate import run_generate

    run_generate(args.root, since_ref=args.since)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
