from __future__ import annotations

import pytest

from md_generator.tools.assistant import MasterAgent, Registry


@pytest.mark.integration
def test_ask_with_rag_when_chromadb_works() -> None:
    try:
        import chromadb  # noqa: F401
    except Exception as exc:  # pragma: no cover - env-specific
        pytest.skip(f"chromadb not usable: {exc}")
    agent = MasterAgent(Registry.load_default())
    res = agent.ask("md-pdf pymupdf flags", use_rag=True)
    assert res.context_markdown
    assert isinstance(res.rag_used, bool)
