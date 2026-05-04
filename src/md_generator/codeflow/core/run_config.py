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
    # Merge parser structural edges (IMPORTS / INHERITS / …) into the DiGraph (Java first).
    graph_include_structural: bool = False
    # When true, "Called By" lists transitive callers (ancestors in call graph) instead of direct only.
    intelligence_transitive_callers: bool = False
    # Append graph inventory (node/edge counts, relation mix) to system_overview.md.
    emit_system_graph_stats: bool = False
    # Optional SQLite graph.db (nodes/edges tables) for large-repo queries.
    emit_graph_sqlite: bool = False
    # When json is in formats, write graph-communities.json (greedy modularity on file imports).
    emit_graph_communities: bool = False
    # Write entry.llm.md beside entry.md (LLM-oriented pointers, no duplicate full text).
    emit_llm_entry_sidecar: bool = False

    def parsed_include(self) -> set[str] | None:
        if not self.include or not str(self.include).strip():
            return None
        return {x.strip() for x in str(self.include).split(",") if x.strip()}
