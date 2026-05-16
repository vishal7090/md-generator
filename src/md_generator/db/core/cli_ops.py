from __future__ import annotations

import json
import sys

from md_generator.db.adapters.factory import create_adapter
from md_generator.db.core.run_config import RunConfig


def run_test_connection(cfg: RunConfig) -> int:
    if not cfg.uri:
        print("database.uri is required", file=sys.stderr)
        return 2
    adapter = create_adapter(
        cfg.db_type,
        cfg.uri,
        schema=cfg.schema,
        database=cfg.database,
        limits=cfg.limits,
    )
    try:
        adapter.validate_connection()
        print(f"OK: connected ({adapter.db_type})")
        return 0
    except Exception as e:
        print(f"Connection failed: {e}", file=sys.stderr)
        return 1
    finally:
        adapter.close()


def run_list_schemas(cfg: RunConfig, *, output_format: str = "text") -> int:
    if not cfg.uri:
        print("database.uri is required", file=sys.stderr)
        return 2
    adapter = create_adapter(
        cfg.db_type,
        cfg.uri,
        schema=cfg.schema,
        database=cfg.database,
        limits=cfg.limits,
    )
    try:
        names = adapter.list_schemas()
        if not names and cfg.schema:
            names = [cfg.schema]
        if output_format == "json":
            print(json.dumps({"schemas": names}, indent=2))
        else:
            for n in names:
                print(n)
        return 0
    except Exception as e:
        print(f"list_schemas failed: {e}", file=sys.stderr)
        return 1
    finally:
        adapter.close()
