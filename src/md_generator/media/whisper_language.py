"""Map user-facing ``language`` strings to Whisper ``language`` / ``initial_prompt`` kwargs."""

from __future__ import annotations

import re
from typing import Final

# Whisper is single-language per ``language=``; for Hindi+English mixes we auto-detect and bias with a prompt.
_BILINGUAL_HI_EN_PROMPT: Final[str] = (
    "This audio may contain both Hindi and English (including code-switching). "
    "Transcribe Hindi in Devanagari where appropriate and English in the Latin alphabet."
)


def _token_to_whisper_code(tok: str, *, languages: dict, to_code: dict) -> str | None:
    t = tok.strip().lower()
    if not t:
        return None
    if t in languages:
        return t
    return to_code.get(t)


def resolve_whisper_language(language: str | None) -> tuple[str | None, str | None, str | None]:
    """
    Return ``(whisper_language, initial_prompt, language_profile)`` for ``model.transcribe``.

    * ``whisper_language`` — passed as ``language=`` when a single supported code is chosen.
    * ``initial_prompt`` — passed as ``initial_prompt=`` for mixed Hindi/English (or multi-code) hints.
    * ``language_profile`` — short label for Markdown metadata (e.g. ``hi+en (mixed)``).

    When ``language`` is omitted or blank, Whisper uses **automatic language detection** (same as
    passing ``auto`` / ``detect`` / ``none`` / ``multilingual``). Pass a single code (e.g. ``en``)
    to force that language.
    """
    if language is None:
        return None, None, None
    raw = str(language).strip()
    if not raw:
        return None, None, None

    lower = raw.lower()
    if lower in ("auto", "detect", "none", "multilingual"):
        return None, None, None

    if "hinglish" in lower.replace(" ", ""):
        return None, _BILINGUAL_HI_EN_PROMPT, "Hindi+English (Hinglish)"

    from whisper.tokenizer import LANGUAGES, TO_LANGUAGE_CODE

    parts = [p for p in re.split(r"[,+/|;]+|\s+", raw) if p.strip()]
    if not parts:
        parts = [raw]

    codes: list[str] = []
    for p in parts:
        code = _token_to_whisper_code(p, languages=LANGUAGES, to_code=TO_LANGUAGE_CODE)
        if code and code not in codes:
            codes.append(code)

    if len(codes) >= 2:
        if set(codes) == {"hi", "en"}:
            return None, _BILINGUAL_HI_EN_PROMPT, "hi+en (mixed, auto-detect)"
        langs = ", ".join(codes)
        prompt = (
            f"This audio may contain multiple spoken languages including: {langs}. "
            "Use each language's usual writing system where appropriate."
        )
        return None, prompt, "+".join(codes) + " (mixed, auto-detect)"

    if len(codes) == 1:
        return codes[0], None, None

    # One segment that did not map (e.g. typo): try whole string once, else auto-detect
    fallback = _token_to_whisper_code(raw, languages=LANGUAGES, to_code=TO_LANGUAGE_CODE)
    if fallback:
        return fallback, None, fallback
    return None, None, raw
