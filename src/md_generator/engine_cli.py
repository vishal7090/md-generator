from __future__ import annotations

import sys


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if len(argv) < 1:
        print(
            "Usage: mdengine ai assist … | mdengine ai export … | mdengine skill build … | mdengine db-to-md … | "
            "mdengine graph-to-md … | mdengine openapi-to-md generate … | mdengine codeflow-to-md scan …",
            file=sys.stderr,
        )
        return 2
    if argv[0] == "skill":
        if len(argv) >= 2 and argv[1] == "build":
            from md_generator.tools.skill_builder.__main__ import main as skill_build_main

            return skill_build_main(argv[2:])
        print(
            "Usage: mdengine skill build … [--since GIT_REF] [--root PATH]",
            file=sys.stderr,
        )
        return 2
    if argv[0] == "ai" and len(argv) >= 2:
        sub, rest = argv[1], argv[2:]
        if sub == "assist":
            from md_generator.tools.assistant.cli import run_assist

            return run_assist(rest)
        if sub == "export":
            from md_generator.tools.assistant.cli import run_export

            return run_export(rest)
        print(
            "Usage: mdengine ai assist … | mdengine ai export …",
            file=sys.stderr,
        )
        return 2
    if argv[0] == "db-to-md":
        from md_generator.db.cli.main import main as db_main

        return db_main(argv[1:])
    if argv[0] == "graph-to-md":
        from md_generator.graph.cli.main import main as graph_main

        return graph_main(argv[1:])
    if argv[0] == "openapi-to-md":
        from md_generator.openapi.cli.main import main as openapi_main

        return openapi_main(argv[1:])
    if argv[0] == "codeflow-to-md":
        from md_generator.codeflow.cli.main import main as cf_main

        return cf_main(argv[1:])
    print(
        "Usage: mdengine ai assist … | mdengine ai export … | mdengine skill build … | mdengine db-to-md … | "
        "mdengine graph-to-md … | mdengine openapi-to-md generate … | mdengine codeflow-to-md scan …",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
