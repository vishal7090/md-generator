"""Regression: PyMySQL INFORMATION_SCHEMA columns are often UPPERCASE in cursor metadata."""

from md_generator.db.adapters.mysql_adapter import _row_dict_lower


def test_row_dict_lower_maps_uppercase_information_schema_columns() -> None:
    row = {"TABLE_NAME": "v1", "VIEW_DEFINITION": "select 1 as x"}
    d = _row_dict_lower(row)
    assert d["table_name"] == "v1"
    assert d["view_definition"] == "select 1 as x"


def test_row_dict_lower_maps_routine_columns() -> None:
    row = {
        "ROUTINE_NAME": "fn_x",
        "EXTERNAL_LANGUAGE": "SQL",
        "ROUTINE_DEFINITION": "RETURN 1",
    }
    d = _row_dict_lower(row)
    assert d["routine_name"] == "fn_x"
    assert d["external_language"] == "SQL"
    assert d["routine_definition"] == "RETURN 1"
