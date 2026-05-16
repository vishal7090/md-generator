from __future__ import annotations

import re

from md_generator.log.enrichment.hash_generator import stable_hash
from md_generator.log.normalization.number_normalizer import mask_numbers
from md_generator.log.normalization.uuid_normalizer import mask_uuids
from md_generator.log.parser.models import LogRecord

_IP = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")


def mask_ips(text: str) -> str:
    return _IP.sub("<IP>", text)


def normalize_for_incident(text: str) -> str:
    out = mask_ips(mask_uuids(mask_numbers(text)))
    return out.strip()


def incident_fingerprint(record: LogRecord, *, stacktrace_aware: bool) -> str:
    msg = normalize_for_incident(record.message)
    basis = msg
    if stacktrace_aware and record.stacktrace:
        head = record.stacktrace.splitlines()[0] if record.stacktrace else ""
        basis = f"{msg}|{normalize_for_incident(head)}"
    return stable_hash(basis, n=16)


def title_slug(record: LogRecord) -> str:
    t = normalize_for_incident(record.message).replace("\n", " ")[:80].strip()
    return t or "unknown"
