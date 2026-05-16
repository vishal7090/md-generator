from __future__ import annotations

from collections.abc import Iterator
from typing import Protocol

from md_generator.log.chunking.chunk_models import SemanticChunk
from md_generator.log.config.schemas import LogRunConfig
from md_generator.log.incidents.models import Incident
from md_generator.log.parser.models import LogRecord


class ChunkStrategy(Protocol):
  name: str

  def iter_chunks(
      self,
      records: list[LogRecord],
      incidents: list[Incident],
      cfg: LogRunConfig,
  ) -> Iterator[SemanticChunk]: ...
