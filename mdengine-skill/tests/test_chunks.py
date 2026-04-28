from __future__ import annotations

from tools.mdengine_skill.chunks import chunk_markdown, strip_yaml_frontmatter


def test_strip_frontmatter() -> None:
    raw = '---\nname: x\nversion: 1\n---\n\n# Body\n\nHello'
    assert strip_yaml_frontmatter(raw).startswith("# Body")


def test_chunk_headings() -> None:
    text = "# T\n\n## A\n\none\n\n## B\n\ntwo\n"
    chunks = chunk_markdown(text, "f.md")
    headings = {c.heading for c in chunks}
    assert "A" in headings
    assert "B" in headings
