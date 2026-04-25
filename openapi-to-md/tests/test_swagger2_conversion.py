from __future__ import annotations

from pathlib import Path

from md_generator.openapi.converters.swagger2_to_openapi3 import convert_swagger2_to_openapi3, is_swagger2_document
from md_generator.openapi.core.extractor import extract_to_markdown
from md_generator.openapi.core.run_config import ApiRunConfig

_FIXTURE = Path(__file__).resolve().parent / "fixtures" / "swagger2_minimal.yaml"


def test_is_swagger2() -> None:
    import yaml

    doc = yaml.safe_load(_FIXTURE.read_text(encoding="utf-8"))
    assert is_swagger2_document(doc) is True


def test_convert_produces_openapi3_with_servers_and_paths() -> None:
    import yaml

    doc = yaml.safe_load(_FIXTURE.read_text(encoding="utf-8"))
    out = convert_swagger2_to_openapi3(doc)
    assert out["openapi"] == "3.0.3"
    assert out["paths"]["/users"]["get"]["responses"]["200"]["content"]["application/json"]["schema"]["type"] == "array"
    assert "components" in out and "User" in out["components"]["schemas"]
    assert out["servers"] and "api.example.com" in out["servers"][0]["url"]


def test_convert_normalizes_discriminator_and_response_headers() -> None:
    doc = {
        "swagger": "2.0",
        "info": {"title": "T", "version": "1"},
        "paths": {
            "/pets": {
                "post": {
                    "parameters": [
                        {
                            "in": "body",
                            "name": "body",
                            "required": True,
                            "schema": {"$ref": "#/definitions/Pet"},
                        }
                    ],
                    "responses": {
                        201: {
                            "description": "Created",
                            "headers": {"X-Trace": {"type": "string", "description": "trace id"}},
                        }
                    },
                }
            }
        },
        "definitions": {
            "Pet": {
                "type": "object",
                "discriminator": "petType",
                "properties": {"petType": {"type": "string"}},
                "required": ["petType"],
            }
        },
    }
    out = convert_swagger2_to_openapi3(doc)
    pet = out["components"]["schemas"]["Pet"]
    assert pet["discriminator"] == {"propertyName": "petType"}
    hdr = out["paths"]["/pets"]["post"]["responses"]["201"]["headers"]["X-Trace"]
    assert hdr["schema"]["type"] == "string"
    assert hdr["description"] == "trace id"


def test_extract_end_to_end_swagger2_fixture(tmp_path: Path) -> None:
    cfg = ApiRunConfig(file=_FIXTURE, output_path=tmp_path, formats=("md",))
    meta = extract_to_markdown(cfg)
    assert meta.title == "Sample API"
    assert (tmp_path / "README.md").is_file()
    assert (tmp_path / "endpoints" / "get__users.md").is_file()


def test_extract_openapi3_normalizes_numeric_keys_and_invalid_path_params(tmp_path: Path) -> None:
    spec = tmp_path / "bad_openapi.yaml"
    spec.write_text(
        "\n".join(
            [
                "openapi: 3.0.3",
                "info:",
                "  title: Test",
                "  version: '1.0.0'",
                "paths:",
                "  /resource:",
                "    post:",
                "      operationId: createResource",
                "      parameters:",
                "        - $ref: '#/components/parameters/resourceId'",
                "      responses:",
                "        201:",
                "          $ref: '#/components/responses/201'",
                "components:",
                "  parameters:",
                "    resourceId:",
                "      name: id",
                "      in: path",
                "      required: true",
                "      schema:",
                "        type: string",
                "  responses:",
                "    201:",
                "      description: Created",
            ]
        ),
        encoding="utf-8",
    )
    out = tmp_path / "out"
    cfg = ApiRunConfig(file=spec, output_path=out, formats=("md",))
    meta = extract_to_markdown(cfg)
    assert meta.title == "Test"
    assert (out / "README.md").is_file()
