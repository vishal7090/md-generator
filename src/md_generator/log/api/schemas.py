from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from md_generator.log.config.schemas import LogRunConfig


class InputSectionModel(BaseModel):
    paths: list[str] = Field(default_factory=list)
    otel_path: str | None = None


class ParserSectionModel(BaseModel):
    preset: str = "generic"
    line_regex: str | None = None
    fuzzy_timestamp: bool = False
    auto_detect: bool = False
    preset_dirs: list[str] = Field(default_factory=list)


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
    frontmatter: bool = False


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
    batch_records: int = Field(default=10_000, ge=100)
    use_runtime: bool = False
    distributed: bool = False


class IncrementalSectionModel(BaseModel):
    enabled: bool = False
    checkpoint_path: str | None = None


class StreamingSectionModel(BaseModel):
    enabled: bool = False
    source: str = "tail"
    batch_size: int = Field(default=100, ge=1)


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
    incremental: IncrementalSectionModel = Field(default_factory=IncrementalSectionModel)
    streaming: StreamingSectionModel = Field(default_factory=StreamingSectionModel)

    model_config = {"extra": "allow"}

    def to_log_run_config(self) -> LogRunConfig:
        from md_generator.log.core.run_config import jsonable_to_log_config

        return jsonable_to_log_config(self.model_dump()).normalized()


def parse_log_upload_config_json(raw: str | None) -> LogToMdRunBody:
    import json

    if raw is None or not str(raw).strip():
        return LogToMdRunBody()
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("config must be a JSON object")
    return LogToMdRunBody.model_validate(data)
