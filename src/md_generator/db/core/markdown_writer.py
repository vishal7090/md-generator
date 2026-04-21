from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Iterable

from md_generator.db.core.models import (
    ClusterInfo,
    ColumnInfo,
    ForeignKeyInfo,
    IndexInfo,
    MongoCollectionInfo,
    MongoIndexInfo,
    PackageInfo,
    PartitionInfo,
    RoutineInfo,
    RunMetadata,
    SequenceInfo,
    TableDetail,
    TriggerInfo,
    ViewInfo,
)


def slugify_segment(name: str, max_len: int = 120) -> str:
    """Filesystem-safe, deterministic slug for a single path segment."""
    s = name.strip()
    s = re.sub(r"[^\w.\-]+", "_", s, flags=re.UNICODE)
    s = s.strip("._") or "unnamed"
    if len(s) > max_len:
        s = s[:max_len].rstrip("._")
    return s or "unnamed"


def _md_escape_cell(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ")


def _columns_table(columns: tuple[ColumnInfo, ...]) -> str:
    lines = [
        "| Column | Type | Nullable | Default | Comment |",
        "| --- | --- | --- | --- | --- |",
    ]
    for c in columns:
        lines.append(
            "| "
            + " | ".join(
                [
                    _md_escape_cell(c.name),
                    _md_escape_cell(c.data_type),
                    "yes" if c.nullable else "no",
                    _md_escape_cell(c.default or ""),
                    _md_escape_cell(c.comment or ""),
                ]
            )
            + " |"
        )
    return "\n".join(lines) + "\n"


def _fk_table(fks: tuple[ForeignKeyInfo, ...]) -> str:
    if not fks:
        return "_No foreign keys._\n"
    lines = [
        "| FK | Columns | Refers to | Ref columns |",
        "| --- | --- | --- | --- |",
    ]
    for fk in fks:
        ref = f"{fk.referred_schema + '.' if fk.referred_schema else ''}{fk.referred_table}"
        lines.append(
            "| "
            + " | ".join(
                [
                    _md_escape_cell(fk.name or ""),
                    _md_escape_cell(", ".join(fk.constrained_columns)),
                    _md_escape_cell(ref),
                    _md_escape_cell(", ".join(fk.referred_columns)),
                ]
            )
            + " |"
        )
    return "\n".join(lines) + "\n"


def _indexes_section(indexes: tuple[IndexInfo, ...]) -> str:
    if not indexes:
        return "_No indexes._\n"
    parts: list[str] = []
    for ix in indexes:
        uniq = "unique" if ix.unique else "non-unique"
        cols = ", ".join(ix.columns)
        parts.append(f"### `{ix.name}` ({uniq})\n\n- Columns: `{cols}`\n")
        if ix.definition:
            parts.append("\n```sql\n" + ix.definition.strip() + "\n```\n")
    return "\n".join(parts)


def format_table_markdown(detail: TableDetail, indexes: tuple[IndexInfo, ...]) -> str:
    t = detail.table
    title = f"{t.schema}.{t.name}" if t.schema else t.name
    lines = [
        f"# Table: `{title}`\n",
    ]
    if t.comment:
        lines.append(f"**Comment:** {t.comment}\n")
    pk = ", ".join(f"`{c}`" for c in detail.primary_key) if detail.primary_key else "_None_"
    lines.append(f"## Primary key\n\n{pk}\n")
    lines.append("## Columns\n\n")
    lines.append(_columns_table(detail.columns))
    lines.append("## Foreign keys\n\n")
    lines.append(_fk_table(detail.foreign_keys))
    lines.append("## Indexes (on this table)\n\n")
    lines.append(_indexes_section(indexes))
    return "\n".join(lines)


def format_view_markdown(v: ViewInfo) -> str:
    title = f"{v.schema}.{v.name}" if v.schema else v.name
    body = ["# View: `" + title + "`\n"]
    if v.definition:
        body.append("## Definition\n\n```sql\n" + v.definition.strip() + "\n```\n")
    else:
        body.append("_Definition not available._\n")
    return "\n".join(body)


def format_routine_markdown(r: RoutineInfo) -> str:
    title = f"{r.schema}.{r.name}" if r.schema else r.name
    body = [f"# {r.kind.title()}: `{title}`\n"]
    if r.language:
        body.append(f"**Language:** {r.language}\n")
    if r.definition:
        body.append("\n## Definition\n\n```sql\n" + r.definition.strip() + "\n```\n")
    else:
        body.append("\n_Definition not available._\n")
    return "\n".join(body)


def format_trigger_markdown(tr: TriggerInfo) -> str:
    title = f"{tr.schema}.{tr.name}" if tr.schema else tr.name
    tbl = f"{tr.table_schema}.{tr.table_name}" if tr.table_schema else tr.table_name
    parts = [
        f"# Trigger: `{title}`\n",
        f"**Table:** `{tbl}`\n",
    ]
    if tr.timing:
        parts.append(f"**Timing:** {tr.timing}\n")
    if tr.events:
        parts.append(f"**Events:** {tr.events}\n")
    parts.append("\n## Definition\n\n")
    if tr.definition:
        parts.append("```sql\n" + tr.definition.strip() + "\n```\n")
    else:
        parts.append("_Definition not available._\n")
    return "".join(parts)


def format_sequence_markdown(s: SequenceInfo) -> str:
    title = f"{s.schema}.{s.name}" if s.schema else s.name
    parts = [f"# Sequence: `{title}`\n\n"]
    if s.details:
        parts.append("```json\n" + json.dumps(s.details, sort_keys=True, indent=2) + "\n```\n")
    else:
        parts.append("_No extra details._\n")
    return "".join(parts)


def format_partition_markdown(p: PartitionInfo) -> str:
    title = f"{p.schema}.{p.name}" if p.schema else p.name
    parent = f"{p.schema}.{p.parent_table}" if p.schema else p.parent_table
    parts = [f"# Partition: `{title}`\n\n", f"**Parent:** `{parent}`\n"]
    if p.method:
        parts.append(f"**Method:** {p.method}\n")
    if p.expression:
        parts.append("\n## Expression\n\n```\n" + p.expression.strip() + "\n```\n")
    return "".join(parts)


def format_package_markdown(pkg: PackageInfo) -> str:
    title = f"{pkg.schema}.{pkg.name}" if pkg.schema else pkg.name
    parts = [f"# Package: `{title}`\n\n"]
    if pkg.spec_source:
        parts.append("## Specification\n\n```sql\n" + pkg.spec_source.strip() + "\n```\n\n")
    if pkg.body_source:
        parts.append("## Body\n\n```sql\n" + pkg.body_source.strip() + "\n```\n")
    if not pkg.spec_source and not pkg.body_source:
        parts.append("_Sources not available._\n")
    return "".join(parts)


def format_cluster_markdown(c: ClusterInfo) -> str:
    title = f"{c.schema}.{c.name}" if c.schema else c.name
    parts = [f"# Cluster: `{title}`\n\n"]
    if c.details:
        parts.append("```json\n" + json.dumps(c.details, sort_keys=True, indent=2) + "\n```\n")
    else:
        parts.append("_No details._\n")
    return "".join(parts)


def _mongo_index_md(ix: MongoIndexInfo) -> str:
    keys = json.dumps(ix.keys, sort_keys=True)
    u = "unique" if ix.unique else "non-unique"
    return f"- **`{ix.name}`** ({u}): `{keys}`"


def format_mongo_collection_markdown(c: MongoCollectionInfo) -> str:
    parts = [
        f"# Collection: `{c.name}`\n\n",
        f"**Sample size:** {c.sample_size}\n\n",
        "## Inferred schema (from samples)\n\n",
        "```json\n",
        json.dumps(c.inferred_schema, sort_keys=True, indent=2),
        "\n```\n\n## Indexes\n\n",
    ]
    if c.indexes:
        parts.extend(_mongo_index_md(ix) + "\n" for ix in c.indexes)
    else:
        parts.append("_No indexes._\n")
    return "".join(parts)


def format_empty_feature_section(feature_label: str, scope: str | None) -> str:
    """Deterministic placeholder when introspection finds no objects of that kind."""
    loc = f"`{scope}`" if scope else "the target database"
    return f"# {feature_label}\n\n_No {feature_label.lower()} found in {loc}._\n"


def format_run_readme(meta: RunMetadata) -> str:
    feats = ", ".join(meta.included_features) if meta.included_features else "(none)"
    limits = json.dumps(meta.limits, sort_keys=True, indent=2)
    lines = [
        "# Database metadata export\n",
        "This bundle was generated deterministically from database metadata (no LLM).\n",
        "## Run\n",
        f"- **Database type:** `{meta.db_type}`\n",
        f"- **Connection (redacted):** `{meta.uri_display}`\n",
    ]
    if meta.schema is not None:
        lines.append(f"- **Schema:** `{meta.schema}`\n")
    if meta.database is not None:
        lines.append(f"- **Mongo database:** `{meta.database}`\n")
    lines.extend(
        [
            f"- **Generated (UTC):** {meta.generated_at_utc}\n",
            f"- **Included features:** {feats}\n",
            "## Limits\n\n",
            "```json\n",
            limits,
            "\n```\n",
        ]
    )
    if meta.erd_note:
        lines.extend(["## ER diagram\n\n", f"{meta.erd_note}\n\n"])
    elif meta.erd_artifacts:
        if meta.erd_engine == "mermaid_text":
            lines.append("## ER diagram (Mermaid)\n\n")
            lines.append(
                "_Graphviz was not available._ Mermaid sources are in `.mermaid` and fenced `.md` files "
                "(GitHub/GitLab render the latter). Install **`mermaid-py`** with network access to mermaid.ink "
                "for PNG/SVG export.\n\n"
            )
            for p in sorted(x for x in meta.erd_artifacts if x.endswith(".md")):
                lines.append(f"- [`{p}`]({p})\n")
            for p in sorted(x for x in meta.erd_artifacts if x.endswith(".mermaid")):
                lines.append(f"- [`{p}`]({p}) (raw)\n")
            lines.append("\n")
        else:
            title = "Graphviz" if meta.erd_engine == "graphviz" else "Mermaid"
            lines.append(f"## ER diagram ({title})\n\n")
            if meta.erd_engine == "mermaid_py":
                lines.append(
                    "_Graphviz was not available._ PNG/SVG were generated with **mermaid-py** (mermaid.ink).\n\n"
                )
            pngs = [p for p in meta.erd_artifacts if p.endswith(".png")]
            svgs = [p for p in meta.erd_artifacts if p.endswith(".svg")]
            if pngs:
                lines.append(f"![Entity-relationship overview]({pngs[0]})\n\n")
            for s in sorted(set(svgs)):
                lines.append(f"- [SVG diagram]({s})\n")
            if len(pngs) > 1:
                lines.append("\n**Additional PNG exports:**\n\n")
                for p in sorted(set(pngs))[1:]:
                    lines.append(f"- [`{p}`]({p})\n")
            mmd = [p for p in meta.erd_artifacts if p.endswith(".mermaid") or p.endswith(".md")]
            if mmd and meta.erd_engine == "mermaid_py":
                lines.append("\n**Mermaid sources:**\n\n")
                for p in sorted(set(mmd)):
                    lines.append(f"- [`{p}`]({p})\n")
            lines.append("\n")
    lines.extend(
        [
            "## Layout\n",
            "See subdirectories for modular Markdown per object type.\n",
        ]
    )
    return "".join(lines)


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")


def write_run_readme(output_root: Path, meta: RunMetadata) -> Path:
    p = output_root / "README.md"
    write_text(p, format_run_readme(meta))
    return p


def _global_indexes_md(indexes: Iterable[tuple[str, tuple[IndexInfo, ...]]]) -> str:
    rows: list[tuple[str, str, str, str]] = []
    for table_key, ixs in sorted(indexes, key=lambda x: x[0]):
        for ix in sorted(ixs, key=lambda i: i.name):
            rows.append(
                (
                    table_key,
                    ix.name,
                    "yes" if ix.unique else "no",
                    ", ".join(ix.columns),
                )
            )
    if not rows:
        return "_No indexes._\n"
    lines = [
        "# Indexes\n",
        "| Object | Index | Unique | Columns |",
        "| --- | --- | --- | --- |",
    ]
    for t, n, u, c in rows:
        lines.append(
            "| "
            + " | ".join(
                [
                    _md_escape_cell(t),
                    _md_escape_cell(n),
                    u,
                    _md_escape_cell(c),
                ]
            )
            + " |"
        )
    return "\n".join(lines) + "\n"


def write_global_indexes(output_root: Path, per_table: dict[str, tuple[IndexInfo, ...]]) -> Path:
    p = output_root / "indexes" / "README.md"
    write_text(p, _global_indexes_md(list(per_table.items())))
    return p
