from __future__ import annotations

import pytest

from md_generator.openapi.parsers.openapi_parser import validate_openapi_version


def test_validate_openapi_version_accepts_3x() -> None:
    assert validate_openapi_version({"openapi": "3.0.3"}) == "3.0.3"


def test_validate_openapi_version_rejects_2x() -> None:
    with pytest.raises(ValueError, match="OpenAPI 3"):
        validate_openapi_version({"swagger": "2.0"})
