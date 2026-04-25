from __future__ import annotations

from md_generator.openapi.generators.dependency_graph import build_dependency_edges, render_dependency_mermaid
from md_generator.openapi.models.domain import ApiTestCase, AuthKind, EndpointDoc, HttpMethod


def _ep(
    oid: str,
    path: str,
    method: HttpMethod = HttpMethod.GET,
    req_refs: frozenset[str] | None = None,
    resp_refs: frozenset[str] | None = None,
    links: frozenset[str] | None = None,
) -> EndpointDoc:
    return EndpointDoc(
        path=path,
        method=method,
        operation_id=oid,
        summary="",
        description="",
        tags=(),
        parameters=(),
        request_body_media_types=(),
        request_schema=None,
        responses=(),
        security=(),
        crud_intent="read",
        auth_kinds=(AuthKind.NONE,),
        test_cases=(ApiTestCase(name="x", description="", body={}),),
        sequence_mermaid="sequenceDiagram\n",
        request_schema_refs=req_refs or frozenset(),
        response_schema_refs=resp_refs or frozenset(),
        link_operation_ids=links or frozenset(),
    )


def test_dependency_edges_from_shared_schema_refs() -> None:
    a = _ep("listPets", "/pets", HttpMethod.GET, resp_refs=frozenset(["#/components/schemas/Pet"]))
    b = _ep("createPet", "/pets", HttpMethod.POST, req_refs=frozenset(["#/components/schemas/Pet"]))
    edges = build_dependency_edges((a, b))
    assert ("listPets", "createPet") in edges


def test_render_dependency_mermaid_stable() -> None:
    a = _ep("a", "/a")
    b = _ep("b", "/b")
    text = render_dependency_mermaid((b, a))
    assert "graph LR" in text
    assert "N0" in text and "N1" in text
