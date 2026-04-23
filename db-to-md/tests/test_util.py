from md_generator.db.core.util import redact_uri


def test_redact_uri_password() -> None:
    u = redact_uri("postgresql://user:secret@localhost:5432/mydb")
    assert "***" in u
    assert "secret" not in u
