from __future__ import annotations

from md_generator.tools.assistant.registry import Registry


def test_load_registry_schema() -> None:
    reg = Registry.load_default()
    assert reg.raw.get("schemaVersion") == "1.1.0"
    routing = reg.raw.get("routing") or {}
    assert "keywordRouting" in routing
    assert "mdengine-ai-pdf" in routing.get("moduleSkillId", {}).values()


def test_skill_path_exists() -> None:
    reg = Registry.load_default()
    p = reg.skill_path("mdengine-ai-pdf")
    assert p is not None
    assert p.is_file()
