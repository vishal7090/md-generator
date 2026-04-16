from __future__ import annotations

import csv
import re
from pathlib import Path

from bs4 import BeautifulSoup
from markdownify import markdownify as html_to_markdown
from readability import Document


def readability_main_html(html: str, page_url: str) -> tuple[str, str | None]:
    """Return (summary_html, document_title) using readability-lxml."""
    doc = Document(html, url=page_url)
    title = doc.title()
    summary = doc.summary()
    return summary, (title.strip() if title else None)


def html_fragment_to_markdown(fragment_html: str) -> str:
    return html_to_markdown(
        fragment_html,
        heading_style="ATX",
        bullets="-",
        strip=["script", "style", "noscript"],
    ).strip()


def append_table_csv_sidecars(
    summary_html: str,
    tables_dir: Path,
    *,
    filename_prefix: str,
    link_prefix: str = "assets/tables",
) -> str:
    """Write each <table> to CSV; return Markdown appendix with links."""
    soup = BeautifulSoup(summary_html, "lxml")
    tables = soup.find_all("table")
    if not tables:
        return ""

    tables_dir.mkdir(parents=True, exist_ok=True)
    lines: list[str] = ["", "## Tables (CSV)", ""]
    for idx, table in enumerate(tables, start=1):
        rows: list[list[str]] = []
        for tr in table.find_all("tr"):
            cells = tr.find_all(["th", "td"])
            if not cells:
                continue
            rows.append([re.sub(r"\s+", " ", c.get_text(strip=True)) for c in cells])
        if not rows:
            continue
        name = f"{filename_prefix}_table_{idx}.csv"
        path = tables_dir / name
        max_cols = max(len(r) for r in rows)
        norm = [r + [""] * (max_cols - len(r)) for r in rows]
        with path.open("w", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            w.writerows(norm)
        lp = link_prefix.strip("/")
        rel = f"{lp}/{name}" if lp else name
        lines.append(f"- [{name}]({rel})")
    lines.append("")
    return "\n".join(lines) if len(lines) > 2 else ""
