from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from md_generator.log.config.schemas import LogRunConfig


class InputSectionModel(BaseModel):
    paths: list[str] = Field(default_factory=list)


class ParserSectionModel(BaseModel):
    preset: str = "generic"
    line_regex: str | None = None
    fuzzy_timestamp: bool = False
    auto_detect: bool = False


class NormalizationSectionModel(BaseModel):
    redact_pii: bool = False
    normalize_numbers: bool = False
    normalize_uuid: bool = False
    normalize_paths: bool = False


class AggregationSectionModel(BaseModel):
    timeline: Literal["none", "hourly", "daily"] = "hourly"


class ClusteringSectionModel(BaseModel):
    enabled: bool = False
    algorithm: str = "kmeans"
    n_clusters: int = Field(default=8, ge=2, le=500)
    random_state: int = 42
    max_features: int = Field(default=4096, ge=100, le=100_000)


class OutputSectionModel(BaseModel):
    path: str = "./log-docs"
    split_by_level: bool = True
    generate_incidents: bool = True
    generate_clusters: bool = False
    generate_chunks: bool = False


class ChunkSectionModel(BaseModel):
    enabled: bool = False
    lines_per_chunk: int = Field(default=100_000, ge=1000)
    records_per_md_chunk: int = Field(default=500, ge=10)


class ExecutionSectionModel(BaseModel):
    workers: int = Field(default=4, ge=1, le=64)
    max_lines_per_file: int | None = None
    encoding_fallbacks: list[str] = Field(
        default_factory=lambda: ["utf-8", "utf-8-sig", "latin-1", "cp1252"],
    )


class PluginsSectionModel(BaseModel):
    enrichers: list[str] = Field(default_factory=list)


class LogToMdRunBody(BaseModel):
    input: InputSectionModel = Field(default_factory=InputSectionModel)
    parser: ParserSectionModel = Field(default_factory=ParserSectionModel)
    normalization: NormalizationSectionModel = Field(default_factory=NormalizationSectionModel)
    aggregation: AggregationSectionModel = Field(default_factory=AggregationSectionModel)
    clustering: ClusteringSectionModel = Field(default_factory=ClusteringSectionModel)
    output: OutputSectionModel = Field(default_factory=OutputSectionModel)
    chunk: ChunkSectionModel = Field(default_factory=ChunkSectionModel)
    execution: ExecutionSectionModel = Field(default_factory=ExecutionSectionModel)
    plugins: PluginsSectionModel = Field(default_factory=PluginsSectionModel)

    def to_log_run_config(self) -> LogRunConfig:
        from md_generator.log.config.schemas import (
            AggregationSection,
            ChunkSection,
            ClusteringSection,
            ExecutionSection,
            InputSection,
            NormalizationSection,
            OutputSection,
            ParserSection,
            PluginsSection,
        )

        return LogRunConfig(
            input=InputSection(paths=list(self.input.paths)),
            parser=ParserSection(
                preset=self.parser.preset,
                line_regex=self.parser.line_regex,
                fuzzy_timestamp=self.parser.fuzzy_timestamp,
                auto_detect=self.parser.auto_detect,
            ),
            normalization=NormalizationSection(
                redact_pii=self.normalization.redact_pii,
                normalize_numbers=self.normalization.normalize_numbers,
                normalize_uuid=self.normalization.normalize_uuid,
                normalize_paths=self.normalization.normalize_paths,
            ),
            aggregation=AggregationSection(timeline=self.aggregation.timeline),
            clustering=ClusteringSection(
                enabled=self.clustering.enabled,
                algorithm=self.clustering.algorithm,
                n_clusters=self.clustering.n_clusters,
                random_state=self.clustering.random_state,
                max_features=self.clustering.max_features,
            ),
            output=OutputSection(
                path=self.output.path,
                split_by_level=self.output.split_by_level,
                generate_incidents=self.output.generate_incidents,
                generate_clusters=self.output.generate_clusters,
                generate_chunks=self.output.generate_chunks,
            ),
            chunk=ChunkSection(
                enabled=self.chunk.enabled,
                lines_per_chunk=self.chunk.lines_per_chunk,
                records_per_md_chunk=self.chunk.records_per_md_chunk,
            ),
            execution=ExecutionSection(
                workers=self.execution.workers,
                max_lines_per_file=self.execution.max_lines_per_file,
                encoding_fallbacks=list(self.execution.encoding_fallbacks),
            ),
            plugins=PluginsSection(enrichers=list(self.plugins.enrichers)),
        ).normalized()


def parse_log_upload_config_json(raw: str | None) -> LogToMdRunBody:
    import json

    if raw is None or not str(raw).strip():
        return LogToMdRunBody()
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("config must be a JSON object")
    return LogToMdRunBody.model_validate(data)
