"""Shim CLI: prefer ``md-log`` after ``pip install mdengine[log]``."""

from __future__ import annotations

import sys


def main() -> None:
    from md_generator.log.cli.main import main as _main

    raise SystemExit(_main(sys.argv[1:]))


if __name__ == "__main__":
    main()
