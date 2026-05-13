from __future__ import annotations

from md_generator.log.config.schemas import IncidentsSection, LogRunConfig
from md_generator.log.enrichment.hash_generator import stable_hash
from md_generator.log.incidents.fingerprinting import incident_fingerprint, title_slug
from md_generator.log.incidents.grouping import group_records
from md_generator.log.incidents.models import Incident, IncidentOccurrence
from md_generator.log.incidents.severity import score_occurrences
from md_generator.log.parser.models import LogRecord


def _to_occurrence(r: LogRecord) -> IncidentOccurrence:
    return IncidentOccurrence(
        timestamp=r.timestamp,
        level=r.level,
        message=r.message,
        source_file=r.source_file,
        line_number=r.line_number,
        stacktrace=r.stacktrace,
        logger=r.logger,
    )


def _affected_services(records: list[LogRecord]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for r in records:
        if r.logger:
            name = r.logger.strip()
            if name and name not in seen:
                seen.add(name)
                out.append(name)
    return sorted(out)


def build_incidents(records: list[LogRecord], cfg: LogRunConfig) -> list[Incident]:
    sec: IncidentsSection = cfg.incidents
    levels = frozenset(x.upper() for x in sec.levels) if sec.levels else None
    groups = group_records(
        records,
        min_occurrences=sec.min_occurrences,
        levels=levels,
        stacktrace_aware=sec.stacktrace_aware,
    )
    incidents: list[Incident] = []
    for fp, rs in groups.items():
        rs_sorted = sorted(rs, key=lambda x: (x.timestamp or x.line_number, x.line_number))
        first = rs_sorted[0]
        title = title_slug(first)
        incident_id = stable_hash(f"{fp}|{title}", n=12)
        occ = [_to_occurrence(r) for r in rs_sorted]
        reps: list[str] = []
        seen_msg: set[str] = set()
        for r in rs_sorted:
            m = r.message.replace("\n", " ")[:500]
            if m not in seen_msg:
                seen_msg.add(m)
                reps.append(m)
            if len(reps) >= 8:
                break
        stacks: list[str] = []
        seen_st: set[str] = set()
        for r in rs_sorted:
            if r.stacktrace and r.stacktrace not in seen_st:
                seen_st.add(r.stacktrace)
                stacks.append(r.stacktrace[:4000])
            if len(stacks) >= 5:
                break
        incidents.append(
            Incident(
                incident_id=incident_id,
                title=title,
                fingerprint=incident_fingerprint(first, stacktrace_aware=sec.stacktrace_aware),
                severity=score_occurrences(occ),
                occurrences=occ,
                representative_messages=reps,
                stacktraces=stacks,
                affected_services=_affected_services(rs_sorted),
            ),
        )
    incidents.sort(key=lambda i: (-i.severity, i.incident_id))
    return incidents
