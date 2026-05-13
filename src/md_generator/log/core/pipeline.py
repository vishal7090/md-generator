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
from md_generator.log.core.plugins import load_enrichers, run_enricher_plugins
from md_generator.log.enrichment.fingerprinting import add_fingerprint
from md_generator.log.enrichment.pattern_matcher import tag_patterns
from md_generator.log.enrichment.severity_ranker import add_severity_rank
from md_generator.log.ingestion.archive_loader import iter_zip_log_members, sniff_zip
from md_generator.log.ingestion.encoding_detector import decode_lines
from md_generator.log.ingestion.file_loader import expand_log_paths
from md_generator.log.ingestion.stream_reader import iter_text_lines, read_file_as_text
from md_generator.log.normalization.token_normalizer import normalize_record
from md_generator.log.parser.models import LogRecord, RunContext
from md_generator.log.parser.multiline_parser import parse_file_lines
from md_generator.log.parser.parser_registry import select_line_regex_for_sample
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
        rx = select_line_regex_for_sample(text[:8192])
        if rx:
            eff_cfg = replace(cfg, parser=replace(cfg.parser, line_regex=rx))
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


def _parse_disk_file(path: Path, cfg: LogRunConfig) -> tuple[list[LogRecord], int, int, int, int]:
    max_lines = _effective_max_lines(cfg)
    text, _n = read_file_as_text(path, cfg.execution.encoding_fallbacks, max_lines)
    eff_cfg = cfg
    if cfg.parser.auto_detect:
        rx = select_line_regex_for_sample(text[:8192])
        if rx:
            eff_cfg = replace(cfg, parser=replace(cfg.parser, line_regex=rx))
    lines = list(iter_text_lines(text, max_lines=max_lines))
    pr = parse_file_lines(path, eff_cfg, lines)
    recs = _post_parse_records(pr.records, eff_cfg, path)
    return recs, pr.total_lines, pr.malformed_lines, pr.skipped_lines, pr.parse_duration_ms


def run_pipeline(ctx: RunContext) -> RunContext:
    cfg = ctx.config
    paths = expand_log_paths(cfg.resolved_input_paths())
    if not paths:
        raise ValueError("No input files: set input.paths in config or CLI --input")

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
    except OSError as e:
        raise WriterError(str(e)) from e

    ctx.records = all_records
    meta = _build_metadata(cfg, metrics, len(all_records))
    write_run_metadata(out / "run_metadata.json", meta)
    return ctx


def _build_metadata(cfg: LogRunConfig, metrics: RunMetrics, n_records: int) -> dict[str, Any]:
    try:
        from importlib.metadata import version

        ver = version("mdengine")
    except Exception:
        ver = "unknown"
    cfg_blob = log_config_to_jsonable(cfg)
    cfg_hash = hashlib.sha256(
        json.dumps(cfg_blob, sort_keys=True, default=str).encode(),
    ).hexdigest()[:16]

    return {
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
