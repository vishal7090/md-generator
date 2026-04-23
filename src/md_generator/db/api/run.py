from __future__ import annotations

import os


def main() -> None:
    import uvicorn

    host = os.environ.get("DB_TO_MD_HOST", "127.0.0.1")
    port = int(os.environ.get("DB_TO_MD_PORT", "8010"))
    uvicorn.run("md_generator.db.api.main:app", host=host, port=port, reload=False)


if __name__ == "__main__":
    main()
