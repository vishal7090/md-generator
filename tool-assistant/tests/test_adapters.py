from __future__ import annotations

import json

from md_generator.tools.assistant import MasterAgent, Registry
from md_generator.tools.assistant.adapters import (
    to_claude_project_prompt,
    to_cursor_rules_markdown,
    to_openai_messages,
)


def test_openai_messages_shape() -> None:
    agent = MasterAgent(Registry.load_default())
    res = agent.ask("How do I run md-pdf on a file?")
    msgs = to_openai_messages(res)
    assert isinstance(msgs, list)
    assert msgs[0]["role"] == "system"
    assert msgs[1]["role"] == "user"
    assert "md-pdf" in msgs[0]["content"] or "pdf" in msgs[0]["content"].lower()
    json.dumps(msgs)  # serializable


def test_claude_prompt_contains_skills() -> None:
    agent = MasterAgent(Registry.load_default())
    res = agent.ask("md-db and sqlalchemy")
    text = to_claude_project_prompt(res)
    assert "mdengine" in text.lower() or "sql" in text.lower()


def test_cursor_rules_markdown_frontmatter() -> None:
    agent = MasterAgent(Registry.load_default())
    res = agent.ask("playwright chromium install")
    md = to_cursor_rules_markdown(res)
    assert md.startswith("---")
    assert "Grounded context" in md
