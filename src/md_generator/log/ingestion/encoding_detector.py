from __future__ import annotations

from md_generator.log.core.errors import EncodingError


def decode_lines(
    raw: bytes,
    fallbacks: list[str],
) -> str:
    for enc in fallbacks:
        try:
            return raw.decode(enc)
        except (UnicodeDecodeError, LookupError):
            continue
    raise EncodingError(f"Could not decode with encodings: {fallbacks}")
