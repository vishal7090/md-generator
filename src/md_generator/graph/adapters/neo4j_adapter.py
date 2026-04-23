from __future__ import annotations

from typing import Any

from neo4j import GraphDatabase
from neo4j.exceptions import Neo4jError

from md_generator.graph.core.base_adapter import BaseAdapter
from md_generator.graph.core.graph_builder import apply_caps_sorted
from md_generator.graph.core.models import GraphMetadata, Node, Relationship
from md_generator.graph.core.run_config import GraphRunConfig


def _id_of(expr: str, use_element_id: bool) -> str:
    return f"elementId({expr})" if use_element_id else f"toString(id({expr}))"


class Neo4jAdapter(BaseAdapter):
    def __init__(self, cfg: GraphRunConfig) -> None:
        self._cfg = cfg.normalized()
        self._driver: Any = None
        self._use_element_id = self._cfg.neo4j_id_mode == "element_id"

    def connect(self) -> None:
        auth = (self._cfg.user, self._cfg.password) if self._cfg.user else None
        self._driver = GraphDatabase.driver(
            self._cfg.uri,
            auth=auth,
            connection_acquisition_timeout=self._cfg.connection_timeout_s,
        )

    def close(self) -> None:
        if self._driver is not None:
            self._driver.close()
            self._driver = None

    def validate_connection(self) -> None:
        self.connect()
        assert self._driver is not None
        self._driver.verify_connectivity()

    def _session(self) -> Any:
        assert self._driver is not None
        db = self._cfg.neo4j_database
        if db:
            return self._driver.session(database=db)
        return self._driver.session()

    def _run_read(self, query: str, **params: Any) -> list[dict[str, Any]]:
        assert self._driver is not None
        with self._session() as session:
            result = session.run(query, **params)
            return [r.data() for r in result]

    def _run_read_try_id_mode(self, query_el: str, query_int: str, **params: Any) -> list[dict[str, Any]]:
        use_el = self._use_element_id
        q = query_el if use_el else query_int
        try:
            return self._run_read(q, **params)
        except Neo4jError:
            if not use_el:
                raise
            self._use_element_id = False
            return self._run_read(query_int, **params)

    def get_nodes(self) -> list[Node]:
        return self._paginate_nodes(self._cfg.max_nodes)

    def get_relationships(self) -> list[Relationship]:
        nodes = {n.id for n in self._paginate_nodes(self._cfg.max_nodes)}
        return self._paginate_rels_scan(nodes, self._cfg.max_edges)

    def _paginate_nodes(self, cap: int) -> list[Node]:
        q_el = f"""
            MATCH (n)
            RETURN {_id_of('n', True)} AS id, labels(n) AS labels, properties(n) AS properties
            ORDER BY id
            SKIP $skip LIMIT $limit
            """
        q_int = f"""
            MATCH (n)
            RETURN {_id_of('n', False)} AS id, labels(n) AS labels, properties(n) AS properties
            ORDER BY id
            SKIP $skip LIMIT $limit
            """
        out: list[Node] = []
        skip = 0
        page = self._cfg.neo4j_page_size
        while len(out) < cap:
            lim = min(page, cap - len(out))
            rows = self._run_read_try_id_mode(q_el, q_int, skip=skip, limit=lim)
            if not rows:
                break
            for row in rows:
                labels = tuple(str(x) for x in (row.get("labels") or ()))
                props = {str(k): v for k, v in dict(row.get("properties") or {}).items()}
                out.append(Node(id=str(row["id"]), labels=labels or ("Node",), properties=props))
            skip += len(rows)
        return out

    def _paginate_rels_scan(self, allowed: set[str], cap: int) -> list[Relationship]:
        q_el = f"""
            MATCH (a)-[r]->(b)
            RETURN {_id_of('r', True)} AS id, type(r) AS typ,
                   {_id_of('a', True)} AS start_id,
                   {_id_of('b', True)} AS end_id,
                   properties(r) AS properties
            ORDER BY id
            SKIP $skip LIMIT $limit
            """
        q_int = f"""
            MATCH (a)-[r]->(b)
            RETURN {_id_of('r', False)} AS id, type(r) AS typ,
                   {_id_of('a', False)} AS start_id,
                   {_id_of('b', False)} AS end_id,
                   properties(r) AS properties
            ORDER BY id
            SKIP $skip LIMIT $limit
            """
        out: list[Relationship] = []
        skip = 0
        page = self._cfg.neo4j_page_size
        while len(out) < cap:
            lim = min(page, cap - len(out))
            rows = self._run_read_try_id_mode(q_el, q_int, skip=skip, limit=lim)
            if not rows:
                break
            for row in rows:
                sid = str(row["start_id"])
                eid = str(row["end_id"])
                if sid not in allowed or eid not in allowed:
                    continue
                props = {str(k): v for k, v in dict(row.get("properties") or {}).items()}
                out.append(
                    Relationship(
                        id=str(row["id"]),
                        type=str(row["typ"]),
                        start_node=sid,
                        end_node=eid,
                        properties=props,
                    )
                )
                if len(out) >= cap:
                    break
            skip += len(rows)
        return out

    def get_subgraph(self, depth: int, start_node: str | None = None) -> GraphMetadata:
        return self.extract_bounded(self._cfg)

    def extract_bounded(self, cfg: GraphRunConfig | None = None) -> GraphMetadata:
        cfg = (cfg or self._cfg).normalized()
        if cfg.start_node:
            nodes, rels = self._bfs_collect(cfg)
            meta = GraphMetadata(nodes=tuple(sorted(nodes, key=lambda n: n.id)), relationships=tuple(rels))
            return apply_caps_sorted(meta, max_nodes=cfg.max_nodes, max_edges=cfg.max_edges)
        nodes = self._paginate_nodes(cfg.max_nodes)
        nid_set = {n.id for n in nodes}
        rels = self._rels_between_ids(nid_set, cfg.max_edges)
        meta = GraphMetadata(nodes=tuple(sorted(nodes, key=lambda n: n.id)), relationships=tuple(rels))
        return apply_caps_sorted(meta, max_nodes=cfg.max_nodes, max_edges=cfg.max_edges)

    def _rels_between_ids(self, allowed: set[str], cap: int) -> list[Relationship]:
        ids = sorted(allowed)
        q_el = f"""
            MATCH (a)-[r]->(b)
            WHERE {_id_of('a', True)} IN $ids AND {_id_of('b', True)} IN $ids
            RETURN {_id_of('r', True)} AS id, type(r) AS typ,
                   {_id_of('a', True)} AS start_id,
                   {_id_of('b', True)} AS end_id,
                   properties(r) AS properties
            ORDER BY id
            SKIP $skip LIMIT $limit
            """
        q_int = f"""
            MATCH (a)-[r]->(b)
            WHERE {_id_of('a', False)} IN $ids AND {_id_of('b', False)} IN $ids
            RETURN {_id_of('r', False)} AS id, type(r) AS typ,
                   {_id_of('a', False)} AS start_id,
                   {_id_of('b', False)} AS end_id,
                   properties(r) AS properties
            ORDER BY id
            SKIP $skip LIMIT $limit
            """
        out: list[Relationship] = []
        skip = 0
        page = self._cfg.neo4j_page_size
        while len(out) < cap:
            lim = min(page, cap - len(out))
            rows = self._run_read_try_id_mode(q_el, q_int, ids=ids, skip=skip, limit=lim)
            if not rows:
                break
            for row in rows:
                props = {str(k): v for k, v in dict(row.get("properties") or {}).items()}
                out.append(
                    Relationship(
                        id=str(row["id"]),
                        type=str(row["typ"]),
                        start_node=str(row["start_id"]),
                        end_node=str(row["end_id"]),
                        properties=props,
                    )
                )
                if len(out) >= cap:
                    break
            skip += len(rows)
        return out

    def _bfs_collect(self, cfg: GraphRunConfig) -> tuple[list[Node], list[Relationship]]:
        assert cfg.start_node is not None
        start = cfg.start_node
        max_depth = cfg.depth if cfg.depth > 0 else 10**9
        max_nodes = cfg.max_nodes
        max_edges = cfg.max_edges

        visited: set[str] = set()
        node_by_id: dict[str, Node] = {}
        rel_by_id: dict[str, Relationship] = {}

        def fetch_node(nid: str) -> Node | None:
            q_el = f"""
                MATCH (n)
                WHERE {_id_of('n', True)} = $nid
                RETURN {_id_of('n', True)} AS id, labels(n) AS labels, properties(n) AS properties
                LIMIT 1
                """
            q_int = f"""
                MATCH (n)
                WHERE {_id_of('n', False)} = $nid
                RETURN {_id_of('n', False)} AS id, labels(n) AS labels, properties(n) AS properties
                LIMIT 1
                """
            rows = self._run_read_try_id_mode(q_el, q_int, nid=nid)
            if not rows:
                return None
            row = rows[0]
            labels = tuple(str(x) for x in (row.get("labels") or ()))
            props = {str(k): v for k, v in dict(row.get("properties") or {}).items()}
            return Node(id=str(row["id"]), labels=labels or ("Node",), properties=props)

        sn = fetch_node(start)
        if sn is None:
            return [], []
        visited.add(sn.id)
        node_by_id[sn.id] = sn

        q_el = f"""
            UNWIND $frontier AS fid
            MATCH (n)
            WHERE {_id_of('n', True)} = fid
            MATCH (n)-[r]-(m)
            RETURN DISTINCT {_id_of('m', True)} AS mid,
                   {_id_of('r', True)} AS rid,
                   type(r) AS typ,
                   {_id_of('startNode(r)', True)} AS start_id,
                   {_id_of('endNode(r)', True)} AS end_id,
                   properties(r) AS rprops,
                   labels(m) AS mlabels,
                   properties(m) AS mprops
            """
        q_int = f"""
            UNWIND $frontier AS fid
            MATCH (n)
            WHERE {_id_of('n', False)} = fid
            MATCH (n)-[r]-(m)
            RETURN DISTINCT {_id_of('m', False)} AS mid,
                   {_id_of('r', False)} AS rid,
                   type(r) AS typ,
                   {_id_of('startNode(r)', False)} AS start_id,
                   {_id_of('endNode(r)', False)} AS end_id,
                   properties(r) AS rprops,
                   labels(m) AS mlabels,
                   properties(m) AS mprops
            """

        layer: set[str] = {start}
        depth = 0
        while layer and depth < max_depth and len(visited) < max_nodes:
            frontier = sorted(layer)
            layer = set()
            for i in range(0, len(frontier), self._cfg.neo4j_page_size):
                batch = frontier[i : i + self._cfg.neo4j_page_size]
                rows = self._run_read_try_id_mode(q_el, q_int, frontier=batch)
                for row in rows:
                    rid = str(row["rid"])
                    if rid not in rel_by_id and len(rel_by_id) < max_edges:
                        rel_by_id[rid] = Relationship(
                            id=rid,
                            type=str(row["typ"]),
                            start_node=str(row["start_id"]),
                            end_node=str(row["end_id"]),
                            properties={str(k): v for k, v in dict(row.get("rprops") or {}).items()},
                        )
                    mid = str(row["mid"])
                    if mid in visited:
                        continue
                    if len(visited) >= max_nodes:
                        break
                    visited.add(mid)
                    labels = tuple(str(x) for x in (row.get("mlabels") or ()))
                    props = {str(k): v for k, v in dict(row.get("mprops") or {}).items()}
                    node_by_id[mid] = Node(id=mid, labels=labels or ("Node",), properties=props)
                    layer.add(mid)
                if len(visited) >= max_nodes:
                    break
            depth += 1

        nodes = [node_by_id[i] for i in sorted(node_by_id)]
        rels = [rel_by_id[i] for i in sorted(rel_by_id)]
        return nodes, rels
