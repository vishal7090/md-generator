from __future__ import annotations

import copy
from typing import Any

from md_generator.openapi.models.domain import (
    ApiTestCase,
    AuthKind,
    EndpointDoc,
    HttpMethod,
    ParameterDoc,
    ResponseDoc,
    SecuritySchemeDoc,
)
from md_generator.openapi.normalizers.schema_flatten import collect_schema_refs, flatten_schema


def load_security_schemes(spec: dict[str, Any]) -> dict[str, SecuritySchemeDoc]:
    comps = spec.get("components") or {}
    raw = comps.get("securitySchemes") or {}
    if not isinstance(raw, dict):
        return {}
    out: dict[str, SecuritySchemeDoc] = {}
    for key in sorted(raw.keys()):
        sch = raw[key]
        if not isinstance(sch, dict):
            continue
        typ = str(sch.get("type") or "other")
        scheme = sch.get("scheme")
        scheme_s = str(scheme) if scheme is not None else None
        bearer_format = sch.get("bearerFormat")
        bf = str(bearer_format) if bearer_format is not None else None
        in_ = sch.get("in")
        in_s = str(in_) if in_ is not None else None
        name = sch.get("name")
        name_s = str(name) if name is not None else None
        flows = sch.get("flows")
        flows_summary = ""
        if isinstance(flows, dict):
            parts = [f"{fk}:{sorted((flows[fk] or {}).keys())}" for fk in sorted(flows.keys())]
            flows_summary = ";".join(parts)
        auth_kind = _classify_auth(typ, scheme_s, sch)
        out[key] = SecuritySchemeDoc(
            key=key,
            type=typ,
            scheme=scheme_s,
            bearer_format=bf,
            in_=in_s,
            name=name_s,
            flows_summary=flows_summary,
            auth_kind=auth_kind,
        )
    return out


def _classify_auth(typ: str, scheme: str | None, sch: dict[str, Any]) -> AuthKind:
    if typ == "apiKey":
        return AuthKind.API_KEY
    if typ == "http":
        if (scheme or "").lower() == "bearer":
            return AuthKind.HTTP_BEARER
        return AuthKind.OTHER
    if typ == "oauth2":
        return AuthKind.OAUTH2
    if typ == "openIdConnect":
        return AuthKind.OPENID
    if typ == "mutualTLS":
        return AuthKind.MUTUAL_TLS
    _ = sch
    return AuthKind.OTHER


def _crud_intent(method: HttpMethod) -> str:
    m = method.value
    if m == "get":
        return "read"
    if m == "post":
        return "create"
    if m in ("put", "patch"):
        return "update"
    if m == "delete":
        return "delete"
    return "other"


def _merge_parameters(path_level: list[Any] | None, op_level: list[Any] | None) -> list[dict[str, Any]]:
    def key(p: dict[str, Any]) -> tuple[str, str]:
        return (str(p.get("name") or ""), str(p.get("in") or ""))

    merged: dict[tuple[str, str], dict[str, Any]] = {}
    for p in path_level or []:
        if isinstance(p, dict):
            merged[key(p)] = p
    for p in op_level or []:
        if isinstance(p, dict):
            merged[key(p)] = p
    return [merged[k] for k in sorted(merged.keys())]


def _param_doc(p: dict[str, Any]) -> ParameterDoc:
    sch = p.get("schema") if isinstance(p.get("schema"), dict) else {}
    if not isinstance(sch, dict):
        sch = {}
    desc = p.get("description")
    return ParameterDoc(
        name=str(p.get("name") or ""),
        in_=str(p.get("in") or ""),
        required=bool(p.get("required")),
        schema=flatten_schema(sch) or sch,
        description=str(desc).strip() if isinstance(desc, str) else "",
    )


def _pick_media(
    content: dict[str, Any] | None,
    preferred: str,
) -> tuple[str | None, dict[str, Any] | None]:
    if not isinstance(content, dict) or not content:
        return None, None
    keys = sorted(content.keys())
    if preferred in content:
        k = preferred
    else:
        k = keys[0]
    node = content.get(k)
    if not isinstance(node, dict):
        return k, None
    return k, node


def _responses_doc(
    responses: dict[str, Any] | None,
    preferred_media: str,
) -> tuple[ResponseDoc, ...]:
    if not isinstance(responses, dict):
        return ()
    out: list[ResponseDoc] = []
    for status in sorted(responses.keys(), key=lambda s: (len(str(s)), str(s))):
        resp = responses[status]
        if not isinstance(resp, dict):
            continue
        desc = resp.get("description")
        content = resp.get("content")
        media, node = _pick_media(content if isinstance(content, dict) else None, preferred_media)
        mts: tuple[str, ...] = ()
        sch: dict[str, Any] | None = None
        if isinstance(content, dict):
            mts = tuple(sorted(str(x) for x in content.keys()))
        if isinstance(node, dict) and isinstance(node.get("schema"), dict):
            sch = flatten_schema(node["schema"])  # type: ignore[arg-type]
        out.append(
            ResponseDoc(
                status=str(status),
                description=str(desc).strip() if isinstance(desc, str) else "",
                content_media_types=mts,
                schema=sch,
            )
        )
    return tuple(out)


def _operation_security(op: dict[str, Any], spec: dict[str, Any]) -> tuple[tuple[str, ...], ...]:
    sec = op.get("security")
    if sec is None:
        sec = spec.get("security")
    if not isinstance(sec, list):
        return ()
    blocks: list[tuple[str, ...]] = []
    for block in sec:
        if not isinstance(block, dict):
            continue
        names = sorted(str(k) for k in block.keys())
        blocks.append(tuple(names))
    return tuple(blocks)


def _collect_link_operation_ids(responses: dict[str, Any] | None) -> frozenset[str]:
    if not isinstance(responses, dict):
        return frozenset()
    ids: set[str] = set()
    for status in sorted(responses.keys()):
        resp = responses[status]
        if not isinstance(resp, dict):
            continue
        links = resp.get("links")
        if not isinstance(links, dict):
            continue
        for lk in sorted(links.keys()):
            link = links[lk]
            if isinstance(link, dict):
                oid = link.get("operationId")
                if isinstance(oid, str) and oid.strip():
                    ids.add(oid.strip())
    return frozenset(sorted(ids))


def _request_body_parts(
    rb: dict[str, Any] | None,
    preferred_media: str,
) -> tuple[tuple[str, ...], dict[str, Any] | None]:
    if not isinstance(rb, dict):
        return (), None
    content = rb.get("content")
    media, node = _pick_media(content if isinstance(content, dict) else None, preferred_media)
    mts = tuple(sorted(str(x) for x in (content or {}).keys())) if isinstance(content, dict) else ()
    sch = None
    if isinstance(node, dict) and isinstance(node.get("schema"), dict):
        sch = flatten_schema(node["schema"])  # type: ignore[arg-type]
    return mts, sch


def build_endpoint_docs(spec: dict[str, Any], *, preferred_media_type: str) -> tuple[EndpointDoc, ...]:
    paths = spec.get("paths")
    if not isinstance(paths, dict):
        return ()
    preferred = preferred_media_type or "application/json"

    endpoints: list[EndpointDoc] = []
    for path in sorted(paths.keys()):
        path_item = paths[path]
        if not isinstance(path_item, dict):
            continue
        path_params = path_item.get("parameters")
        pp = path_params if isinstance(path_params, list) else []
        for method in sorted(path_item.keys()):
            if method.startswith("x-"):
                continue
            mlow = method.lower()
            if mlow not in {m.value for m in HttpMethod}:
                continue
            op = path_item[method]
            if not isinstance(op, dict):
                continue
            op_params = op.get("parameters")
            op_list = op_params if isinstance(op_params, list) else []
            merged_ps = _merge_parameters(pp, op_list)
            params = tuple(_param_doc(copy.deepcopy(p)) for p in merged_ps if isinstance(p, dict))
            rb = op.get("requestBody")
            mts, req_sch = _request_body_parts(rb if isinstance(rb, dict) else None, preferred)
            responses = op.get("responses")
            resp_docs = _responses_doc(responses if isinstance(responses, dict) else None, preferred)
            oid = op.get("operationId")
            operation_id = str(oid).strip() if isinstance(oid, str) and str(oid).strip() else f"{mlow}_{path}"
            summary = op.get("summary")
            desc = op.get("description")
            tags_raw = op.get("tags")
            tags: tuple[str, ...] = ()
            if isinstance(tags_raw, list):
                tags = tuple(str(t) for t in tags_raw if isinstance(t, str))
            sec_blocks = _operation_security(op, spec)
            req_refs = collect_schema_refs(req_sch) if req_sch else frozenset()
            resp_refs: set[str] = set()
            for r in resp_docs:
                if r.schema:
                    resp_refs.update(collect_schema_refs(r.schema))
            for pd in params:
                resp_refs.update(collect_schema_refs(pd.schema))
            link_ids = _collect_link_operation_ids(responses if isinstance(responses, dict) else None)

            method_enum = HttpMethod(mlow)
            crud = _crud_intent(method_enum)
            auth_kinds: tuple[AuthKind, ...] = ()
            tests: tuple[ApiTestCase, ...] = ()
            seq = ""
            ep = EndpointDoc(
                path=str(path),
                method=method_enum,
                operation_id=operation_id,
                summary=str(summary).strip() if isinstance(summary, str) else "",
                description=str(desc).strip() if isinstance(desc, str) else "",
                tags=tags,
                parameters=params,
                request_body_media_types=mts,
                request_schema=req_sch,
                responses=resp_docs,
                security=sec_blocks,
                crud_intent=crud,
                auth_kinds=auth_kinds,
                test_cases=tests,
                sequence_mermaid=seq,
                request_schema_refs=req_refs,
                response_schema_refs=frozenset(sorted(resp_refs)),
                link_operation_ids=link_ids,
            )
            endpoints.append(ep)

    return tuple(endpoints)
