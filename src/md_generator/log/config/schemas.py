from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class InputSection:
    paths: list[str] = field(default_factory=list)


@dataclass
class ParserSection:
    preset: str = "generic"
    line_regex: str | None = None
    fuzzy_timestamp: bool = False
    auto_detect: bool = False


@dataclass
class NormalizationSection:
    redact_pii: bool = False
    normalize_numbers: bool = False
    normalize_uuid: bool = False
    normalize_paths: bool = False


@dataclass
class AggregationSection:
    timeline: str = "hourly"  # none | hourly | daily


@dataclass
class ClusteringSection:
    enabled: bool = False
    algorithm: str = "kmeans"
    n_clusters: int = 8
    random_state: int = 42
    max_features: int = 4096


@dataclass
class OutputSection:
    path: str = "./log-docs"
    split_by_level: bool = True
    generate_incidents: bool = True
    generate_clusters: bool = False
    generate_chunks: bool = False


@dataclass
class ChunkSection:
    enabled: bool = False
    lines_per_chunk: int = 100_000
    records_per_md_chunk: int = 500


@dataclass
class ExecutionSection:
    workers: int = 4
    max_lines_per_file: int | None = None
    encoding_fallbacks: list[str] = field(
        default_factory=lambda: ["utf-8", "utf-8-sig", "latin-1", "cp1252"],
    )


@dataclass
class PluginsSection:
    enrichers: list[str] = field(default_factory=list)
    parsers: list[str] = field(default_factory=list)
    writers: list[str] = field(default_factory=list)
    classifiers: list[str] = field(default_factory=list)


@dataclass
class IncidentsSection:
    min_occurrences: int = 2
    levels: list[str] = field(default_factory=lambda: ["ERROR", "FATAL", "WARN"])
    stacktrace_aware: bool = True


@dataclass
class ChunkingSection:
    enabled: bool = False
    strategies: list[str] = field(
        default_factory=lambda: ["incident", "timeline", "stacktrace", "cluster", "service"],
    )
    chunk_id_namespace: str = "chunk"
    max_chunk_bytes: int = 256_000


@dataclass
class EmbeddingsSection:
    enabled: bool = False
    exporters: list[str] = field(default_factory=list)
    output_subdir: str = "embeddings"


@dataclass
class CorrelationSection:
    enabled: bool = False
    timeline_window_seconds: int = 300


@dataclass
class KnowledgeGraphSection:
    enabled: bool = False
    mermaid: bool = True


@dataclass
class TimelineSection:
    enabled: bool = False
    causal_window_seconds: int = 120


@dataclass
class IntelligenceSection:
    enabled: bool = False


@dataclass
class SearchSection:
    index_path: str | None = None


@dataclass
class LogRunConfig:
    input: InputSection = field(default_factory=InputSection)
    parser: ParserSection = field(default_factory=ParserSection)
    normalization: NormalizationSection = field(default_factory=NormalizationSection)
    aggregation: AggregationSection = field(default_factory=AggregationSection)
    clustering: ClusteringSection = field(default_factory=ClusteringSection)
    output: OutputSection = field(default_factory=OutputSection)
    chunk: ChunkSection = field(default_factory=ChunkSection)
    execution: ExecutionSection = field(default_factory=ExecutionSection)
    plugins: PluginsSection = field(default_factory=PluginsSection)
    incidents: IncidentsSection = field(default_factory=IncidentsSection)
    chunking: ChunkingSection = field(default_factory=ChunkingSection)
    embeddings: EmbeddingsSection = field(default_factory=EmbeddingsSection)
    correlation: CorrelationSection = field(default_factory=CorrelationSection)
    knowledge_graph: KnowledgeGraphSection = field(default_factory=KnowledgeGraphSection)
    timeline: TimelineSection = field(default_factory=TimelineSection)
    intelligence: IntelligenceSection = field(default_factory=IntelligenceSection)
    search: SearchSection = field(default_factory=SearchSection)

    def resolved_input_paths(self) -> list[Path]:
        return [Path(p).expanduser().resolve() for p in self.input.paths if str(p).strip()]

    def output_path(self) -> Path:
        return Path(self.output.path).expanduser().resolve()

    def normalized(self) -> LogRunConfig:
        tl = (self.aggregation.timeline or "none").lower().strip()
        if tl not in {"none", "hourly", "daily"}:
            tl = "hourly"
        alg = (self.clustering.algorithm or "kmeans").lower().strip()
        nc = max(2, min(int(self.clustering.n_clusters), 10_000))
        mf = max(100, min(int(self.clustering.max_features), 100_000))
        workers = max(1, min(int(self.execution.workers), 64))
        lines_chunk = max(1000, int(self.chunk.lines_per_chunk))
        rec_chunk = max(10, int(self.chunk.records_per_md_chunk))
        from dataclasses import replace

        return replace(
            self,
            aggregation=replace(self.aggregation, timeline=tl),
            clustering=replace(
                self.clustering,
                algorithm=alg,
                n_clusters=nc,
                max_features=mf,
            ),
            execution=replace(self.execution, workers=workers),
            chunk=replace(
                self.chunk,
                lines_per_chunk=lines_chunk,
                records_per_md_chunk=rec_chunk,
            ),
        )
