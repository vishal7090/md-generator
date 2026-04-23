from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from md_generator.graph.core.run_config import GraphRunConfig, VizConfig


class GraphSection(BaseModel):
    source: str = Field(..., description="networkx | neo4j")
    uri: str = ""
    user: str = ""
    password: str = ""
    database: str | None = Field(default=None, description="Neo4j database name")
    graph_file: str | None = None
    neo4j_id_mode: str = "element_id"
    neo4j_page_size: int = Field(default=500, ge=1, le=10_000)
    connection_timeout_s: float = Field(default=30.0, gt=0)
    depth: int = Field(default=0, ge=0)
    start_node: str | None = None
    max_nodes: int = Field(default=10_000, ge=1)
    max_edges: int = Field(default=50_000, ge=1)


class OutputSection(BaseModel):
    path: str = "./docs"
    split_files: bool = True
    combine_markdown: bool = True


class ExecutionSection(BaseModel):
    workers: int = Field(default=4, ge=1, le=32)


class VizSection(BaseModel):
    enabled: bool = False
    mermaid: bool = True
    formats: list[str] = Field(default_factory=lambda: ["png", "svg"])


class GraphToMdRunBody(BaseModel):
    graph: GraphSection
    output: OutputSection = Field(default_factory=OutputSection)
    execution: ExecutionSection = Field(default_factory=ExecutionSection)
    viz: VizSection = Field(default_factory=VizSection)

    def to_run_config(self) -> GraphRunConfig:
        gf = Path(self.graph.graph_file).expanduser() if self.graph.graph_file else None
        return GraphRunConfig(
            source=self.graph.source,
            uri=self.graph.uri,
            user=self.graph.user,
            password=self.graph.password,
            neo4j_database=self.graph.database,
            graph_file=gf,
            neo4j_id_mode=self.graph.neo4j_id_mode,
            neo4j_page_size=self.graph.neo4j_page_size,
            connection_timeout_s=self.graph.connection_timeout_s,
            depth=self.graph.depth,
            start_node=self.graph.start_node,
            max_nodes=self.graph.max_nodes,
            max_edges=self.graph.max_edges,
            output_path=Path(self.output.path),
            split_files=self.output.split_files,
            combine_markdown=self.output.combine_markdown,
            workers=self.execution.workers,
            viz=VizConfig(enabled=self.viz.enabled, mermaid=self.viz.mermaid, formats=tuple(self.viz.formats)),
        ).normalized()
