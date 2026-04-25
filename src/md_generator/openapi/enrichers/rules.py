from __future__ import annotations

from dataclasses import replace

from md_generator.openapi.enrichers.sample_body import sample_from_schema
from md_generator.openapi.models.domain import ApiTestCase, AuthKind, EndpointDoc, SecuritySchemeDoc


def _sequence_mermaid(ep: EndpointDoc, api_title: str, auth_kinds: tuple[AuthKind, ...]) -> str:
    title = api_title.replace('"', "'")
    op = ep.operation_id.replace('"', "'")
    path = ep.path.replace('"', "'")
    lines = [
        "sequenceDiagram",
        "    autonumber",
        '    participant Client as Client',
        f'    participant API as API_{title[:40]}',
    ]
    if auth_kinds and auth_kinds != (AuthKind.NONE,):
        lines.append('    participant Auth as Auth')
        lines.append("    Client->>Auth: Obtain credentials")
        lines.append("    Auth-->>Client: Token / API key")
    lines.append(f"    Client->>API: {ep.method.value.upper()} {path}")
    lines.append("    Note right of API: " + op)
    lines.append("    API-->>Client: Response")
    return "\n".join(lines) + "\n"


def _auth_kinds_for_endpoint(ep: EndpointDoc, schemes: dict[str, SecuritySchemeDoc]) -> tuple[AuthKind, ...]:
    if not ep.security:
        return (AuthKind.NONE,)
    kinds: list[AuthKind] = []
    for block in ep.security:
        for name in block:
            doc = schemes.get(name)
            if doc:
                kinds.append(doc.auth_kind)
    if not kinds:
        return (AuthKind.NONE,)
    # stable unique order
    uniq = []
    seen: set[AuthKind] = set()
    for k in kinds:
        if k not in seen:
            seen.add(k)
            uniq.append(k)
    return tuple(uniq)


def _test_cases_for_endpoint(ep: EndpointDoc) -> tuple[ApiTestCase, ...]:
    sch = ep.request_schema
    if not sch:
        return (
            ApiTestCase(
                name="valid_request",
                description="No request body defined; send empty body.",
                body={},
            ),
        )
    valid = sample_from_schema(sch, invalid_enum=False, omit_keys=None)
    if not isinstance(valid, dict):
        valid = {"value": valid}
    omit_key: str | None = None
    req = sch.get("required")
    if isinstance(req, list) and req:
        candidates = sorted(str(x) for x in req if isinstance(x, str))
        omit_key = candidates[0]
    missing = sample_from_schema(sch, invalid_enum=False, omit_keys=frozenset({omit_key}) if omit_key else None)
    if not isinstance(missing, dict):
        missing = {"value": missing}
    invalid = sample_from_schema(sch, invalid_enum=True, omit_keys=None)
    if not isinstance(invalid, dict):
        invalid = {"value": invalid}
    out = [
        ApiTestCase(name="valid_request", description="All required fields populated (deterministic).", body=valid),
    ]
    if omit_key:
        out.append(
            ApiTestCase(
                name="missing_required_field",
                description=f"Omit required field `{omit_key}`.",
                body=missing,
            )
        )
    has_enum = _schema_has_enum(sch)
    if has_enum:
        out.append(
            ApiTestCase(
                name="invalid_enum",
                description="Value outside allowed enum (deterministic sentinel).",
                body=invalid,
            )
        )
    return tuple(out)


def _schema_has_enum(sch: dict) -> bool:
    if "enum" in sch:
        return True
    props = sch.get("properties")
    if isinstance(props, dict):
        for v in props.values():
            if isinstance(v, dict) and _schema_has_enum(v):
                return True
    for key in ("oneOf", "anyOf", "allOf"):
        node = sch.get(key)
        if isinstance(node, list):
            for item in node:
                if isinstance(item, dict) and _schema_has_enum(item):
                    return True
    return False


def enrich_endpoints(
    endpoints: tuple[EndpointDoc, ...],
    *,
    security_schemes: dict[str, SecuritySchemeDoc],
    api_title: str,
) -> tuple[EndpointDoc, ...]:
    out: list[EndpointDoc] = []
    for ep in endpoints:
        kinds = _auth_kinds_for_endpoint(ep, security_schemes)
        tests = _test_cases_for_endpoint(ep)
        seq = _sequence_mermaid(ep, api_title, kinds)
        out.append(
            replace(
                ep,
                auth_kinds=kinds,
                test_cases=tests,
                sequence_mermaid=seq,
            )
        )
    return tuple(out)
