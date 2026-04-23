from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Callable

from md_generator.db.adapters.factory import create_adapter
from md_generator.db.core.markdown_writer import (
    format_cluster_markdown,
    format_empty_feature_section,
    format_mongo_collection_markdown,
    format_package_markdown,
    format_partition_markdown,
    format_routine_markdown,
    format_sequence_markdown,
    format_table_markdown,
    format_trigger_markdown,
    format_view_markdown,
    slugify_segment,
    ordered_combined_readme_paths,
    write_global_indexes,
    write_run_readme,
    write_text,
)
from md_generator.db.core.erd.pipeline import count_erd_render_steps, write_erd_outputs
from md_generator.db.core.erd.render import try_resolve_dot_executable
from md_generator.db.core.models import RunMetadata, TableDetail, TableInfo
from md_generator.db.core.run_config import RunConfig
from md_generator.db.core.util import redact_uri

logger = logging.getLogger(__name__)


def _emit(
    on_progress: Callable[[int, str], None] | None,
    pct: int,
    current: str,
) -> None:
    if on_progress:
        on_progress(pct, current)


def _scope_label(cfg: RunConfig) -> str | None:
    return cfg.schema or cfg.database


def _flush_combined(
    root: Path,
    rel_path: str,
    parts: list[tuple[str, str]],
    *,
    on_file: Callable[[Path], None] | None,
) -> None:
    if not parts:
        return
    body = "\n\n---\n\n".join(b for _, b in sorted(parts, key=lambda x: x[0]))
    p = root / rel_path
    write_text(p, body)
    if on_file:
        on_file(p)


def _remove_stale_split_readme(root: Path, subdir: str) -> None:
    """Drop `subdir/README.md` left from a prior run when this export has real objects."""
    p = root / subdir / "README.md"
    if p.is_file():
        p.unlink()


def _write_empty_feature_dir(
    root: Path,
    subdir: str,
    title: str,
    scope: str | None,
    *,
    split_files: bool,
    combined_filename: str,
    on_file: Callable[[Path], None] | None,
) -> None:
    body = format_empty_feature_section(title, scope)
    if split_files:
        p = root / subdir / "README.md"
    else:
        p = root / combined_filename
    write_text(p, body)
    if on_file:
        on_file(p)


def extract_to_markdown(
    cfg: RunConfig,
    *,
    on_progress: Callable[[int, str], None] | None = None,
    on_file: Callable[[Path], None] | None = None,
) -> Path:
    """Run introspection and write Markdown under cfg.output_path. Returns output root."""
    if not cfg.uri:
        raise ValueError("database.uri is required")

    adapter = create_adapter(
        cfg.db_type,
        cfg.uri,
        schema=cfg.schema,
        database=cfg.database,
        limits=cfg.limits,
    )
    try:
        adapter.validate_connection()
    except Exception as e:
        raise RuntimeError(f"Database connection failed: {e}") from e

    feats = cfg.effective_features()
    root = cfg.output_path.resolve()
    root.mkdir(parents=True, exist_ok=True)

    per_table_indexes: dict[str, tuple] = {}
    ordered_table_details: list[TableDetail] = []
    erd_artifact_paths: tuple[str, ...] = ()
    erd_note: str | None = None
    erd_engine: str | None = None
    bundle_paths_written: list[str] = []

    try:
        if adapter.db_type == "mongo":
            if "mongodb_collections" in feats:
                cols = adapter.get_collections()
                n = max(len(cols), 1)
                combined: list[tuple[str, str]] = []
                for i, c in enumerate(cols):
                    body = format_mongo_collection_markdown(c)
                    if cfg.split_files:
                        p = root / "mongodb" / "collections" / f"{slugify_segment(c.name)}.md"
                        write_text(p, body)
                        if on_file:
                            on_file(p)
                        combined.append((c.name, body))
                    else:
                        combined.append((c.name, body))
                    _emit(on_progress, int(20 + 70 * (i + 1) / n), f"mongodb/collections/{c.name}")
                if cfg.split_files and cfg.write_combined_feature_markdown and combined:
                    _flush_combined(root, "mongodb/collections.md", combined, on_file=on_file)
                    bundle_paths_written.append("mongodb/collections.md")
                elif not cfg.split_files and combined:
                    _flush_combined(root, "mongodb/collections.md", combined, on_file=on_file)
                    bundle_paths_written.append("mongodb/collections.md")
            if "erd" in feats:
                erd_note = "ER diagrams are not generated for MongoDB exports (no relational FK metadata)."
            merge_paths = (
                ordered_combined_readme_paths(bundle_paths_written)
                if cfg.readme_feature_merge != "none"
                else ()
            )
            meta = RunMetadata(
                db_type=adapter.db_type,
                uri_display=redact_uri(cfg.uri),
                schema=cfg.schema,
                database=cfg.database,
                included_features=tuple(sorted(feats)),
                limits=dict(cfg.limits),
                erd_artifacts=(),
                erd_note=erd_note,
                erd_engine=None,
                readme_feature_merge=cfg.readme_feature_merge,
                combined_readme_paths=merge_paths,
            )
            readme = write_run_readme(root, meta)
            if on_file:
                on_file(readme)
            _emit(on_progress, 100, "README.md")
            return root

        workers = max(1, min(cfg.workers, 32))

        if "tables" in feats:
            tables = adapter.get_tables()
            max_t = int(cfg.limits.get("max_tables", 10_000))
            tables = tables[:max_t]
            tables_sorted = sorted(tables, key=lambda t: (t.schema, t.name))
            nt = max(len(tables_sorted), 1)

            def one_table(tbl: TableInfo) -> tuple[str, str, tuple, TableDetail]:
                detail = adapter.get_table_detail(tbl)
                idxs = tuple(adapter.get_indexes(tbl))
                key = f"{tbl.schema}.{tbl.name}" if tbl.schema else tbl.name
                md = format_table_markdown(detail, idxs)
                return key, md, idxs, detail

            table_parts: list[tuple[str, str]] = []
            detail_by_key: dict[str, TableDetail] = {}
            with ThreadPoolExecutor(max_workers=workers) as ex:
                futs = {ex.submit(one_table, t): t for t in tables_sorted}
                done = 0
                for fut in as_completed(futs):
                    key, md, idxs, detail = fut.result()
                    per_table_indexes[key] = idxs
                    detail_by_key[key] = detail
                    t = futs[fut]
                    sort_key = f"{t.schema}.{t.name}" if t.schema else t.name
                    table_parts.append((sort_key, md))
                    if cfg.split_files:
                        fname = slugify_segment(f"{t.schema}_{t.name}" if t.schema else t.name) + ".md"
                        p = root / "tables" / fname
                        write_text(p, md)
                        if on_file:
                            on_file(p)
                    done += 1
                    _emit(on_progress, int(5 + 40 * done / nt), f"tables/{sort_key}")
            if cfg.split_files:
                if cfg.write_combined_feature_markdown and table_parts:
                    _flush_combined(root, "tables.md", table_parts, on_file=on_file)
                    bundle_paths_written.append("tables.md")
            elif table_parts:
                _flush_combined(root, "tables.md", table_parts, on_file=on_file)
                bundle_paths_written.append("tables.md")
            ordered_table_details = []
            for t in tables_sorted:
                k = f"{t.schema}.{t.name}" if t.schema else t.name
                d = detail_by_key.get(k)
                if d is not None:
                    ordered_table_details.append(d)

        if "erd" in feats and "tables" in feats and adapter.db_type != "mongo":
            if not ordered_table_details:
                erd_note = "ERD skipped (no tables exported)."
            else:
                dot_ok = try_resolve_dot_executable() is not None
                total_steps = max(1, count_erd_render_steps(ordered_table_details, cfg.erd, dot_available=dot_ok))
                step = [0]

                def on_erd_step(msg: str) -> None:
                    step[0] += 1
                    pct = 82 + min(13, int(13 * step[0] / total_steps))
                    _emit(on_progress, pct, msg)

                try:
                    erd_res = write_erd_outputs(
                        root,
                        ordered_table_details,
                        cfg.erd,
                        on_step=on_erd_step,
                    )
                    erd_artifact_paths = erd_res.artifacts
                    erd_engine = erd_res.engine
                except Exception as e:
                    logger.exception("ERD generation failed")
                    raise RuntimeError(f"ERD generation failed: {e}") from e
        elif "erd" in feats and "tables" not in feats:
            erd_note = "ERD skipped (enable the `tables` feature so foreign keys can be introspected)."

        if "indexes" in feats and per_table_indexes:
            p = write_global_indexes(
                root,
                per_table_indexes,
                write_root_bundle=cfg.write_combined_feature_markdown,
            )
            if on_file:
                on_file(p)
            if cfg.write_combined_feature_markdown:
                ip = root / "indexes.md"
                if ip.is_file():
                    bundle_paths_written.append("indexes.md")
                    if on_file:
                        on_file(ip)

        def write_simple(subdir: str, name: str, body: str) -> Path:
            p = root / subdir / f"{slugify_segment(name)}.md"
            write_text(p, body)
            return p

        if "views" in feats:
            views = adapter.get_views()
            vparts: list[tuple[str, str]] = []
            for v in views:
                body = format_view_markdown(v)
                title = f"{v.schema}.{v.name}" if v.schema else v.name
                vparts.append((title, body))
                if cfg.split_files:
                    p = write_simple("views", title, body)
                    if on_file:
                        on_file(p)
            if cfg.split_files and views:
                _remove_stale_split_readme(root, "views")
            scope = _scope_label(cfg)
            if cfg.split_files:
                if not views:
                    _write_empty_feature_dir(
                        root,
                        "views",
                        "Views",
                        scope,
                        split_files=True,
                        combined_filename="views.md",
                        on_file=on_file,
                    )
                elif cfg.write_combined_feature_markdown and vparts:
                    _flush_combined(root, "views.md", vparts, on_file=on_file)
                    bundle_paths_written.append("views.md")
            elif vparts:
                _flush_combined(root, "views.md", vparts, on_file=on_file)
                bundle_paths_written.append("views.md")
            else:
                _write_empty_feature_dir(
                    root,
                    "views",
                    "Views",
                    scope,
                    split_files=False,
                    combined_filename="views.md",
                    on_file=on_file,
                )

        if "functions" in feats:
            funcs = adapter.get_functions()
            acc: list[tuple[str, str]] = []
            for r in funcs:
                title = f"{r.schema}.{r.name}" if r.schema else r.name
                body = format_routine_markdown(r)
                acc.append((title, body))
                if cfg.split_files:
                    p = write_simple("functions", title, body)
                    if on_file:
                        on_file(p)
            if cfg.split_files and funcs:
                _remove_stale_split_readme(root, "functions")
            scope = _scope_label(cfg)
            if cfg.split_files:
                if not funcs:
                    _write_empty_feature_dir(
                        root,
                        "functions",
                        "Functions",
                        scope,
                        split_files=True,
                        combined_filename="functions.md",
                        on_file=on_file,
                    )
                elif cfg.write_combined_feature_markdown and acc:
                    _flush_combined(root, "functions.md", acc, on_file=on_file)
                    bundle_paths_written.append("functions.md")
            elif acc:
                _flush_combined(root, "functions.md", acc, on_file=on_file)
                bundle_paths_written.append("functions.md")
            else:
                _write_empty_feature_dir(
                    root,
                    "functions",
                    "Functions",
                    scope,
                    split_files=False,
                    combined_filename="functions.md",
                    on_file=on_file,
                )

        if "procedures" in feats:
            procs = adapter.get_procedures()
            acc = []
            for r in procs:
                title = f"{r.schema}.{r.name}" if r.schema else r.name
                body = format_routine_markdown(r)
                acc.append((title, body))
                if cfg.split_files:
                    p = write_simple("procedures", title, body)
                    if on_file:
                        on_file(p)
            if cfg.split_files and procs:
                _remove_stale_split_readme(root, "procedures")
            scope = _scope_label(cfg)
            if cfg.split_files:
                if not procs:
                    _write_empty_feature_dir(
                        root,
                        "procedures",
                        "Stored procedures",
                        scope,
                        split_files=True,
                        combined_filename="procedures.md",
                        on_file=on_file,
                    )
                elif cfg.write_combined_feature_markdown and acc:
                    _flush_combined(root, "procedures.md", acc, on_file=on_file)
                    bundle_paths_written.append("procedures.md")
            elif acc:
                _flush_combined(root, "procedures.md", acc, on_file=on_file)
                bundle_paths_written.append("procedures.md")
            else:
                _write_empty_feature_dir(
                    root,
                    "procedures",
                    "Stored procedures",
                    scope,
                    split_files=False,
                    combined_filename="procedures.md",
                    on_file=on_file,
                )

        if "triggers" in feats:
            trigs = adapter.get_triggers()
            acc = []
            for tr in trigs:
                title = f"{tr.schema}.{tr.name}" if tr.schema else tr.name
                body = format_trigger_markdown(tr)
                acc.append((title, body))
                if cfg.split_files:
                    p = write_simple("triggers", title, body)
                    if on_file:
                        on_file(p)
            scope = _scope_label(cfg)
            if cfg.split_files:
                if not trigs:
                    _write_empty_feature_dir(
                        root,
                        "triggers",
                        "Triggers",
                        scope,
                        split_files=True,
                        combined_filename="triggers.md",
                        on_file=on_file,
                    )
                elif cfg.write_combined_feature_markdown and acc:
                    _flush_combined(root, "triggers.md", acc, on_file=on_file)
                    bundle_paths_written.append("triggers.md")
            elif acc:
                _flush_combined(root, "triggers.md", acc, on_file=on_file)
                bundle_paths_written.append("triggers.md")
            else:
                _write_empty_feature_dir(
                    root,
                    "triggers",
                    "Triggers",
                    scope,
                    split_files=False,
                    combined_filename="triggers.md",
                    on_file=on_file,
                )

        if "sequences" in feats:
            acc = []
            for s in adapter.get_sequences():
                title = f"{s.schema}.{s.name}" if s.schema else s.name
                body = format_sequence_markdown(s)
                acc.append((title, body))
                if cfg.split_files:
                    p = write_simple("sequences", title, body)
                    if on_file:
                        on_file(p)
            if cfg.split_files:
                if cfg.write_combined_feature_markdown and acc:
                    _flush_combined(root, "sequences.md", acc, on_file=on_file)
                    bundle_paths_written.append("sequences.md")
            elif acc:
                _flush_combined(root, "sequences.md", acc, on_file=on_file)
                bundle_paths_written.append("sequences.md")

        if "partitions" in feats:
            acc = []
            for part in adapter.get_partitions():
                title = f"{part.schema}.{part.parent_table}.{part.name}"
                body = format_partition_markdown(part)
                acc.append((title, body))
                if cfg.split_files:
                    path = write_simple("partitions", title, body)
                    if on_file:
                        on_file(path)
            if cfg.split_files:
                if cfg.write_combined_feature_markdown and acc:
                    _flush_combined(root, "partitions.md", acc, on_file=on_file)
                    bundle_paths_written.append("partitions.md")
            elif acc:
                _flush_combined(root, "partitions.md", acc, on_file=on_file)
                bundle_paths_written.append("partitions.md")

        if "oracle_packages" in feats:
            acc = []
            for pkg in adapter.get_packages():
                title = f"{pkg.schema}.{pkg.name}"
                body = format_package_markdown(pkg)
                acc.append((title, body))
                if cfg.split_files:
                    path = write_simple("oracle/packages", title, body)
                    if on_file:
                        on_file(path)
            if cfg.split_files:
                if cfg.write_combined_feature_markdown and acc:
                    _flush_combined(root, "oracle/packages.md", acc, on_file=on_file)
                    bundle_paths_written.append("oracle/packages.md")
            elif acc:
                _flush_combined(root, "oracle/packages.md", acc, on_file=on_file)
                bundle_paths_written.append("oracle/packages.md")

        if "oracle_clusters" in feats:
            acc = []
            for c in adapter.get_clusters():
                title = f"{c.schema}.{c.name}"
                body = format_cluster_markdown(c)
                acc.append((title, body))
                if cfg.split_files:
                    path = write_simple("oracle/clusters", title, body)
                    if on_file:
                        on_file(path)
            if cfg.split_files:
                if cfg.write_combined_feature_markdown and acc:
                    _flush_combined(root, "oracle/clusters.md", acc, on_file=on_file)
                    bundle_paths_written.append("oracle/clusters.md")
            elif acc:
                _flush_combined(root, "oracle/clusters.md", acc, on_file=on_file)
                bundle_paths_written.append("oracle/clusters.md")

    finally:
        adapter.close()

    if adapter.db_type != "mongo":
        merge_paths = (
            ordered_combined_readme_paths(bundle_paths_written)
            if cfg.readme_feature_merge != "none"
            else ()
        )
        meta = RunMetadata(
            db_type=adapter.db_type,
            uri_display=redact_uri(cfg.uri),
            schema=cfg.schema,
            database=cfg.database,
            included_features=tuple(sorted(feats)),
            limits=dict(cfg.limits),
            erd_artifacts=erd_artifact_paths,
            erd_note=erd_note,
            erd_engine=erd_engine,
            readme_feature_merge=cfg.readme_feature_merge,
            combined_readme_paths=merge_paths,
        )
        readme = write_run_readme(root, meta)
        if on_file:
            on_file(readme)
        _emit(on_progress, 98, "README.md")

    _emit(on_progress, 100, "completed")
    return root
