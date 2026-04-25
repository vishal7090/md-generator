from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any


class HttpMethod(str, Enum):
    GET = "get"
    PUT = "put"
    POST = "post"
    DELETE = "delete"
    PATCH = "patch"
    HEAD = "head"
    OPTIONS = "options"
    TRACE = "trace"


class AuthKind(str, Enum):
    NONE = "none"
    API_KEY = "apiKey"
    HTTP_BEARER = "http_bearer"
    OAUTH2 = "oauth2"
    OPENID = "openIdConnect"
    MUTUAL_TLS = "mutualTLS"
    OTHER = "other"


@dataclass(frozen=True, slots=True)
class ParameterDoc:
    name: str
    in_: str
    required: bool
    schema: dict[str, Any]
    description: str = ""


@dataclass(frozen=True, slots=True)
class ResponseDoc:
    status: str
    description: str
    content_media_types: tuple[str, ...]
    schema: dict[str, Any] | None


@dataclass(frozen=True, slots=True)
class SecuritySchemeDoc:
    key: str
    type: str
    scheme: str | None
    bearer_format: str | None
    in_: str | None
    name: str | None
    flows_summary: str
    auth_kind: AuthKind


@dataclass(frozen=True, slots=True)
class ApiTestCase:
    name: str
    description: str
    body: dict[str, Any]


@dataclass(frozen=True, slots=True)
class FlatSchema:
    """Normalized JSON-schema-like dict for documentation (deterministic)."""

    data: dict[str, Any]


@dataclass(frozen=True, slots=True)
class EndpointDoc:
    path: str
    method: HttpMethod
    operation_id: str
    summary: str
    description: str
    tags: tuple[str, ...]
    parameters: tuple[ParameterDoc, ...]
    request_body_media_types: tuple[str, ...]
    request_schema: dict[str, Any] | None
    responses: tuple[ResponseDoc, ...]
    security: tuple[tuple[str, ...], ...]
    crud_intent: str
    auth_kinds: tuple[AuthKind, ...]
    test_cases: tuple[ApiTestCase, ...]
    sequence_mermaid: str
    request_schema_refs: frozenset[str]
    response_schema_refs: frozenset[str]
    link_operation_ids: frozenset[str]


@dataclass(frozen=True, slots=True)
class ApiSpecMeta:
    title: str
    version: str
    openapi_version: str
    servers: tuple[str, ...]
    security_schemes: dict[str, SecuritySchemeDoc]
    endpoints: tuple[EndpointDoc, ...]
    raw_spec_path: Path | None = None


HTTP_METHODS_LOWER = frozenset(m.value for m in HttpMethod)
