from __future__ import annotations

from dataclasses import replace

from md_generator.log.enrichment.hash_generator import stable_hash
from md_generator.log.parser.models import LogRecord


def add_fingerprint(record: LogRecord) -> LogRecord:
    basis = f"{record.level}|{record.message}"
    return replace(record, fingerprint=stable_hash(basis, n=16))
