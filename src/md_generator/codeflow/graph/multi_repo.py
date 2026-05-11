"""Merge codeflow graphs from multiple repository roots with stable id namespacing."""

from __future__ import annotations

import re
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import networkx as nx

from md_generator.codeflow.graph.multigraph_utils import CodeflowGraph, edge_payload, iter_multi_edges
from md_generator.codeflow.models.ir import (
    BranchPoint,
    BusinessRule,
    CallSite,
    EntryRecord,
    FileParseResult,
    StructuralEdge,
)
from md_generator.codeflow.models.ir_cfg import IRMethod


def repo_label(root: Path, index: int, used: set[str] | None = None) -> str:
    """Short filesystem-safe label (unique within ``used``)."""
    raw = re.sub(r"[^a-zA-Z0-9_.-]+", "_", root.name.strip())[:48] or f"r{index}"
    lab = raw
    if used is not None:
        base = lab
        n = 0
        while lab in used:
            n += 1
            lab = f"{base}_{n}"
        used.add(lab)
    return lab


def prefixed_id(label: str, node_id: str) -> str:
    if node_id.startswith(f"{label}::"):
        return node_id
    return f"{label}::{node_id}"


def merge_graphs(graphs: Sequence[CodeflowGraph], labels: Sequence[str]) -> CodeflowGraph:
    """Union disjoint graphs with node/edge ids rewritten to ``label::original_id``."""
    if len(graphs) != len(labels):
        raise ValueError("graphs and labels length mismatch")
    out: CodeflowGraph = nx.MultiDiGraph()
    for g, lab in zip(graphs, labels):
        for n in g.nodes:
            nn = prefixed_id(lab, str(n))
            d = dict(g.nodes[n])
            d["repo"] = lab
            out.add_node(nn, **d)
        for u, v, k, ed in iter_multi_edges(g):
            u2, v2 = prefixed_id(lab, str(u)), prefixed_id(lab, str(v))
            out.add_edge(u2, v2, key=k, **edge_payload(**dict(ed)))
    return out


def _pref_sym(label: str, sid: str | None) -> str | None:
    if sid is None:
        return None
    return prefixed_id(label, sid)


def prefix_parse_results(results: list[FileParseResult], label: str) -> None:
    """Rewrite symbol ids in parse results to match ``merge_graphs`` namespacing."""
    for fr in results:
        fr.symbol_ids = [prefixed_id(label, s) for s in fr.symbol_ids]
        new_calls: list[CallSite] = []
        for c in fr.calls:
            new_calls.append(
                CallSite(
                    caller_id=prefixed_id(label, c.caller_id),
                    callee_hint=c.callee_hint,
                    resolution=c.resolution,
                    is_async=c.is_async,
                    line=c.line,
                    condition_label=c.condition_label,
                ),
            )
        fr.calls = new_calls
        new_br: list[BranchPoint] = []
        for b in fr.branches:
            new_br.append(
                BranchPoint(
                    caller_id=prefixed_id(label, b.caller_id),
                    kind=b.kind,
                    label=b.label,
                    line=b.line,
                ),
            )
        fr.branches = new_br
        new_entries: list[EntryRecord] = []
        for e in fr.entries:
            new_entries.append(
                EntryRecord(
                    symbol_id=prefixed_id(label, e.symbol_id),
                    kind=e.kind,
                    label=e.label,
                    file_path=e.file_path,
                    line=e.line,
                ),
            )
        fr.entries = new_entries
        new_rules: list[BusinessRule] = []
        for r in fr.rules:
            new_rules.append(
                BusinessRule(
                    source=r.source,
                    symbol_id=_pref_sym(label, r.symbol_id),
                    file_path=r.file_path,
                    line=r.line,
                    title=r.title,
                    detail=r.detail,
                    confidence=r.confidence,
                ),
            )
        fr.rules = new_rules
        new_struct: list[StructuralEdge] = []
        for se in fr.structural_edges:
            new_struct.append(
                StructuralEdge(
                    source_id=prefixed_id(label, se.source_id),
                    target_id=prefixed_id(label, se.target_id),
                    relation=se.relation,
                    confidence=se.confidence,
                    line=se.line,
                ),
            )
        fr.structural_edges = new_struct
        new_ir: list[object] = []
        for im in fr.ir_methods:
            if isinstance(im, IRMethod):
                new_ir.append(
                    IRMethod(
                        symbol_id=prefixed_id(label, im.symbol_id),
                        name=im.name,
                        file_path=im.file_path,
                        language=im.language,
                        body=im.body,
                    ),
                )
            else:
                new_ir.append(im)
        fr.ir_methods = new_ir


def link_cross_repo_imports(
    g: CodeflowGraph,
    *,
    package_hints: dict[str, str] | None = None,
) -> int:
    """Deprecated no-op: use ``resolve_cross_repo`` + :func:`cross_repo_resolver.resolve_cross_repo_imports` in the scan."""
    del g, package_hints
    return 0
