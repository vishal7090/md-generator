from __future__ import annotations

from md_generator.log.config.schemas import NormalizationSection, LogRunConfig
from md_generator.log.normalization.number_normalizer import mask_numbers
from md_generator.log.normalization.path_normalizer import mask_paths
from md_generator.log.normalization.pii_redactor import redact as redact_pii
from md_generator.log.normalization.uuid_normalizer import mask_uuids
from md_generator.log.parser.models import LogRecord


def normalize_record_text(text: str, norm: NormalizationSection) -> str:
    out = text
    if norm.redact_pii:
        out = redact_pii(out)
    if norm.normalize_uuid:
        out = mask_uuids(out)
    if norm.normalize_numbers:
        out = mask_numbers(out)
    if norm.normalize_paths:
        out = mask_paths(out)
    return out


def normalize_record(record: LogRecord, cfg: LogRunConfig) -> LogRecord:
    norm = cfg.normalization
    msg = normalize_record_text(record.message, norm)
    raw = normalize_record_text(record.raw_message, norm)
    st = record.stacktrace
    if st:
        st = normalize_record_text(st, norm)
    return LogRecord(
        timestamp=record.timestamp,
        level=record.level,
        logger=record.logger,
        thread=record.thread,
        message=msg,
        raw_message=raw,
        stacktrace=st,
        source_file=record.source_file,
        line_number=record.line_number,
        correlation_id=record.correlation_id,
        fingerprint=record.fingerprint,
        metadata=dict(record.metadata),
    )
