from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

@dataclass
class ScanConfig:
    """Input and output options for a codeflow scan."""

    project_root: Path
    output_path: Path
    paths_override: list[Path] | None = None
    formats: tuple[str, ...] = ("md", "mermaid", "json")
    depth: int = 5
    languages: str = "mixed"  # mixed|python|java|javascript|typescript|tsx|cpp|go|php|comma list
    entry: list[str] | None = None
    include: str | None = None  # api,event,main,...
    exclude: str | None = None
    include_internal: bool = True
    async_mode: bool = True
    jobs: bool = False
    runtime: bool = False
    business_rules: bool = True
    business_rules_sql: bool = False
    business_rules_combined: bool = True
    # Entry resolution: ``none`` = no heuristic roots when nothing detected; ``roots`` = in-degree 0 symbols; ``first_n`` = lexicographic first nodes (legacy-ish).
    entry_fallback: Literal["none", "roots", "first_n"] = "roots"
    entry_fallback_max: int = 20
    emit_entry_per_method: bool = False
    emit_entry_max: int | None = None
    emit_entry_filter: str | None = None
    entries_file: Path | None = None
    write_scan_summary: bool = True
    # Extra Liferay portlet superclass simple names (merged with defaults + optional codeflow.yaml).
    liferay_portlet_base_classes: tuple[str, ...] = ()
    # Explicit codeflow.yaml path; if None, ``<project_root>/codeflow.yaml`` is used when present.
    codeflow_config_path: Path | None = None
    emit_flow_tree_json: bool = False
    verbose: bool = False
    # Emit graph-schema.json (stable Node/Edge view) when ``json`` is in formats.
    emit_graph_schema: bool = False
    # Cap for Called by / Impact / Dependencies lists in Markdown.
    intelligence_list_cap: int = 80
    # Emit IR-based CFG sidecars (cfg.json, cfg.mmd) and append CFG section to flow.md when md is on.
    emit_cfg: bool = False
    cfg_max_nodes: int = 500
    cfg_inline_calls: bool = False
    cfg_call_depth: int = 3
    cfg_max_paths: int = 100
    cfg_path_max_depth: int = 1000
    cfg_loop_visits: int = 2
    # CFG path scoring (static defaults; optional runtime trace).
    cfg_probability: bool = False
    cfg_mermaid_probabilities: bool = False
    cfg_runtime_trace: Path | None = None
    cfg_loop_repeat_prob: float = 0.6
    # Merge parser structural edges (IMPORTS / INHERITS / …) into the graph (Java first).
    graph_include_structural: bool = False
    # Emit REFERENCES edges from parsers (Python/Java/TS heuristics).
    include_references: bool = False
    # Emit EVENT edges (e.g. Kafka topic → consumer).
    include_events: bool = False
    # Clustering mode for graph-communities.json and optional Markdown cluster line.
    cluster_mode: Literal["file_imports", "structural", "semantic", "hybrid"] = "file_imports"
    # Optional Cypher-like query; results written to query-results.json when json in formats.
    graph_query: str | None = None
    # When true, "Called By" lists transitive callers (ancestors in call graph) instead of direct only.
    intelligence_transitive_callers: bool = False
    # Append graph inventory (node/edge counts, relation mix) to system_overview.md.
    emit_system_graph_stats: bool = False
    # Optional SQLite graph.db (nodes/edges tables) for large-repo queries.
    emit_graph_sqlite: bool = False
    # ``full`` replaces ``graph.db``; ``incremental`` upserts nodes/edges and records scan rows.
    graph_sqlite_mode: Literal["full", "incremental"] = "full"
    # When ``incremental``, drop nodes/edges not seen in this scan (default off = accumulate).
    graph_sqlite_prune_missing: bool = False
    # When json is in formats, write graph-communities.json (greedy modularity on file imports).
    emit_graph_communities: bool = False
    # Deterministic rule-based community labels in JSON / Markdown / unified HTML (no LLM).
    emit_cluster_labels: bool = True
    # Write entry.llm.md beside entry.md (LLM-oriented pointers, no duplicate full text).
    emit_llm_entry_sidecar: bool = False
    # When ``emit_cfg`` is on, build IR for these languages (skip heavy repos by turning one off).
    cfg_ir_go: bool = True
    cfg_ir_php: bool = True
    cfg_ir_cpp: bool = True
    # Include EVENT (and optionally REFERENCES) edges in flow slice / flow.mmd (not only CALLS).
    flow_include_event_edges: bool = False
    flow_include_reference_edges: bool = False
    # Markdown: add Event impact section (CALLS ∪ EVENT reachability).
    event_impact: bool = False
    # Optional semantic layer (local SentenceTransformers; install mdengine[codeflow-semantic]).
    enable_embeddings: bool = False
    embedding_model: str = "all-MiniLM-L6-v2"
    embedding_max_nodes: int = 5000
    embedding_k_clusters: int = 8
    semantic_top_k: int = 10
    semantic_search: str | None = None
    emit_html_unified: bool = False
    # Natural-language query (rule-based); writes nl-query-results.json at scan root.
    nl_query: str | None = None
    # Hot paths + runtime-frequency CFG anomalies (+ optional semantic outliers); needs emit_cfg + cfg_runtime_trace JSON.
    emit_runtime_insights: bool = False
    runtime_insight_frequency_threshold: float = 0.05
    runtime_insight_hot_paths_top: int = 5
    semantic_outlier_distance_threshold: float = 0.7
    # Additional repository roots merged into one graph (``project_root`` is first; labels from dir names).
    multi_repo_roots: tuple[Path, ...] = ()
    # When set on a git ``project_root``, write ``pr-impact.json`` after the graph is built.
    diff_base: str | None = None
    diff_head: str | None = None
    # Optional package prefix → target repo label for cross-repo IMPORT resolution after multi-repo merge.
    cross_repo_package_hints: dict[str, str] | None = None
    # When true (with hints + structural deps), resolve ``external::…`` IMPORTS to other repos.
    resolve_cross_repo: bool = False
    # Load ``tsconfig.json`` / ``jsconfig.json`` ``paths`` per merged repo for ``@…`` cross-repo candidates.
    cross_repo_tsconfig: bool = False
    # Add ``pom.xml`` ``groupId`` → repo label hints (does not override ``cross_repo_package_hints`` keys).
    cross_repo_maven_hints: bool = False
    # Unified cache: TTL for git clone refresh skip; ``cache_clear_mode`` runs once at scan start.
    cache_enabled: bool = True
    cache_ttl_seconds: int = 0
    cache_clear_mode: str | None = None  # all | git | semantic | unified
    # UX alias: treat like ``graph_include_structural`` for dependency/import edges.
    enable_dependency_graph: bool = False
    # Parser preference: ``auto`` per language; ``treesitter`` / ``external`` where wired (see unified_parser).
    parser_mode: Literal["auto", "treesitter", "external"] = "auto"
    # When true, include ``REL_CONTAINS`` in dependency reachability (default: exclude).
    graph_include_contains_reachability: bool = False
    # Cap embedded per-method CFG Mermaid payloads in ``index.unified.html``.
    ui_cfg_max_methods: int = 25

    def structural_graph_enabled(self) -> bool:
        return bool(self.graph_include_structural or self.enable_dependency_graph)

    def parsed_include(self) -> set[str] | None:
        if not self.include or not str(self.include).strip():
            return None
        return {x.strip() for x in str(self.include).split(",") if x.strip()}

    def flow_slice_relations(self) -> frozenset[str]:
        from md_generator.codeflow.graph import relations as rel

        r = {rel.REL_CALLS}
        if self.flow_include_event_edges:
            r.add(rel.REL_EVENT)
        if self.flow_include_reference_edges:
            r.add(rel.REL_REFERENCES)
        return frozenset(r)
