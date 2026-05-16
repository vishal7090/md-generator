from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from pathlib import Path
from typing import Any

from md_generator.log.aggregation.metrics import RunMetrics
from md_generator.log.core.run_config import log_config_to_jsonable
from md_generator.log.clustering.kmeans_cluster import run_kmeans
from md_generator.log.clustering.vectorizer import tfidf_matrix
from md_generator.log.config.schemas import LogRunConfig
from md_generator.log.core.errors import WriterError
from md_generator.log.core.plugins import load_enrichers, load_parser_plugins, run_enricher_plugins, try_parse_with_plugins
from md_generator.log.enrichment.fingerprinting import add_fingerprint
from md_generator.log.enrichment.pattern_matcher import tag_patterns
from md_generator.log.enrichment.severity_ranker import add_severity_rank
from md_generator.archive.extractors import detect_archive_format
from md_generator.log.ingestion.archive_loader import iter_zip_log_members, sniff_zip
from md_generator.log.ingestion.batch_reader import iter_file_line_batches
from md_generator.log.ingestion.encoding_detector import decode_lines
from md_generator.log.ingestion.file_loader import expand_log_paths
from md_generator.log.ingestion.stream_reader import iter_text_lines, read_file_as_text
from md_generator.log.noise_reduction.filter import apply_noise_filters
from md_generator.runtime.execution_context import ExecutionContext
from md_generator.runtime.metrics import merge_runtime_metrics
from md_generator.log.normalization.token_normalizer import normalize_record
from md_generator.log.parser.models import LogRecord, RunContext
from md_generator.log.parser.multiline_parser import parse_file_lines
from md_generator.log.parser.parser_registry import select_preset_for_sample
from md_generator.log.utils.io import ensure_dir
from md_generator.log.writers.assets_writer import write_run_metadata
from md_generator.log.writers.markdown_writer import render_all


def _effective_max_lines(cfg: LogRunConfig) -> int | None:
    if cfg.chunk.enabled:
        return cfg.chunk.lines_per_chunk
    return cfg.execution.max_lines_per_file


def _parse_virtual_file(zip_path: Path, member: str, raw: bytes, cfg: LogRunConfig) -> list[LogRecord]:
    text = decode_lines(raw, cfg.execution.encoding_fallbacks)
    max_lines = _effective_max_lines(cfg)
    lines = list(iter_text_lines(text, max_lines=max_lines))
    eff_cfg = cfg
    if cfg.parser.auto_detect:
        eff_cfg = _apply_detected_preset(cfg, text[:8192])
    pr = parse_file_lines(zip_path, eff_cfg, lines)
    patched: list[LogRecord] = []
    for r in pr.records:
        md = dict(r.metadata)
        md["zip_member"] = member
        patched.append(replace(r, metadata=md))
    return _post_parse_records(patched, eff_cfg, zip_path)


def _post_parse_records(records: list[LogRecord], cfg: LogRunConfig, _source_hint: Path) -> list[LogRecord]:
    plugins = load_enrichers(cfg.plugins.enrichers)
    out: list[LogRecord] = []
    for r in records:
        r = normalize_record(r, cfg)
        r = add_fingerprint(r)
        r = tag_patterns(r)
        r = add_severity_rank(r)
        r = run_enricher_plugins(r, plugins)
        out.append(r)
    return out


def _parse_line_batch(
    path: Path,
    cfg: LogRunConfig,
    lines: list[tuple[int, str]],
    eff_cfg: LogRunConfig,
) -> tuple[list[LogRecord], int, int, int, int]:
    plugin_result = try_parse_with_plugins(path, eff_cfg, lines)
    if plugin_result is not None:
        pr = plugin_result
    else:
        pr = parse_file_lines(path, eff_cfg, lines)
    recs = _post_parse_records(pr.records, eff_cfg, path)
    return recs, pr.total_lines, pr.malformed_lines, pr.skipped_lines, pr.parse_duration_ms


def _apply_detected_preset(cfg: LogRunConfig, sample: str) -> LogRunConfig:
    from md_generator.log.core.run_config import load_preset

    name = select_preset_for_sample(sample[:8192], preset_dirs=cfg.parser.preset_dirs or None)
    if not name:
        return cfg
    preset_data = load_preset(name, cfg.parser.preset_dirs or None)
    parser_data = preset_data.get("parser") or {}
    return replace(
        cfg,
        parser=replace(
            cfg.parser,
            preset=str(parser_data.get("preset") or name),
            line_regex=parser_data.get("line_regex") if "line_regex" in parser_data else cfg.parser.line_regex,
        ),
    )


def _resolve_eff_cfg(path: Path, cfg: LogRunConfig, sample: str) -> LogRunConfig:
    if not cfg.parser.auto_detect:
        return cfg
    return _apply_detected_preset(cfg, sample)


def _parse_disk_file(path: Path, cfg: LogRunConfig) -> tuple[list[LogRecord], int, int, int, int]:
    max_lines = _effective_max_lines(cfg)
    batch_size = max(100, int(cfg.execution.batch_records))
    if cfg.incremental.enabled:
        from md_generator.log.incremental.checkpoint import load_checkpoint
        from md_generator.log.incremental.resume_reader import iter_new_lines

        ck_path = Path(cfg.incremental.checkpoint_path or (cfg.output_path() / ".checkpoint.json"))
        cp = load_checkpoint(ck_path)
        lines = [(ln, text) for ln, text, _off in iter_new_lines(path, cp)]
        if max_lines is not None:
            lines = lines[:max_lines]
        sample = "\n".join(t for _, t in lines[:50])
        eff_cfg = _resolve_eff_cfg(path, cfg, sample)
        return _parse_line_batch(path, cfg, lines, eff_cfg)

    all_recs: list[LogRecord] = []
    total_lines = malformed = skipped = 0
    duration_ms = 0
    eff_cfg = cfg
    first_sample = ""
    for batch in iter_file_line_batches(
        path,
        cfg.execution.encoding_fallbacks,
        max_lines_per_batch=batch_size,
        max_lines_total=max_lines,
    ):
        if not first_sample and batch:
            first_sample = batch[0][1]
            eff_cfg = _resolve_eff_cfg(path, cfg, first_sample)
        recs, tl, ml, sl, pd_ms = _parse_line_batch(path, cfg, batch, eff_cfg)
        all_recs.extend(recs)
        total_lines += tl
        malformed += ml
        skipped += sl
        duration_ms += pd_ms
    if not all_recs and batch_size > 0:
        text, _n = read_file_as_text(path, cfg.execution.encoding_fallbacks, max_lines)
        eff_cfg = _resolve_eff_cfg(path, cfg, text)
        lines = list(iter_text_lines(text, max_lines=max_lines))
        return _parse_line_batch(path, cfg, lines, eff_cfg)
    return all_recs, total_lines, malformed, skipped, duration_ms


def _expand_paths(cfg: LogRunConfig, paths: list[Path]) -> list[Path]:
    import shutil
    import tempfile

    out: list[Path] = []
    for path in paths:
        if cfg.ingestion.use_archive_bridge and detect_archive_format(path):
            from md_generator.log.ingestion.archive_bridge import iter_log_files_from_archive

            staging = Path(tempfile.mkdtemp(prefix="md-log-archive-")) / path.stem
            staging.mkdir(parents=True, exist_ok=True)
            for extracted in iter_log_files_from_archive(path, cleanup=cfg.ingestion.archive_cleanup):
                dest = staging / extracted.name
                if extracted.resolve() != dest.resolve():
                    shutil.copy2(extracted, dest)
                out.append(dest)
        else:
            out.append(path)
    return out or paths


def run_pipeline(ctx: RunContext) -> RunContext:
    cfg = ctx.config
    exec_ctx = ExecutionContext()
    paths = _expand_paths(cfg, expand_log_paths(cfg.resolved_input_paths()))
    if not paths:
        raise ValueError("No input files: set input.paths in config or CLI --input")

    if cfg.execution.distributed and len(paths) > 1:
        from md_generator.distributed.worker_pool import process_files_distributed

        staging = cfg.output_path() / ".staging"
        process_files_distributed(paths, staging, cfg.execution.workers)

    metrics = RunMetrics()
    all_records: list[LogRecord] = []

    for path in paths:
        if sniff_zip(path):
            metrics.files_parsed += 1
            for member, raw in iter_zip_log_members(path):
                try:
                    recs = _parse_virtual_file(path, member, raw, cfg)
                except Exception:
                    continue
                all_records.extend(recs)
                metrics.add_records(len(recs))
        else:
            metrics.files_parsed += 1
            recs, tl, ml, sl, pd_ms = _parse_disk_file(path, cfg)
            metrics.merge_parse(lines=tl, malformed=ml, skipped=sl, duration_ms=pd_ms)
            metrics.add_records(len(recs))
            all_records.extend(recs)

    if cfg.noise_reduction.enabled:
        all_records = apply_noise_filters(all_records, cfg)
    if cfg.governance.enabled and cfg.governance.classify_pii:
        from md_generator.governance.classification import classify_records

        all_records = classify_records(all_records)

    cluster_labels: list[int] | None = None
    if cfg.clustering.enabled and len(all_records) > 0:
        try:
            texts = [r.message for r in all_records]
            _, X = tfidf_matrix(texts, max_features=cfg.clustering.max_features)
            n_clust = max(1, min(cfg.clustering.n_clusters, len(texts)))
            raw_labels = run_kmeans(
                X,
                n_clusters=n_clust,
                random_state=cfg.clustering.random_state,
            )
            cluster_labels = [int(x) for x in raw_labels]
            updated: list[LogRecord] = []
            for r, lab in zip(all_records, cluster_labels):
                md = dict(r.metadata)
                md["cluster"] = lab
                updated.append(replace(r, metadata=md))
            all_records = updated
        except ImportError:
            cluster_labels = None

    out = cfg.output_path()
    ensure_dir(out)
    did_cluster = cluster_labels is not None
    out_cfg = replace(
        cfg.output,
        generate_clusters=cfg.output.generate_clusters or did_cluster,
    )
    cfg_render = replace(cfg, output=out_cfg)

    try:
        render_all(out, all_records, cfg_render, cluster_labels=cluster_labels)
        incidents: list = []
        if cfg.output.generate_incidents:
            from md_generator.log.incidents.incident_engine import build_incidents
            from md_generator.log.writers.incident_writer import write_incidents as write_incident_files

            incidents = build_incidents(all_records, cfg)
            write_incident_files(out, all_records, cfg)
        if cfg.chunking.enabled or cfg.output.generate_chunks or cfg.embeddings.enabled or cfg.embeddings.exporters:
            from md_generator.log.writers.chunk_writer import write_semantic_chunks

            chunks = write_semantic_chunks(out, all_records, incidents, cfg)
        else:
            chunks = []
        if cfg.embeddings.enabled or cfg.embeddings.exporters:
            from md_generator.log.embeddings.embedding_exporter import export_embeddings

            export_embeddings(out, chunks, cfg)
        if cfg.correlation.enabled:
            from md_generator.log.writers.correlation_writer import write_correlation_artifacts

            ensure_dir(out / "correlation")
            write_correlation_artifacts(out, all_records)
        if cfg.knowledge_graph.enabled:
            from md_generator.log.knowledge_graph.graph_exporter import export_graph

            ensure_dir(out / "graphs")
            export_graph(out, all_records, cfg)
        if cfg.timeline.enabled:
            from md_generator.log.timeline.timeline_engine import write_timeline_artifacts

            ensure_dir(out / "timeline")
            write_timeline_artifacts(out, all_records, incidents, cfg)
        if cfg.intelligence.enabled:
            from md_generator.log.intelligence.root_cause_engine import write_root_cause_artifacts

            ensure_dir(out / "intelligence")
            write_root_cause_artifacts(out, incidents)
        if cfg.visualization.enabled:
            from md_generator.log.utils.io import write_text
            from md_generator.log.visualization.mermaid_timeline import render_timeline_mermaid
            from md_generator.log.visualization.mermaid_topology import render_topology_mermaid

            viz = out / "visualizations"
            ensure_dir(viz)
            write_text(viz / "timeline.mmd.md", render_timeline_mermaid(all_records))
            write_text(viz / "topology.mmd.md", render_topology_mermaid(all_records))
        if cfg.documentation.enabled:
            from md_generator.log.documentation.incident_summary import write_incident_summaries
            from md_generator.log.documentation.service_report import write_service_reports
            from md_generator.log.documentation.troubleshooting import write_troubleshooting_guides

            write_incident_summaries(out, incidents)
            write_service_reports(out, all_records)
            write_troubleshooting_guides(out, incidents)
        if cfg.topology.enabled:
            from md_generator.log.topology.discovery import discover_topology, topology_to_mermaid
            from md_generator.log.utils.io import write_text

            g = discover_topology(all_records)
            ensure_dir(out / "topology")
            write_text(out / "topology" / "service_map.mmd.md", topology_to_mermaid(g))
        if cfg.linking.enabled:
            from md_generator.log.linking.link_graph import build_link_graph, write_link_index

            write_link_index(out, build_link_graph(all_records, incidents))
        if cfg.correlation.cross_source:
            from md_generator.log.correlation.cross_source import (
                correlate_cross_source,
                render_cross_source_markdown,
            )
            from md_generator.log.utils.io import write_text

            otel = cfg.resolved_otel_path()
            result = correlate_cross_source(
                all_records,
                otel,
                window_seconds=cfg.correlation.timeline_window_seconds,
            )
            ensure_dir(out / "correlation")
            write_text(out / "correlation" / "cross_source.md", render_cross_source_markdown(result))
        if cfg.governance.enabled:
            from md_generator.governance.audit import build_audit_block
            from md_generator.governance.retention import retention_metadata

            manifest = out / "governance" / "manifest.json"
            ensure_dir(manifest.parent)
            cfg_blob = log_config_to_jsonable(cfg)
            cfg_hash = hashlib.sha256(
                json.dumps(cfg_blob, sort_keys=True, default=str).encode(),
            ).hexdigest()[:16]
            manifest.write_text(
                json.dumps(
                    {
                        "audit": build_audit_block(
                            tool="log-to-md",
                            records=len(all_records),
                            config_hash=cfg_hash,
                        ),
                        "retention": retention_metadata(),
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
    except OSError as e:
        raise WriterError(str(e)) from e

    ctx.records = all_records
    meta = _build_metadata(cfg, metrics, len(all_records), exec_ctx)
    write_run_metadata(out / "run_metadata.json", meta)
    return ctx


def _build_metadata(
    cfg: LogRunConfig,
    metrics: RunMetrics,
    n_records: int,
    exec_ctx: ExecutionContext | None = None,
) -> dict[str, Any]:
    try:
        from importlib.metadata import version

        ver = version("mdengine")
    except Exception:
        ver = "unknown"
    cfg_blob = log_config_to_jsonable(cfg)
    cfg_hash = hashlib.sha256(
        json.dumps(cfg_blob, sort_keys=True, default=str).encode(),
    ).hexdigest()[:16]

    base = {
        "tool": "log-to-md",
        "mdengine_version": ver,
        "config_hash": cfg_hash,
        "files_parsed": metrics.files_parsed,
        "lines_total": metrics.lines_total,
        "records_total": n_records,
        "malformed_lines": metrics.malformed_lines,
        "skipped_lines": metrics.skipped_lines,
        "parse_duration_ms": metrics.parse_duration_ms,
        "lines_per_sec": round(metrics.lines_per_sec, 2),
    }
    if exec_ctx is not None:
        return merge_runtime_metrics(base, exec_ctx)
    return base
