from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import PurePosixPath

from md_generator.db.core.markdown_writer import slugify_segment


def _relpath_md(from_rel: str, to_rel: str) -> str:
    a = PurePosixPath(from_rel).parent
    b = PurePosixPath(to_rel)
    ups = 0
    from_parts = a.parts
    to_parts = b.parts
    common = 0
    for x, y in zip(from_parts, to_parts):
        if x != y:
            break
        common += 1
    ups = [".."] * (len(from_parts) - common)
    return "/".join(ups + list(to_parts[common:]))


@dataclass
class LinkGraph:
    """Maps logical object keys to relative Markdown paths for cross-linking."""

    _paths: dict[tuple[str, str, str], str] = field(default_factory=dict)

    def register(self, kind: str, schema: str, name: str, rel_path: str) -> None:
        self._paths[(kind, schema or "", name)] = rel_path.replace("\\", "/")

    def path_for_table(self, schema: str, name: str) -> str | None:
        return self._paths.get(("table", schema or "", name))

    def path_for_view(self, schema: str, name: str) -> str | None:
        return self._paths.get(("view", schema or "", name))

    def path_for_routine(self, kind: str, schema: str, name: str) -> str | None:
        k = "procedure" if kind.upper() == "PROCEDURE" else "function"
        return self._paths.get((k, schema or "", name))

    def table_rel_path(self, schema: str, name: str) -> str:
        slug = slugify_segment(f"{schema}_{name}" if schema else name)
        return f"tables/{slug}.md"

    def view_rel_path(self, schema: str, name: str) -> str:
        title = f"{schema}.{name}" if schema else name
        return f"views/{slugify_segment(title)}.md"

    def procedure_rel_path(self, schema: str, name: str) -> str:
        title = f"{schema}.{name}" if schema else name
        return f"procedures/{slugify_segment(title)}.md"

    def function_rel_path(self, schema: str, name: str) -> str:
        title = f"{schema}.{name}" if schema else name
        return f"functions/{slugify_segment(title)}.md"

    def related_links_for_fk(
        self,
        from_rel: str,
        referred_schema: str | None,
        referred_table: str,
    ) -> list[tuple[str, str]]:
        target = self.path_for_table(referred_schema or "", referred_table)
        if not target:
            return []
        label = f"{referred_schema}.{referred_table}" if referred_schema else referred_table
        return [(label, _relpath_md(from_rel, target))]
