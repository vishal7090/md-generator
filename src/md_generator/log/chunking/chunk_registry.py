from __future__ import annotations

from collections.abc import Iterator

from md_generator.log.chunking.chunk_models import SemanticChunk
from md_generator.log.chunking.chunk_strategy import ChunkStrategy
from md_generator.log.config.schemas import LogRunConfig
from md_generator.log.incidents.models import Incident
from md_generator.log.parser.models import LogRecord


class IncidentChunkStrategy:
    name = "incident"

    def iter_chunks(
        self,
        records: list[LogRecord],
        incidents: list[Incident],
        cfg: LogRunConfig,
    ) -> Iterator[SemanticChunk]:
        ns = cfg.chunking.chunk_id_namespace
        for i, inc in enumerate(incidents, start=1):
            slug = inc.title.lower().replace(" ", "_")[:40] or "incident"
            cid = f"chunk://{ns}/incident/{slug}/{i:04d}"
            body = "\n".join(f"- {m}" for m in inc.representative_messages)
            yield SemanticChunk(
                chunk_id=cid,
                chunk_type="incident",
                title=inc.title,
                content=body,
                metadata={"severity": inc.severity, "occurrences": len(inc.occurrences)},
                source_refs=[inc.incident_id],
            )


class TimelineChunkStrategy:
    name = "timeline"

    def iter_chunks(
        self,
        records: list[LogRecord],
        incidents: list[Incident],
        cfg: LogRunConfig,
    ) -> Iterator[SemanticChunk]:
        ordered = sorted(records, key=lambda r: (r.timestamp or r.line_number, r.line_number))
        if not ordered:
            return
        lines = []
        for r in ordered[:200]:
            ts = r.timestamp.isoformat() if r.timestamp else "n/a"
            lines.append(f"{ts} [{r.level}] {r.message[:300]}")
        yield SemanticChunk(
            chunk_id=f"chunk://{cfg.chunking.chunk_id_namespace}/timeline/0001",
            chunk_type="timeline",
            title="Operational timeline",
            content="\n".join(lines),
            metadata={"record_count": len(ordered)},
            source_refs=[],
        )


class StacktraceChunkStrategy:
    name = "stacktrace"

    def iter_chunks(
        self,
        records: list[LogRecord],
        incidents: list[Incident],
        cfg: LogRunConfig,
    ) -> Iterator[SemanticChunk]:
        n = 0
        for r in records:
            if not r.stacktrace:
                continue
            n += 1
            yield SemanticChunk(
                chunk_id=f"chunk://{cfg.chunking.chunk_id_namespace}/stacktrace/{n:04d}",
                chunk_type="stacktrace",
                title=f"Stacktrace at line {r.line_number}",
                content=r.stacktrace[: cfg.chunking.max_chunk_bytes],
                metadata={"level": r.level},
                source_refs=[str(r.source_file)],
            )


class ClusterChunkStrategy:
    name = "cluster"

    def iter_chunks(
        self,
        records: list[LogRecord],
        incidents: list[Incident],
        cfg: LogRunConfig,
    ) -> Iterator[SemanticChunk]:
        by_cluster: dict[int, list[LogRecord]] = {}
        for r in records:
            c = r.metadata.get("cluster")
            if c is None:
                continue
            by_cluster.setdefault(int(c), []).append(r)
        for cid, rs in sorted(by_cluster.items()):
            msgs = [r.message[:200] for r in rs[:20]]
            yield SemanticChunk(
                chunk_id=f"chunk://{cfg.chunking.chunk_id_namespace}/cluster/{cid:04d}",
                chunk_type="cluster",
                title=f"Cluster {cid}",
                content="\n".join(msgs),
                metadata={"size": len(rs)},
                source_refs=[],
            )


class ServiceChunkStrategy:
    name = "service"

    def iter_chunks(
        self,
        records: list[LogRecord],
        incidents: list[Incident],
        cfg: LogRunConfig,
    ) -> Iterator[SemanticChunk]:
        by_svc: dict[str, list[LogRecord]] = {}
        for r in records:
            svc = r.logger or "unknown"
            by_svc.setdefault(svc, []).append(r)
        for i, (svc, rs) in enumerate(sorted(by_svc.items()), start=1):
            msgs = [f"[{r.level}] {r.message[:200]}" for r in rs[:30]]
            yield SemanticChunk(
                chunk_id=f"chunk://{cfg.chunking.chunk_id_namespace}/service/{i:04d}",
                chunk_type="service",
                title=svc,
                content="\n".join(msgs),
                metadata={"count": len(rs)},
                source_refs=[svc],
            )


STRATEGIES: dict[str, ChunkStrategy] = {
    IncidentChunkStrategy.name: IncidentChunkStrategy(),
    TimelineChunkStrategy.name: TimelineChunkStrategy(),
    StacktraceChunkStrategy.name: StacktraceChunkStrategy(),
    ClusterChunkStrategy.name: ClusterChunkStrategy(),
    ServiceChunkStrategy.name: ServiceChunkStrategy(),
}
