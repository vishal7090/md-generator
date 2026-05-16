from __future__ import annotations

from collections.abc import Iterator

from md_generator.log.chunking.chunk_models import SemanticChunk
from md_generator.log.chunking.chunk_registry import STRATEGIES
from md_generator.log.config.schemas import LogRunConfig
from md_generator.log.incidents.models import Incident
from md_generator.log.parser.models import LogRecord


def iter_semantic_chunks(
    records: list[LogRecord],
    incidents: list[Incident],
    cfg: LogRunConfig,
) -> Iterator[SemanticChunk]:
    if not cfg.chunking.enabled and not cfg.output.generate_chunks:
        return
    for name in cfg.chunking.strategies:
        strat = STRATEGIES.get(name)
        if strat is None:
            continue
        yield from strat.iter_chunks(records, incidents, cfg)
