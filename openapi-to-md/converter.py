"""Shim CLI: prefer ``md-api`` after ``pip install mdengine[openapi]``."""

from __future__ import annotations

import sys


def main() -> None:
    from md_generator.openapi.cli.main import main as _main

    raise SystemExit(_main(sys.argv[1:]))


if __name__ == "__main__":
    main()
