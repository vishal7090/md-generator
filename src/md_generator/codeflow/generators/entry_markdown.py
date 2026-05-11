"""Structured per-entry Markdown (Execution Flow Documentation)."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any

import networkx as nx

from md_generator.codeflow.analyzers.flow_analyzer import FlowSlice
from md_generator.codeflow.graph.analysis import event_flow_edges, event_impact, references_from
from md_generator.codeflow.graph.multigraph_utils import CodeflowGraph, iter_multi_edges, iter_out_edges
from md_generator.codeflow.generators.flow_summary import format_flow_description, format_method_summary_lines
from md_generator.codeflow.graph import relations as graph_rel
from md_generator.codeflow.graph.dependency_builder import class_structural_successors, file_import_successors
from md_generator.codeflow.graph.enricher import (
    called_by_direct,
    called_by_transitive,
    impact_descendants,
    structural_dependency_bullets,
)
from md_generator.codeflow.models.ir import BusinessRule, EntryKind, EntryRecord


def _md_escape(s: str) -> str:
    return s.replace("|", "\\|")


def _file_node_for_entry(g: CodeflowGraph, entry_id: str) -> str | None:
    if entry_id not in g:
        return None
    d = g.nodes[entry_id]
    fp = str(d.get("file_path") or "").replace("\\", "/")
    if not fp:
        return None
    repo = d.get("repo")
    if isinstance(repo, str) and repo.strip():
        nid = f"{repo.strip()}::file:{fp}"
        if nid in g:
            return nid
    fid = f"file:{fp}"
    return fid if fid in g else None


def _cross_repo_import_bullets(g: CodeflowGraph, entry_id: str, cap: int) -> list[str]:
    fid = _file_node_for_entry(g, entry_id)
    if not fid or fid not in g:
        return []
    out: list[str] = []
    for _u, v, _k, d in iter_out_edges(g, fid):
        if d.get("relation") != graph_rel.REL_CROSS_REPO_IMPORT:
            continue
        out.append(f"- `{_md_escape(str(v))}`")
        if len(out) >= cap:
            break
    return out


def _class_vertex_for_method(entry_id: str, g: CodeflowGraph) -> str | None:
    if entry_id not in g:
        return None
    fp = str(g.nodes[entry_id].get("file_path") or "").replace("\\", "/")
    if not fp or "::" not in entry_id:
        return None
    tail = entry_id.split("::", 1)[-1]
    if "." not in tail:
        return None
    cls, _m = tail.rsplit(".", 1)
    cid = f"class:{fp}::{cls}"
    return cid if cid in g else None


def _event_chain_lines(g: CodeflowGraph, entry_id: str, cap: int) -> list[str]:
    """Producer → topic → consumer bullets involving ``entry_id``."""
    producers: dict[str, list[str]] = {}
    consumers: dict[str, list[str]] = {}
    for u, v, _k, d in iter_multi_edges(g):
        if d.get("relation") != graph_rel.REL_EVENT:
            continue
        role = d.get("event_role")
        su, sv = str(u), str(v)
        if role == "consumer" and su.startswith("topic:"):
            consumers.setdefault(su, []).append(sv)
        elif role == "producer" and sv.startswith("topic:"):
            producers.setdefault(sv, []).append(su)
    out: list[str] = []
    for topic in sorted(set(producers) | set(consumers)):
        ps = sorted(set(producers.get(topic, [])))
        cs = sorted(set(consumers.get(topic, [])))
        if entry_id not in ps and entry_id not in cs:
            continue
        if ps and cs:
            for p in ps:
                for c in cs:
                    out.append(f"- `{_md_escape(p)}` → `{_md_escape(topic)}` → `{_md_escape(c)}`")
                    if len(out) >= cap:
                        return out
        elif entry_id in ps:
            out.append(f"- `{_md_escape(entry_id)}` → `{_md_escape(topic)}` *(producer)*")
        elif entry_id in cs:
            out.append(f"- `{_md_escape(topic)}` → `{_md_escape(entry_id)}` *(consumer)*")
        if len(out) >= cap:
            break
    return out[:cap]


def type_label_for_kind(kind: str | None) -> str:
    if not kind:
        return "Other"
    mapping = {
        EntryKind.API_REST.value: "API",
        EntryKind.PORTLET.value: "Portlet",
        EntryKind.KAFKA.value: "Event",
        EntryKind.QUEUE.value: "Event",
        EntryKind.SCHEDULER.value: "Scheduler",
        EntryKind.MAIN.value: "Main",
        EntryKind.CLI.value: "CLI",
        EntryKind.UNKNOWN.value: "Other",
    }
    return mapping.get(kind, "Other")


def _subtitle(entry_id: str, entry_record: EntryRecord | None, g: CodeflowGraph) -> str | None:
    if entry_record and entry_record.label.strip():
        lab = entry_record.label.strip()
        up = lab.upper()
        if any(m in up for m in ("GET ", "POST ", "PUT ", "DELETE ", "PATCH ")) or "`/" in lab or "/" in lab:
            return lab
    if entry_id in g:
        el = g.nodes[entry_id].get("entry_label")
        if el and str(el).strip():
            s = str(el).strip()
            if "/" in s or any(m in s.upper() for m in ("GET ", "POST ", "PUT ")):
                return s
    tail = entry_id.split("::", 1)[-1] if "::" in entry_id else entry_id
    return tail.replace("_", " ") if tail else None


def pretty_start_method(g: CodeflowGraph, entry_id: str) -> str:
    if entry_id not in g:
        tail = entry_id.split("::")[-1] if "::" in entry_id else entry_id
        if "." in tail:
            c, m = tail.rsplit(".", 1)
            return f"{c}.{m}()"
        return f"{tail}()"
    d = g.nodes[entry_id]
    cn = d.get("class_name")
    mn = d.get("method_name")
    if mn and cn:
        return f"{cn}.{mn}()"
    if mn:
        return f"{mn}()"
    tail = entry_id.split("::")[-1]
    return tail if tail.endswith(")") else f"{tail}()"


def _async_event_lines(sl: FlowSlice, g: CodeflowGraph) -> list[str]:
    lines: list[str] = []
    for _u, v, ed in sl.edges:
        if ed.get("async_") or ed.get("type") == "async":
            lines.append(f"- Async call to `{v}`")
        if v in g:
            ek = g.nodes[v].get("entry_kind")
            if ek in (EntryKind.KAFKA.value, EntryKind.QUEUE.value):
                lab = g.nodes[v].get("entry_label") or v
                lines.append(f"- Event-style target (`{ek}`): {lab}")
    return lines


def _collect_entry_tags(entry_id: str, g: CodeflowGraph) -> list[str]:
    if entry_id not in g:
        return []
    d = g.nodes[entry_id]
    tags = {str(x) for x in (d.get("tags") or []) if x}
    for ek in ("entry_kind", "type"):
        v = d.get(ek)
        if v:
            tags.add(str(v))
    for _, _succ, _k, ed in iter_out_edges(g, entry_id):
        if ed.get("async_") or ed.get("type") == "async":
            tags.add("async_outbound")
            break
    return sorted(tags)


def _graph_inventory_lines(graph: CodeflowGraph, top_n: int = 10) -> list[str]:
    from md_generator.codeflow.graph.enricher import call_graph_view

    rel_counts: dict[str, int] = {}
    for _, _, _k, ed in iter_multi_edges(graph):
        k = str(ed.get("relation") or graph_rel.REL_CALLS)
        rel_counts[k] = rel_counts.get(k, 0) + 1
    lines = [
        "## Graph inventory",
        "",
        f"- **Nodes:** {graph.number_of_nodes()}",
        f"- **Edges:** {graph.number_of_edges()}",
        "",
        "**Edges by relation**",
        "",
    ]
    for k in sorted(rel_counts.keys()):
        lines.append(f"- `{k}`: {rel_counts[k]}")
    lines += ["", f"**Top call-graph out-degree (first {top_n})**", ""]
    cg = call_graph_view(graph)
    ranked = sorted(((n, cg.out_degree(n)) for n in cg.nodes()), key=lambda t: -t[1])[:top_n]
    for n, deg in ranked:
        lines.append(f"- `{n}` → {deg}")
    lines.append("")
    return lines


def _system_graph_insights_lines(
    graph: CodeflowGraph,
    *,
    top_n: int = 10,
    community_preview: int = 8,
    include_contains: bool = False,
) -> list[str]:
    """Top modules, file import layer, high-impact symbols, modularity communities."""
    from md_generator.codeflow.graph.analysis import dependency_reachability_subgraph
    from md_generator.codeflow.graph.clustering import greedy_modularity_file_communities

    lines = [
        "## System graph view",
        "",
        "### Top modules (by method/entry count)",
        "",
    ]
    mod_counts: dict[str, int] = {}
    for _n, d in graph.nodes(data=True):
        fp = (d.get("file_path") or "").strip()
        if not fp:
            continue
        if d.get("type") not in ("method", "entry"):
            continue
        top = fp.split("/")[0] if "/" in fp else fp
        mod_counts[top] = mod_counts.get(top, 0) + 1
    ranked_mod = sorted(mod_counts.items(), key=lambda x: -x[1])[:top_n]
    if ranked_mod:
        for m, c in ranked_mod:
            lines.append(f"- `{m}`: {c} symbols")
    else:
        lines.append("- *No file paths on method/entry nodes.*")
    lines += ["", "### File dependency graph", ""]
    file_nodes = [n for n in graph.nodes() if isinstance(n, str) and str(n).startswith("file:")]
    ff_imp = 0
    for u, v, _k, d in iter_multi_edges(graph):
        if d.get("relation") != graph_rel.REL_IMPORTS:
            continue
        if (
            isinstance(u, str)
            and u.startswith("file:")
            and isinstance(v, str)
            and v.startswith("file:")
        ):
            ff_imp += 1
    lines.append(f"- **File nodes:** {len(file_nodes)}")
    lines.append(f"- **File → file IMPORTS:** {ff_imp}")
    lines.append("")

    lines += [
        "### Most impacted nodes (approx.)",
        "",
        "Largest downstream reach in the **dependency reachability** graph ("
        f"{'CONTAINS included' if include_contains else 'CONTAINS excluded'}"
        "); candidate set capped for performance.",
        "",
    ]
    dg = dependency_reachability_subgraph(graph, include_contains=include_contains)
    candidates: list[str] = []
    for n, d in graph.nodes(data=True):
        if not isinstance(n, str) or "::" not in n or n.startswith("unknown::"):
            continue
        if d.get("type") not in ("method", "entry"):
            continue
        if n in dg:
            candidates.append(n)
    if len(candidates) > 300:
        candidates = sorted(candidates, key=lambda x: dg.out_degree(x), reverse=True)[:300]
    scored: list[tuple[str, int]] = []
    for nid in candidates:
        scored.append((nid, len(nx.descendants(dg, nid))))
    scored.sort(key=lambda t: -t[1])
    if scored:
        for sym, cnt in scored[:top_n]:
            lines.append(f"- `{sym}` → {cnt} downstream nodes")
    else:
        lines.append("- *No scored symbols.*")
    lines.append("")

    lines += ["### Dependency graph (structural communities)", ""]
    comms = greedy_modularity_file_communities(graph)
    if comms:
        comms.sort(key=lambda c: -len(c))
        for i, c in enumerate(comms[:community_preview], start=1):
            sample = ", ".join(f"`{x}`" for x in c[:3])
            extra = f" (+{len(c) - 3} more)" if len(c) > 3 else ""
            lines.append(f"- Community {i} ({len(c)} files): {sample}{extra}")
        if len(comms) > community_preview:
            lines.append(f"- *…and {len(comms) - community_preview} more communities.*")
    else:
        lines.append("- *No file-level import graph (try Java with `--graph-include-structural`).*")
    lines.append("")
    return lines


def _decision_bullets(sl: FlowSlice) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for u, v, ed in sl.edges:
        cond = ed.get("condition") or ""
        labs = ed.get("labels") or []
        lab = (labs[-1] if labs else None) or cond
        if not lab:
            continue
        key = (u, v, str(lab))
        if key in seen:
            continue
        seen.add(key)
        out.append(f"- `{u}` → `{v}` — *{lab}*")
    return out


def write_entry_markdown(
    path: Path,
    entry_id: str,
    sl: FlowSlice,
    g: CodeflowGraph,
    entry_record: EntryRecord | None,
    rules: Sequence[BusinessRule] | None = None,
    *,
    intelligence_cap: int = 80,
    graph_include_structural: bool = False,
    intelligence_transitive_callers: bool = False,
    intelligence_include_contains: bool = False,
    include_references: bool = False,
    include_events: bool = False,
    event_impact_section: bool = False,
    cluster_by_file: dict[str, int] | None = None,
    cluster_label_by_file: dict[str, str] | None = None,
    enable_embeddings: bool = False,
    semantic_neighbors: list[dict[str, Any]] | None = None,
    nl_query_href: str | None = None,
    runtime_insights: dict[str, Any] | None = None,
    pr_impact_slice: dict[str, Any] | None = None,
) -> None:
    lines: list[str] = []
    lines.append("# Execution Flow Documentation")
    lines.append("")
    sub = _subtitle(entry_id, entry_record, g)
    if sub:
        lines.append(f"*{sub}*")
        lines.append("")
    lines.append("## Entry Point")
    lines.append("")
    lines.append(f"- {pretty_start_method(g, entry_id)}")
    lines.append("")
    if entry_record is not None:
        kind = entry_record.kind.value
    elif entry_id in g:
        kind = g.nodes[entry_id].get("entry_kind")
    else:
        kind = None
    lines.append("## Type")
    lines.append("")
    lines.append(type_label_for_kind(kind))
    lines.append("")
    if pr_impact_slice:
        lines.append("## PR impact (git diff)")
        lines.append("")
        lines.append(
            f"- **Base → head:** `{pr_impact_slice.get('base')}` → `{pr_impact_slice.get('head')}`",
        )
        lines.append(f"- **Changed files (scan):** {pr_impact_slice.get('changed_files_count', 0)}")
        lines.append(
            f"- **Impacted nodes (scan, reachability):** {pr_impact_slice.get('impacted_nodes_count', 0)}",
        )
        lines.append(f"- **Seeds in this flow slice:** {pr_impact_slice.get('seeds_in_slice_count', 0)}")
        ss = pr_impact_slice.get("seed_sample") or []
        if ss:
            lines.append("- **Sample seeds in slice:**")
            for s in ss:
                lines.append(f"  - `{_md_escape(str(s))}`")
        lines.append(
            f"- **Impacted nodes in this slice:** {pr_impact_slice.get('impacted_in_slice_count', 0)}",
        )
        href = pr_impact_slice.get("pr_impact_json_href")
        if isinstance(href, str) and href.strip():
            lines.append(f"- **Full payload:** [{href.strip()}]({href.strip()})")
        lines.append("")
    lines.append("## Flow Description")
    lines.append("")
    lines.extend(format_flow_description(sl, g))
    lines.append("")
    lines.append("## Method Summary")
    lines.append("")
    lines.extend(format_method_summary_lines(sl, g, entry_id))
    lines.append("")

    if intelligence_transitive_callers:
        cb = called_by_transitive(
            g,
            entry_id,
            intelligence_cap,
            include_contains=intelligence_include_contains,
        )
        cb_blurb = (
            "*Transitive upstream (`nx.ancestors` on dependency reachability: CALLS + structural edges; "
            f"{'CONTAINS included' if intelligence_include_contains else 'CONTAINS excluded'}; capped).*"
        )
    else:
        cb = called_by_direct(
            g,
            entry_id,
            intelligence_cap,
            include_contains=intelligence_include_contains,
        )
        cb_blurb = (
            "*Direct predecessors in dependency reachability (calls + structural relations when enabled; "
            f"{'CONTAINS included' if intelligence_include_contains else 'CONTAINS excluded'}; capped).*"
        )
    im = impact_descendants(
        g,
        entry_id,
        intelligence_cap,
        include_contains=intelligence_include_contains,
    )
    lines.append("## Called By")
    lines.append("")
    lines.append(cb_blurb)
    lines.append("")
    if cb:
        for x in cb:
            lines.append(f"- `{x}`")
        if len(cb) >= intelligence_cap:
            lines.append(f"- *…truncated at {intelligence_cap} items.*")
    else:
        lines.append("*None in dependency reachability graph or entry not found.*")
    lines.append("")
    lines.append("## Impact")
    lines.append("")
    lines.append(
        "*Transitive downstream (`nx.descendants` on dependency reachability; "
        f"{'CONTAINS included' if intelligence_include_contains else 'CONTAINS excluded'}; capped).*",
    )
    lines.append("")
    if im:
        for x in im:
            lines.append(f"- `{x}`")
        if len(im) >= intelligence_cap:
            lines.append(f"- *…truncated at {intelligence_cap} items.*")
    else:
        lines.append("*None or empty downstream.*")
    lines.append("")

    lines.append("## Dependencies")
    lines.append("")
    if graph_include_structural:
        dep = structural_dependency_bullets(g, entry_id, intelligence_cap)
        any_dep = bool(dep)
        if dep:
            lines.extend(dep)
            if len(dep) >= intelligence_cap:
                lines.append(f"- *…truncated at {intelligence_cap} items.*")
        if entry_id in g:
            fp = str(g.nodes[entry_id].get("file_path") or "").replace("\\", "/")
            if fp:
                fid = f"file:{fp}"
                if fid in g:
                    imps = file_import_successors(g, fid, cap=intelligence_cap)
                    if imps:
                        any_dep = True
                        lines.append("")
                        lines.append("**Imports (file scope)**")
                        for t in imps[:intelligence_cap]:
                            lines.append(f"- `{_md_escape(str(t))}`")
        cvert = _class_vertex_for_method(entry_id, g)
        if cvert:
            inh = class_structural_successors(
                g,
                cvert,
                frozenset({graph_rel.REL_INHERITS, graph_rel.REL_IMPLEMENTS}),
                cap=intelligence_cap,
            )
            if inh:
                any_dep = True
                lines.append("")
                lines.append("**Class inheritance / implements**")
                for reln, tgt in inh:
                    lines.append(f"- `{reln}` → `{_md_escape(str(tgt))}`")
        if not any_dep:
            lines.append(
                "*No structural edges for this symbol's file/class, or class context missing. "
                "Use `--graph-include-structural` or `--enable-dependency-graph` (imports for Java/Python/TS when parsed).*",
            )
    else:
        lines.append(
            "Enable **`--graph-include-structural`** or **`--enable-dependency-graph`** to list imports and inheritance. "
            "Structural view is also summarized in `graph-schema.json` when `--emit-graph-schema` is used with `json`.",
        )
    lines.append("")

    crb = _cross_repo_import_bullets(g, entry_id, intelligence_cap)
    if crb:
        lines.append("## Cross-repo imports")
        lines.append("")
        lines.append("*Outgoing `CROSS_REPO_IMPORT` edges from this entry's file (package-hint resolution; capped).*")
        lines.append("")
        lines.extend(crb)
        if len(crb) >= intelligence_cap:
            lines.append(f"- *…truncated at {intelligence_cap} items.*")
        lines.append("")

    ref_list = references_from(g, entry_id)
    if include_references or ref_list:
        lines.append("## References")
        lines.append("")
        if ref_list:
            for tgt in ref_list[:intelligence_cap]:
                lines.append(f"- `{_md_escape(str(tgt))}`")
            if len(ref_list) >= intelligence_cap:
                lines.append(f"- *…truncated at {intelligence_cap} items.*")
        else:
            lines.append("*No REFERENCES edges for this symbol (enable `--include-references`).*")
        lines.append("")

    if include_events:
        lines.append("## Event flow (graph)")
        lines.append("")
        chains = _event_chain_lines(g, entry_id, intelligence_cap)
        if chains:
            lines.append("*Producer → topic → consumer chains involving this entry:*")
            lines.append("")
            lines.extend(chains)
            lines.append("")
        ev_lines: list[str] = []
        for u, v, _d in event_flow_edges(g):
            su, sv = str(u), str(v)
            if entry_id == su or entry_id == sv:
                ev_lines.append(f"- `{su}` → `{sv}`")
        if ev_lines:
            if chains:
                lines.append("*Raw EVENT edges (this entry):*")
                lines.append("")
            lines.extend(ev_lines[:intelligence_cap])
            if len(ev_lines) >= intelligence_cap:
                lines.append(f"- *…truncated at {intelligence_cap} items.*")
        elif not chains:
            lines.append("*No EVENT edges touching this entry (enable `--include-events` for Kafka).*")
        lines.append("")

    if event_impact_section:
        lines.append("## Event impact")
        lines.append("")
        lines.append("*Transitive downstream over CALLS ∪ EVENT only (capped).*")
        lines.append("")
        ei = event_impact(g, entry_id, intelligence_cap)
        if ei:
            for x in ei:
                lines.append(f"- `{_md_escape(str(x))}`")
            if len(ei) >= intelligence_cap:
                lines.append(f"- *…truncated at {intelligence_cap} items.*")
        else:
            lines.append("*None, or entry not in graph (enable `--include-events` / `--flow-include-event-edges` as needed).*")
        lines.append("")

    if cluster_by_file and entry_id in g:
        fp0 = str((g.nodes[entry_id].get("file_path") or "")).strip().replace("\\", "/")
        cid0 = cluster_by_file.get(fp0) if fp0 else None
        if cid0 is not None:
            lines.append("## Cluster")
            lines.append("")
            lab0 = (
                cluster_label_by_file.get(fp0)
                if cluster_label_by_file and fp0
                else None
            )
            if lab0:
                lines.append(
                    f"- **Cluster label:** `{_md_escape(str(lab0))}` (id {cid0}; rule-based, `cluster_mode` communities)",
                )
            else:
                lines.append(f"- **Community id:** {cid0} (from `cluster_mode` communities)")
            lines.append("")

    if enable_embeddings and entry_id in g:
        sg = g.nodes[entry_id].get("semantic_group")
        if sg is not None:
            lines.append("## Semantic group")
            lines.append("")
            lines.append(f"- **KMeans cluster (embedding):** {int(sg)}")
            lines.append("")
        if semantic_neighbors:
            lines.append("## Similar methods")
            lines.append("")
            lines.append("*Cosine similarity in embedding space (global index; see `semantic-neighbors.json`).*")
            lines.append("")
            for row in semantic_neighbors:
                nid = str(row.get("node_id", ""))
                sc = row.get("score")
                name = row.get("name")
                cn = row.get("class_name")
                lab = f"{cn}.{name}" if cn and name else nid
                if isinstance(sc, int | float):
                    lines.append(f"- `{_md_escape(nid)}` — {float(sc):.4f} — {_md_escape(str(lab))}")
                else:
                    lines.append(f"- `{_md_escape(nid)}` — {_md_escape(str(lab))}")
            lines.append("")

    if nl_query_href:
        lines.append("## NL query (scan)")
        lines.append("")
        lines.append(f"- Full rule-based result: [`nl-query-results.json`]({_md_escape(nl_query_href)})")
        lines.append("")

    if runtime_insights:
        hp = runtime_insights.get("hot_paths") or []
        meta = runtime_insights.get("hot_paths_meta") or {}
        if hp:
            lines.append("## Hot paths (CFG + runtime)")
            lines.append("")
            lines.append("*Scores sum runtime trace counts along enumerated CFG paths (see `runtime-insights.json`).*")
            lines.append("")
            for i, row in enumerate(hp[:12], 1):
                nodes = row.get("nodes") or []
                sc = float(row.get("score") or 0)
                chain = " → ".join(str(x) for x in nodes[:16])
                lines.append(f"{i}. score **{sc:.1f}** — `{_md_escape(chain)}`")
            if meta.get("paths_truncated"):
                lines.append("- *CFG path enumeration truncated.*")
            lines.append("")
        rare = runtime_insights.get("rare_cfg_edges") or []
        if rare:
            lines.append("## Anomalies (rare CFG edges)")
            lines.append("")
            defn = str(runtime_insights.get("definition") or "").strip()
            if defn:
                lines.append(f"*{defn}*")
                lines.append("")
            for row in rare[:30]:
                fr = row.get("frequency")
                frs = f"{float(fr):.4f}" if isinstance(fr, int | float) else str(fr)
                lines.append(
                    f"- `{_md_escape(str(row.get('source')))}`→`{_md_escape(str(row.get('target')))}` — freq {frs}",
                )
            lines.append("")
        outs = runtime_insights.get("semantic_outliers") or []
        local_o = [x for x in outs if x.get("node_id") in sl.nodes]
        if local_o:
            lines.append("## Semantic outliers (in slice)")
            lines.append("")
            for x in local_o[:24]:
                lines.append(
                    f"- `{_md_escape(str(x.get('node_id')))}` — distance {float(x.get('distance', 0)):.3f}",
                )
            lines.append("")
        lines.append("- Data: [`runtime-insights.json`](runtime-insights.json)")
        lines.append("")

    if entry_id in g:
        d = g.nodes[entry_id]
        lines.append("## Metadata")
        lines.append("")
        lines.append(f"- **File:** `{_md_escape(str(d.get('file_path', '')))}`")
        lines.append(f"- **Class:** `{_md_escape(str(d.get('class_name', '')))}`")
        lines.append(f"- **Language:** `{_md_escape(str(d.get('language', '')))}`")
        tag_list = _collect_entry_tags(entry_id, g)
        if tag_list:
            lines.append(f"- **Tags:** {', '.join(_md_escape(t) for t in tag_list)}")
        lines.append("")

    async_lines = _async_event_lines(sl, g)
    lines.append("## Async / Event Flow")
    lines.append("")
    if async_lines:
        lines.extend(async_lines)
    else:
        lines.append("*None detected in this slice.*")
    lines.append("")

    dec = _decision_bullets(sl)
    if dec:
        lines.append("## Decision Points")
        lines.append("")
        lines.extend(dec)
        lines.append("")

    if rules is not None:
        lines.append("## Business rules")
        lines.append("")
        if rules:
            for r in list(rules)[:4]:
                d = " ".join(r.detail.splitlines())[:140]
                lines.append(f"- **{_md_escape(r.title)}** (`{r.source}`, line {r.line}) — {_md_escape(d)}")
            if len(rules) > 4:
                lines.append(f"- *…and {len(rules) - 4} more in the full rules file.*")
        else:
            lines.append("*No detailed rules extracted for this slice.*")
        lines.append("")
        lines.append("[Full business rules](./business_rules.md)")
        lines.append("")

    lines.append("## Call graph (detail)")
    lines.append("")
    lines.append("See `flow.md` in this directory for the flat edge list.")
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def write_llm_entry_sidecar(sub: Path, entry_id: str, *, emit_cfg: bool = False) -> None:
    """Short pointer doc for LLM consumption (avoids duplicating full entry.md)."""
    lines = [
        "# LLM-oriented entry summary",
        "",
        f"- **Entry symbol:** `{entry_id}`",
        "- **Full narrative:** [entry.md](./entry.md)",
        "- **Flat call / condition list:** [flow.md](./flow.md)",
    ]
    if emit_cfg:
        lines.append("- **CFG paths (when emitted):** [cfg-paths.md](./cfg-paths.md)")
    lines.append("")
    (sub / "entry.llm.md").write_text("\n".join(lines), encoding="utf-8")


def write_system_overview(
    path: Path,
    rows: list[tuple[str, str, str, str, str]],
    *,
    project_hint: str | None = None,
    graph: CodeflowGraph | None = None,
    emit_graph_stats: bool = False,
    graph_reachability_include_contains: bool = False,
    extra_sections: list[str] | None = None,
) -> None:
    """Write root overview. Each row: ``(slug, type_label, start_method, link_line, one_line)``.

    ``link_line`` is typically ``[entry](./slug/entry.md)``.
    """
    lines: list[str] = []
    lines.append("# System overview")
    lines.append("")
    if project_hint:
        lines.append(project_hint)
        lines.append("")
    lines.append("Entries are listed in **priority order** (API, event, scheduler, main, …).")
    lines.append("")
    lines.append("| Type | Start method | Doc | Summary |")
    lines.append("| --- | --- | --- | --- |")
    for slug, typ, start_m, link, summary in rows:
        safe = summary.replace("|", "\\|")
        lines.append(f"| {typ} | `{start_m}` | {link} | {safe} |")
    lines.append("")
    if emit_graph_stats and graph is not None:
        lines.extend(_graph_inventory_lines(graph))
        lines.extend(
            _system_graph_insights_lines(
                graph,
                include_contains=graph_reachability_include_contains,
            ),
        )
    if extra_sections:
        lines.extend(extra_sections)
    path.write_text("\n".join(lines), encoding="utf-8")
