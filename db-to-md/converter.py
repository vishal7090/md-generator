"""Shim CLI: prefer ``md-db`` after ``pip install mdengine[db]``."""

from __future__ import annotations

import sys


def main() -> None:
    from md_generator.db.cli.main import main as _main

    raise SystemExit(_main(sys.argv[1:]))


if __name__ == "__main__":
    main()
