from __future__ import annotations

from md_generator.db.core.markdown_writer import (
    format_run_readme,
    format_table_markdown,
    slugify_segment,
)
from md_generator.db.core.models import (
    ColumnInfo,
    ForeignKeyInfo,
    IndexInfo,
    RunMetadata,
    TableDetail,
    TableInfo,
)


def test_slugify_segment() -> None:
    assert slugify_segment("users") == "users"
    assert slugify_segment("a/b") == "a_b"
    assert slugify_segment("  ") == "unnamed"


def test_format_table_markdown_snapshot() -> None:
    detail = TableDetail(
        table=TableInfo(schema="public", name="users", comment="App users"),
        columns=(
            ColumnInfo("id", "integer", False, None, "PK"),
            ColumnInfo("email", "text", False, None, None),
        ),
        primary_key=("id",),
        foreign_keys=(
            ForeignKeyInfo(
                "fk_org",
                ("org_id",),
                "public",
                "orgs",
                ("id",),
            ),
        ),
    )
    indexes = (
        IndexInfo("users_email_key", True, ("email",), None),
        IndexInfo("users_org_idx", False, ("org_id",), "CREATE INDEX users_org_idx ON public.users (org_id)"),
    )
    md = format_table_markdown(detail, indexes)
    assert "# Table: `public.users`" in md
    assert "**Comment:** App users" in md
    assert "`id`" in md
    assert "users_email_key" in md
    assert "CREATE INDEX users_org_idx" in md


def test_format_run_readme() -> None:
    meta = RunMetadata(
        db_type="postgres",
        uri_display="postgresql://***@localhost/db",
        schema="public",
        database=None,
        included_features=("tables", "views"),
        limits={"max_tables": 100},
    )
    text = format_run_readme(meta)
    assert "postgres" in text
    assert "public" in text
    assert "tables" in text


def test_format_run_readme_embeds_erd() -> None:
    meta = RunMetadata(
        db_type="postgres",
        uri_display="postgresql://***@localhost/db",
        schema="public",
        database=None,
        included_features=("tables", "erd"),
        limits={},
        erd_artifacts=("erd/full.png", "erd/full.svg"),
        erd_engine="graphviz",
    )
    text = format_run_readme(meta)
    assert "Entity-relationship" in text
    assert "![Entity-relationship overview](erd/full.png)" in text
    assert "[SVG diagram](erd/full.svg)" in text


def test_format_run_readme_mermaid_text_erd() -> None:
    meta = RunMetadata(
        db_type="postgres",
        uri_display="postgresql://***@localhost/db",
        schema="public",
        database=None,
        included_features=("tables", "erd"),
        limits={},
        erd_artifacts=("erd/full.md", "erd/full.mermaid"),
        erd_engine="mermaid_text",
    )
    text = format_run_readme(meta)
    assert "ER diagram (Mermaid)" in text
    assert "erd/full.md" in text
