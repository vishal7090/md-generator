from __future__ import annotations

import os


def main() -> None:
    import uvicorn

    host = os.environ.get("GRAPH_TO_MD_HOST", "127.0.0.1")
    port = int(os.environ.get("GRAPH_TO_MD_PORT", "8012"))
    uvicorn.run("md_generator.graph.api.main:app", host=host, port=port, reload=False)


if __name__ == "__main__":
    main()
