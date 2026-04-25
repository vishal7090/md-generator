from __future__ import annotations

import copy
import json
import re
from typing import Any


def is_swagger2_document(doc: dict[str, Any]) -> bool:
    v = doc.get("swagger")
    return isinstance(v, str) and v.strip().startswith("2.")


def _rewrite_ref_strings(obj: Any) -> None:
    """In-place: #/definitions -> #/components/schemas, #/parameters -> #/components/parameters, #/responses -> #/components/responses."""
    repl = (
        ("#/definitions/", "#/components/schemas/"),
        ("#/parameters/", "#/components/parameters/"),
        ("#/responses/", "#/components/responses/"),
    )
    if isinstance(obj, dict):
        ref = obj.get("$ref")
        if isinstance(ref, str):
            for old, new in repl:
                if ref.startswith(old):
                    obj["$ref"] = new + ref[len(old) :]
                    break
        for v in obj.values():
            _rewrite_ref_strings(v)
    elif isinstance(obj, list):
        for it in obj:
            _rewrite_ref_strings(it)


def _normalize_oas3_schema_nodes(obj: Any) -> None:
    """In-place OAS3 schema normalization for validator compatibility."""
    if isinstance(obj, dict):
        # Swagger 2 discriminator uses a plain string; OAS3 requires an object with propertyName.
        disc = obj.get("discriminator")
        if isinstance(disc, str):
            obj["discriminator"] = {"propertyName": disc}
        for v in obj.values():
            _normalize_oas3_schema_nodes(v)
    elif isinstance(obj, list):
        for it in obj:
            _normalize_oas3_schema_nodes(it)


def _swagger_param_to_oas3_param(p: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k in ("name", "in", "description", "required", "deprecated", "allowEmptyValue"):
        if k in p:
            out[k] = p[k]
    if "schema" in p and isinstance(p["schema"], dict):
        out["schema"] = copy.deepcopy(p["schema"])
    elif "type" in p:
        sch: dict[str, Any] = {"type": p.get("type")}
        if "format" in p:
            sch["format"] = p["format"]
        if "enum" in p:
            sch["enum"] = copy.deepcopy(p["enum"])
        if p.get("type") == "array" and "items" in p:
            sch["items"] = copy.deepcopy(p["items"])
        out["schema"] = sch
    return out


def _implicit_path_parameters(path_key: str) -> list[dict[str, Any]]:
    """Swagger 2 often omits explicit ``{param}`` declarations; OpenAPI 3 requires them."""
    return [
        {"name": name, "in": "path", "required": True, "schema": {"type": "string"}}
        for name in re.findall(r"\{([^}]+)\}", path_key)
    ]


def _resolve_parameter_ref(p: dict[str, Any], param_defs: dict[str, Any]) -> dict[str, Any]:
    ref = p.get("$ref")
    if isinstance(ref, str) and ref.startswith("#/parameters/"):
        key = ref.split("/")[-1]
        base = param_defs.get(key)
        if isinstance(base, dict):
            return copy.deepcopy(base)
    return copy.deepcopy(p)


def _swagger_response_to_oas3(resp: dict[str, Any], default_produces: list[str]) -> dict[str, Any]:
    if not isinstance(resp, dict):
        return {"description": ""}
    # OpenAPI 3 requires ``description`` on every Response object (may be empty).
    out: dict[str, Any] = {"description": str(resp.get("description") or "")}
    headers = resp.get("headers")
    if isinstance(headers, dict) and headers:
        out["headers"] = {str(k): _swagger_header_to_oas3_header(v) for k, v in headers.items()}
    schema = resp.get("schema")
    if schema is not None:
        mt = default_produces[0] if default_produces else "application/json"
        out["content"] = {mt: {"schema": copy.deepcopy(schema)}}
    return out


def _swagger_header_to_oas3_header(h: Any) -> dict[str, Any]:
    if not isinstance(h, dict):
        return {"schema": {"type": "string"}}
    out: dict[str, Any] = {}
    if isinstance(h.get("description"), str):
        out["description"] = h["description"]
    if "schema" in h and isinstance(h["schema"], dict):
        out["schema"] = copy.deepcopy(h["schema"])
        return out
    sch: dict[str, Any] = {}
    if isinstance(h.get("type"), str):
        sch["type"] = h["type"]
    if isinstance(h.get("format"), str):
        sch["format"] = h["format"]
    if isinstance(h.get("items"), dict):
        sch["items"] = copy.deepcopy(h["items"])
    if isinstance(h.get("enum"), list):
        sch["enum"] = copy.deepcopy(h["enum"])
    out["schema"] = sch or {"type": "string"}
    return out


def _merge_parameters(path_params: list[Any], op_params: list[Any], param_defs: dict[str, Any]) -> list[dict[str, Any]]:
    def key(p: dict[str, Any]) -> tuple[str, str]:
        return (str(p.get("name") or ""), str(p.get("in") or ""))

    merged: dict[tuple[str, str], dict[str, Any]] = {}
    for p in path_params:
        if isinstance(p, dict):
            rp = _resolve_parameter_ref(p, param_defs)
            merged[key(rp)] = rp
    for p in op_params:
        if isinstance(p, dict):
            rp = _resolve_parameter_ref(p, param_defs)
            merged[key(rp)] = rp
    return [merged[k] for k in sorted(merged.keys())]


def _convert_responses_block(responses: dict[str, Any] | None, produces: list[str]) -> dict[str, Any]:
    if not isinstance(responses, dict):
        return {}
    out: dict[str, Any] = {}
    for status in sorted(responses.keys(), key=lambda s: str(s)):
        sk = str(status)
        node = responses[status]
        if isinstance(node, dict) and isinstance(node.get("$ref"), str):
            out[sk] = {"$ref": node["$ref"].replace("#/responses/", "#/components/responses/")}
            continue
        if isinstance(node, dict):
            out[sk] = _swagger_response_to_oas3(node, produces)
        else:
            out[sk] = {"description": ""}
    return out


def _resolve_swagger_body_schema(schema: Any, definitions: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(schema, dict):
        return {}
    ref = schema.get("$ref")
    if isinstance(ref, str) and ref.startswith("#/definitions/"):
        name = ref.split("/")[-1]
        d = definitions.get(name)
        return copy.deepcopy(d) if isinstance(d, dict) else {}
    return copy.deepcopy(schema)


def _formdata_param_to_property(p: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    name = str(p.get("name") or "field")
    typ = p.get("type")
    desc = p.get("description")
    if typ == "file":
        prop: dict[str, Any] = {"type": "string", "format": "binary"}
    elif typ == "array":
        prop = {"type": "array", "items": copy.deepcopy(p.get("items") or {"type": "string"})}
    elif isinstance(typ, str):
        prop = {"type": typ}
    else:
        prop = {"type": "string"}
    if isinstance(desc, str) and desc.strip():
        prop["description"] = desc.strip()
    return name, prop


def _consumes_has_multipart(consumes: list[str]) -> bool:
    return any(isinstance(c, str) and "multipart/form-data" in c.lower() for c in consumes)


def _convert_operation(
    op: dict[str, Any],
    merged_params: list[dict[str, Any]],
    consumes: list[str],
    produces: list[str],
    definitions: dict[str, Any],
) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k in ("summary", "description", "operationId", "tags", "deprecated"):
        if k in op:
            out[k] = copy.deepcopy(op[k])
    if "security" in op:
        out["security"] = copy.deepcopy(op["security"])
    body_params = [p for p in merged_params if str(p.get("in") or "") == "body"]
    form_params = [p for p in merged_params if str(p.get("in") or "") == "formData"]
    other_params = [p for p in merged_params if str(p.get("in") or "") not in ("body", "formData")]
    if other_params:
        out["parameters"] = [_swagger_param_to_oas3_param(p) for p in other_params]

    use_multipart = bool(form_params) or (_consumes_has_multipart(consumes) and bool(body_params))

    if body_params or form_params:
        if use_multipart:
            mt = "multipart/form-data"
            props: dict[str, Any] = {}
            required_names: list[str] = []
            if body_params:
                body = body_params[0]
                sch = _resolve_swagger_body_schema(body.get("schema"), definitions)
                if isinstance(sch, dict) and sch.get("type") == "object" and isinstance(sch.get("properties"), dict):
                    props.update(copy.deepcopy(sch["properties"]))
                    for r in sch.get("required") or []:
                        if isinstance(r, str):
                            required_names.append(r)
                elif sch:
                    props["payload"] = sch
            for fp in form_params:
                n, prop = _formdata_param_to_property(fp)
                props[n] = prop
                if fp.get("required"):
                    required_names.append(n)
            obj_schema: dict[str, Any] = {"type": "object", "properties": props}
            if required_names:
                obj_schema["required"] = sorted(set(required_names))
            rb_required = (
                bool(body_params and body_params[0].get("required"))
                or any(bool(fp.get("required")) for fp in form_params)
                or bool(obj_schema.get("required"))
            )
            out["requestBody"] = {"required": rb_required, "content": {mt: {"schema": obj_schema}}}
        elif body_params:
            body = body_params[0]
            req = bool(body.get("required"))
            schema = body.get("schema")
            if schema is None:
                schema = {}
            content: dict[str, Any] = {}
            for mt in consumes:
                content[mt] = {"schema": copy.deepcopy(schema) if isinstance(schema, dict) else schema}
            if not content:
                content["application/json"] = {"schema": copy.deepcopy(schema) if isinstance(schema, dict) else schema}
            out["requestBody"] = {"required": req, "content": content}
    out["responses"] = _convert_responses_block(op.get("responses") or {}, produces)
    return out


def _build_servers(doc: dict[str, Any]) -> list[dict[str, str]]:
    schemes = doc.get("schemes") or ["https"]
    if not isinstance(schemes, list) or not schemes:
        schemes = ["https"]
    schemes = [str(s).lower() for s in schemes if isinstance(s, str)]
    if not schemes:
        schemes = ["https"]
    host = str(doc.get("host") or "localhost")
    base_path = str(doc.get("basePath") or "/")
    if not base_path.startswith("/"):
        base_path = "/" + base_path
    servers: list[dict[str, str]] = []
    for sch in sorted(set(schemes)):
        url = f"{sch}://{host.rstrip('/')}{base_path}"
        if url.endswith("//"):
            url = url[:-1]
        servers.append({"url": url})
    return servers


def _convert_security_definitions(sd: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    if not isinstance(sd, dict):
        return out
    for name in sorted(sd.keys()):
        scheme = sd[name]
        if not isinstance(scheme, dict):
            continue
        typ = scheme.get("type")
        if typ == "basic":
            out[name] = {"type": "http", "scheme": "basic"}
        elif typ == "apiKey":
            out[name] = {
                "type": "apiKey",
                "in": scheme.get("in"),
                "name": scheme.get("name"),
            }
        elif typ == "oauth2":
            flow_raw = str(scheme.get("flow") or "implicit")
            flow = flow_raw.lower().replace(" ", "_")
            scopes = copy.deepcopy(scheme.get("scopes") or {})
            flows: dict[str, Any] = {}
            if flow in ("accesscode", "access_code"):
                flows["authorizationCode"] = {
                    "authorizationUrl": str(scheme.get("authorizationUrl") or ""),
                    "tokenUrl": str(scheme.get("tokenUrl") or ""),
                    "scopes": scopes,
                }
            elif flow == "password":
                flows["password"] = {
                    "tokenUrl": str(scheme.get("tokenUrl") or ""),
                    "scopes": scopes,
                }
            elif flow == "application":
                flows["clientCredentials"] = {
                    "tokenUrl": str(scheme.get("tokenUrl") or ""),
                    "scopes": scopes,
                }
            else:
                flows["implicit"] = {
                    "authorizationUrl": str(scheme.get("authorizationUrl") or ""),
                    "scopes": scopes,
                }
            out[name] = {"type": "oauth2", "flows": flows}
        else:
            out[name] = copy.deepcopy(scheme)
    return out


def _convert_top_parameters(params: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    if not isinstance(params, dict):
        return out
    for k in sorted(params.keys()):
        v = params[k]
        if isinstance(v, dict):
            out[str(k)] = _swagger_param_to_oas3_param(v)
    return out


def _convert_top_responses(responses: dict[str, Any], default_produces: list[str]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    if not isinstance(responses, dict):
        return out
    for k in sorted(responses.keys()):
        v = responses[k]
        if isinstance(v, dict):
            out[str(k)] = _swagger_response_to_oas3(v, default_produces)
    return out


def convert_swagger2_to_openapi3(doc: dict[str, Any]) -> dict[str, Any]:
    """Convert a Swagger 2.0 document dict to OpenAPI 3.0.3 (best-effort, deterministic)."""
    if not is_swagger2_document(doc):
        raise ValueError("Document is not Swagger 2.x")

    global_consumes = doc.get("consumes")
    if not isinstance(global_consumes, list) or not global_consumes:
        global_consumes = ["application/json"]
    global_produces = doc.get("produces")
    if not isinstance(global_produces, list) or not global_produces:
        global_produces = ["application/json"]

    param_defs = doc.get("parameters") if isinstance(doc.get("parameters"), dict) else {}
    response_defs = doc.get("responses") if isinstance(doc.get("responses"), dict) else {}

    components: dict[str, Any] = {}
    if isinstance(doc.get("definitions"), dict):
        components["schemas"] = copy.deepcopy(doc["definitions"])
    if param_defs:
        components["parameters"] = _convert_top_parameters(param_defs)
    if response_defs:
        components["responses"] = _convert_top_responses(response_defs, global_produces)
    sd = doc.get("securityDefinitions")
    if isinstance(sd, dict) and sd:
        components["securitySchemes"] = _convert_security_definitions(sd)

    definitions_for_convert: dict[str, Any] = doc["definitions"] if isinstance(doc.get("definitions"), dict) else {}

    paths_out: dict[str, Any] = {}
    paths = doc.get("paths")
    if isinstance(paths, dict):
        for path_key in sorted(paths.keys()):
            path_item = paths[path_key]
            if not isinstance(path_item, dict):
                continue
            path_consumes = path_item.get("consumes") or global_consumes
            path_produces = path_item.get("produces") or global_produces
            if not isinstance(path_consumes, list) or not path_consumes:
                path_consumes = global_consumes
            if not isinstance(path_produces, list) or not path_produces:
                path_produces = global_produces
            path_level_params = path_item.get("parameters") or []
            if not isinstance(path_level_params, list):
                path_level_params = []
            out_item: dict[str, Any] = {}
            for xk, xv in path_item.items():
                if xk.startswith("x-"):
                    out_item[xk] = copy.deepcopy(xv)
            if path_level_params:
                non_body = [p for p in path_level_params if isinstance(p, dict) and str(p.get("in")) != "body"]
                if non_body:
                    out_item["parameters"] = [
                        _swagger_param_to_oas3_param(_resolve_parameter_ref(p, param_defs)) for p in non_body
                    ]
            for method in sorted(path_item.keys()):
                mlow = method.lower()
                if method.startswith("x-") or method == "parameters":
                    continue
                if mlow not in ("get", "put", "post", "delete", "options", "head", "patch"):
                    continue
                op = path_item[method]
                if not isinstance(op, dict):
                    continue
                op_consumes = op.get("consumes") or path_consumes
                op_produces = op.get("produces") or path_produces
                if not isinstance(op_consumes, list) or not op_consumes:
                    op_consumes = path_consumes
                if not isinstance(op_produces, list) or not op_produces:
                    op_produces = path_produces
                implicit_path = _implicit_path_parameters(path_key)
                merged = _merge_parameters(
                    implicit_path + path_level_params,
                    op.get("parameters") or [],
                    param_defs,
                )
                out_item[mlow] = _convert_operation(
                    op,
                    merged,
                    op_consumes,
                    op_produces,
                    definitions_for_convert,
                )
            paths_out[path_key] = out_item

    out_doc: dict[str, Any] = {
        "openapi": "3.0.3",
        "info": copy.deepcopy(doc.get("info") or {}),
        "paths": paths_out,
    }
    if components:
        out_doc["components"] = components
    out_doc["servers"] = _build_servers(doc)
    if isinstance(doc.get("tags"), list):
        out_doc["tags"] = copy.deepcopy(doc["tags"])
    if doc.get("security") is not None:
        out_doc["security"] = copy.deepcopy(doc["security"])
    for k, v in doc.items():
        if k.startswith("x-") and k not in out_doc:
            out_doc[k] = copy.deepcopy(v)

    _rewrite_ref_strings(out_doc)
    _normalize_oas3_schema_nodes(out_doc)
    return out_doc


def converted_document_to_json_bytes(doc: dict[str, Any]) -> bytes:
    """Serialize for a temp file consumed by Prance (UTF-8 JSON)."""
    text = json.dumps(doc, indent=2, sort_keys=True, ensure_ascii=False)
    return text.encode("utf-8")
