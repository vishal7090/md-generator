from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from .chunks import strip_yaml_frontmatter
from .rag import try_chroma_retrieve
from .registry import Registry


@dataclass
class AskResult:
    query: str
    resolved_skill_ids: list[str]
    resolved_areas: list[str]
    context_markdown: str
    scores: dict[str, int] = field(default_factory=dict)
    rag_used: bool = False


def _tokenize(q: str) -> list[str]:
    return re.findall(r"[a-zA-Z0-9][a-zA-Z0-9_-]*", q.lower())


def _load_graph(path: Path | None) -> dict:
    if not path or not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _neighbor_areas(graph: dict, areas: set[str], depth: int = 1) -> set[str]:
    if depth < 1:
        return set()
    edges = graph.get("edges") or []
    out: set[str] = set()
    for e in edges:
        s, t = e.get("source"), e.get("target")
        if s in areas and isinstance(t, str) and t != "__root__":
            out.add(t)
        if t in areas and isinstance(s, str) and s != "__root__":
            out.add(s)
    return out


def _score_keywords(query_lower: str, tokens: set[str], registry: Registry) -> dict[str, int]:
    scores: dict[str, int] = {}
    q = query_lower
    for row in registry.keyword_routing():
        kw = str(row.get("keyword", "")).lower()
        if not kw:
            continue
        pr = int(row.get("priority", 0))
        areas = row.get("areas") or []
        if not isinstance(areas, list):
            continue
        hit = 0
        if kw in tokens:
            hit = pr
        elif kw in q:
            hit = max(pr // 2, 1)
        if hit:
            for a in areas:
                if not isinstance(a, str):
                    continue
                scores[a] = scores.get(a, 0) + hit
    return scores


class MasterAgent:
    def __init__(self, registry: Registry) -> None:
        self.registry = registry

    def ask(
        self,
        query: str,
        *,
        use_rag: bool = False,
        graph_depth: int = 1,
        include_reference: bool | None = None,
    ) -> AskResult:
        qlow = query.lower()
        tokens = set(_tokenize(query))
        area_scores = _score_keywords(qlow, tokens, self.registry)

        if include_reference is None:
            include_reference = any(
                x in qlow for x in ("mcp", "fastapi", "http", "api", "entrypoint", "cli", "all scripts")
            )

        if not area_scores or max(area_scores.values(), default=0) < 3:
            area_scores["global"] = area_scores.get("global", 0) + 5

        ranked_areas = sorted(area_scores.keys(), key=lambda a: (-area_scores[a], a))
        selected_areas: list[str] = []
        for a in ranked_areas[:6]:
            if a not in selected_areas:
                selected_areas.append(a)

        graph_path = self.registry.dependency_graph_path()
        graph = _load_graph(graph_path)
        area_set = set(selected_areas)
        neighbors = _neighbor_areas(graph, area_set, depth=graph_depth)
        for n in sorted(neighbors):
            if n not in area_set and self.registry.module_skill_id(n):
                selected_areas.append(n)

        skill_ids: list[str] = []
        for area in selected_areas:
            sid = self.registry.module_skill_id(area)
            if sid and sid not in skill_ids:
                skill_ids.append(sid)
        if include_reference and "mdengine-reference" not in skill_ids:
            skill_ids.append("mdengine-reference")

        order = self.registry.skill_order()
        skill_ids = sorted(skill_ids, key=lambda s: (order.index(s) if s in order else 999, s))

        rag_used = False
        context_parts: list[str] = []
        if use_rag:
            rag_blob = try_chroma_retrieve(self.registry, query, skill_ids, k=10)
            if rag_blob:
                rag_used = True
                context_parts.append("## Retrieved skill excerpts (RAG)\n\n" + rag_blob)

        if not rag_used:
            gpath = self.registry.global_architecture_path()
            if gpath and gpath.is_file():
                context_parts.append(
                    "## Global architecture\n\n" + strip_yaml_frontmatter(gpath.read_text(encoding="utf-8"))
                )
            for sid in skill_ids:
                p = self.registry.skill_path(sid)
                if not p or not p.is_file():
                    continue
                body = strip_yaml_frontmatter(p.read_text(encoding="utf-8"))
                context_parts.append(f"## Skill `{sid}`\n\n{body}")

        ctx = "\n\n---\n\n".join(context_parts)
        return AskResult(
            query=query,
            resolved_skill_ids=skill_ids,
            resolved_areas=selected_areas,
            context_markdown=ctx,
            scores=area_scores,
            rag_used=rag_used,
        )
