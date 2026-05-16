from __future__ import annotations

from md_generator.log.config.schemas import LogRunConfig, NoiseReductionSection
from md_generator.log.noise_reduction.dedupe import dedupe_records
from md_generator.log.noise_reduction.entropy import repetition_score
from md_generator.log.parser.models import LogRecord


def apply_noise_filters(records: list[LogRecord], cfg: LogRunConfig | NoiseReductionSection) -> list[LogRecord]:
    section = cfg.noise_reduction if hasattr(cfg, "noise_reduction") else cfg
    if not section.enabled:
        return records
    out = records
    if section.dedupe:
        out = dedupe_records(out)
    thr = section.entropy_threshold
    min_len = section.min_message_length
    filtered: list[LogRecord] = []
    for r in out:
        msg = r.message or ""
        if len(msg.strip()) < min_len:
            continue
        if repetition_score(msg) < thr:
            continue
        filtered.append(r)
    return filtered
