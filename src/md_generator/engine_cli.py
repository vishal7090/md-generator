from __future__ import annotations

import sys


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if len(argv) < 1 or argv[0] != "db-to-md":
        print("Usage: mdengine db-to-md [--config path] [--type postgres|...] ...", file=sys.stderr)
        return 2
    from md_generator.db.cli.main import main as db_main

    return db_main(argv[1:])


if __name__ == "__main__":
    raise SystemExit(main())
