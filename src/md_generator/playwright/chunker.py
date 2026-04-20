from __future__ import annotations


def chunk_markdown(
    md: str,
    *,
    max_tokens: int = 900,
    overlap_chars: int = 0,
    chars_per_token: int = 4,
) -> str:
    """
    Split Markdown into ~max_tokens chunks using a simple chars-per-token estimate.
    Inserts <!-- chunk:start id=N --> ... <!-- chunk:end --> markers.
    """
    _ = overlap_chars  # reserved for future overlap between chunks
    max_chars = max(200, max_tokens * max(1, chars_per_token))
    text = md.strip()
    if not text:
        return md

    paragraphs = text.split("\n\n")
    chunks: list[str] = []
    buf: list[str] = []
    buf_len = 0

    def flush() -> None:
        nonlocal buf, buf_len
        if not buf:
            return
        block = "\n\n".join(buf).strip()
        if block:
            chunks.append(block)
        buf = []
        buf_len = 0

    for para in paragraphs:
        plen = len(para) + (2 if buf else 0)
        if buf_len + plen > max_chars and buf:
            flush()
        buf.append(para)
        buf_len += plen
        if buf_len >= max_chars:
            flush()

    flush()

    if len(chunks) <= 1:
        return md

    parts: list[str] = []
    for i, c in enumerate(chunks, start=1):
        parts.append(f"<!-- chunk:start id={i} -->\n\n{c}\n\n<!-- chunk:end -->\n")
    return "\n".join(parts).rstrip() + "\n"
