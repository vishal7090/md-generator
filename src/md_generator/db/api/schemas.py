from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from md_generator.db.core.models import FEATURES
from md_generator.db.core.run_config import ErdConfig, RunConfig


class DatabaseSection(BaseModel):
    type: str = Field(..., description="postgres | mysql | oracle | mongo")
    uri: str
    schema: str | None = None
    database: str | None = None


class OutputSection(BaseModel):
    path: str = "./docs"
    split_files: bool = True


class FeaturesSection(BaseModel):
    include: list[str] | None = None
    exclude: list[str] = Field(default_factory=list)


class ExecutionSection(BaseModel):
    workers: int = Field(default=4, ge=1, le=32)


class ErdSection(BaseModel):
    max_tables: int = Field(default=100, ge=1, le=100_000)
    scope: Literal["full", "per_schema", "per_table"] = Field(
        default="full",
        description="full | per_schema | per_table",
    )


class DbToMdRunBody(BaseModel):
    database: DatabaseSection
    output: OutputSection = Field(default_factory=OutputSection)
    features: FeaturesSection = Field(default_factory=FeaturesSection)
    execution: ExecutionSection = Field(default_factory=ExecutionSection)
    limits: dict[str, Any] = Field(default_factory=dict)
    erd: ErdSection = Field(default_factory=ErdSection)

    @model_validator(mode="after")
    def check_features(self) -> DbToMdRunBody:
        if self.features.include:
            bad = set(self.features.include) - FEATURES
            if bad:
                raise ValueError(f"Unknown features in include: {sorted(bad)}")
        bad_ex = set(self.features.exclude) - FEATURES
        if bad_ex:
            raise ValueError(f"Unknown features in exclude: {sorted(bad_ex)}")
        return self

    def to_run_config(self) -> RunConfig:
        inc = frozenset(self.features.include) if self.features.include else frozenset(FEATURES)
        return RunConfig(
            db_type=self.database.type,
            uri=self.database.uri,
            schema=self.database.schema,
            database=self.database.database,
            output_path=Path(self.output.path),
            split_files=self.output.split_files,
            include=inc,
            exclude=frozenset(self.features.exclude),
            workers=self.execution.workers,
            limits=dict(self.limits),
            erd=ErdConfig(max_tables=self.erd.max_tables, scope=self.erd.scope).normalized(),
        )
