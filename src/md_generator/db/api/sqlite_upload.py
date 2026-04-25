from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from md_generator.db.core.models import FEATURES
from md_generator.db.core.run_config import ErdConfig, RunConfig


class SqliteUploadOutputSection(BaseModel):
    path: str = "./docs"
    split_files: bool = True
    write_combined_feature_markdown: bool = False
    readme_feature_merge: Literal["none", "inline", "toc"] = "none"


class SqliteUploadFeaturesSection(BaseModel):
    include: list[str] | None = None
    exclude: list[str] = Field(default_factory=list)


class SqliteUploadExecutionSection(BaseModel):
    workers: int = Field(default=4, ge=1, le=32)


class SqliteUploadErdSection(BaseModel):
    max_tables: int = Field(default=100, ge=1, le=100_000)
    scope: Literal["full", "per_schema", "per_table"] = Field(default="full")


class SqliteUploadJsonBody(BaseModel):
    """Same export options as ``DbToMdRunBody`` except the DB file comes from the upload."""

    schema: str | None = Field(default="main", description="SQLite catalog (default main)")
    output: SqliteUploadOutputSection = Field(default_factory=SqliteUploadOutputSection)
    features: SqliteUploadFeaturesSection = Field(default_factory=SqliteUploadFeaturesSection)
    execution: SqliteUploadExecutionSection = Field(default_factory=SqliteUploadExecutionSection)
    limits: dict[str, Any] = Field(default_factory=dict)
    erd: SqliteUploadErdSection = Field(default_factory=SqliteUploadErdSection)

    @model_validator(mode="after")
    def check_features(self) -> SqliteUploadJsonBody:
        if self.features.include:
            bad = set(self.features.include) - FEATURES
            if bad:
                raise ValueError(f"Unknown features in include: {sorted(bad)}")
        bad_ex = set(self.features.exclude) - FEATURES
        if bad_ex:
            raise ValueError(f"Unknown features in exclude: {sorted(bad_ex)}")
        return self

    def to_run_config(self, sqlite_uri: str) -> RunConfig:
        sch = self.schema
        if sch is None or str(sch).strip() == "" or str(sch).lower() == "public":
            sch = "main"
        inc = frozenset(self.features.include) if self.features.include else frozenset(FEATURES)
        merge = self.output.readme_feature_merge
        write_combined = self.output.write_combined_feature_markdown
        if merge != "none" and self.output.split_files:
            write_combined = True
        return RunConfig(
            db_type="sqlite",
            uri=sqlite_uri,
            schema=sch,
            database=None,
            output_path=Path(self.output.path),
            split_files=self.output.split_files,
            write_combined_feature_markdown=write_combined,
            readme_feature_merge=merge,
            include=inc,
            exclude=frozenset(self.features.exclude),
            workers=self.execution.workers,
            limits=dict(self.limits),
            erd=ErdConfig(max_tables=self.erd.max_tables, scope=self.erd.scope).normalized(),
        )


def parse_sqlite_upload_config_json(raw: str | None) -> SqliteUploadJsonBody:
    if raw is None or not str(raw).strip():
        return SqliteUploadJsonBody()
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("config must be a JSON object")
    return SqliteUploadJsonBody.model_validate(data)
