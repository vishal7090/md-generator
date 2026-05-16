"""Shim CLI: prefer ``md-otel`` after ``pip install mdengine[log,log-otel-proto]``."""

from __future__ import annotations

import sys


def main() -> None:
    from md_generator.otel.cli.main import main as _main

    raise SystemExit(_main(sys.argv[1:]))


if __name__ == "__main__":
    main()
