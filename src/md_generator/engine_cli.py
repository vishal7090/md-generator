from __future__ import annotations

import sys


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if len(argv) < 1:
        print(
            "Usage: mdengine db-to-md ... | mdengine graph-to-md [--config path] [--source networkx|neo4j] ...",
            file=sys.stderr,
        )
        return 2
    if argv[0] == "db-to-md":
        from md_generator.db.cli.main import main as db_main

        return db_main(argv[1:])
    if argv[0] == "graph-to-md":
        from md_generator.graph.cli.main import main as graph_main

        return graph_main(argv[1:])
    print(
        "Usage: mdengine db-to-md ... | mdengine graph-to-md [--config path] [--source networkx|neo4j] ...",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
