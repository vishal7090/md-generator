"""Rank entry points for documentation order (API first, then events, scheduler, main, etc.)."""

from __future__ import annotations

import networkx as nx

from md_generator.codeflow.models.ir import EntryKind, EntryRecord


def entry_kind_rank(kind: str | None) -> int:
    """Lower rank = earlier in docs. Unknown kinds sort last."""
    if not kind:
        return 90
    order = {
        EntryKind.API_REST.value: 0,
        EntryKind.PORTLET.value: 0,
        EntryKind.KAFKA.value: 1,
        EntryKind.QUEUE.value: 1,
        EntryKind.SCHEDULER.value: 2,
        EntryKind.MAIN.value: 3,
        EntryKind.CLI.value: 4,
        EntryKind.UNKNOWN.value: 5,
    }
    return order.get(kind, 50)


def _kind_for_entry_id(
    entry_id: str,
    g: nx.DiGraph,
    by_symbol: dict[str, EntryRecord],
) -> str | None:
    rec = by_symbol.get(entry_id)
    if rec is not None:
        return rec.kind.value
    if entry_id in g:
        return g.nodes[entry_id].get("entry_kind")
    return None


def sort_entry_ids(
    entry_ids: list[str],
    g: nx.DiGraph,
    all_entries: list[EntryRecord],
) -> list[str]:
    """Stable sort: API → event (kafka/queue) → scheduler → main → cli → unknown; tie-break by ``entry_id``."""
    by_symbol = {e.symbol_id: e for e in all_entries}

    def sort_key(eid: str) -> tuple[int, str]:
        k = _kind_for_entry_id(eid, g, by_symbol)
        return (entry_kind_rank(k), eid)

    return sorted(entry_ids, key=sort_key)
