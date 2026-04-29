from __future__ import annotations

import argparse
import sys
from pathlib import Path


def _find_repo_root(start: Path) -> Path:
    cur = start.resolve()
    for p in (cur, *cur.parents):
        if (p / "pyproject.toml").is_file():
            return p
    raise RuntimeError(f"No pyproject.toml found above {start}")


_REPO_ROOT = _find_repo_root(Path(__file__).resolve().parent)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="mdengine skill build",
        description="Generate AI skills, dependency graph, and registry routing.",
    )
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
    from .generate import run_generate

    run_generate(args.root, since_ref=args.since)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
