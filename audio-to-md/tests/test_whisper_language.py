from __future__ import annotations

import pytest


@pytest.mark.parametrize(
    ("inp", "exp_lang", "has_prompt", "exp_profile"),
    [
        (None, None, False, None),
        ("", None, False, None),
        ("auto", None, False, None),
        ("en", "en", False, None),
        ("english", "en", False, None),
        ("hi", "hi", False, None),
        ("hindi", "hi", False, None),
        ("hi,en", None, True, "hi+en (mixed, auto-detect)"),
        ("en hi", None, True, "hi+en (mixed, auto-detect)"),
        ("hinglish", None, True, "Hindi+English (Hinglish)"),
        ("Hindi and English mix", None, True, "hi+en (mixed, auto-detect)"),
        ("xyztypo", None, False, "xyztypo"),
        ("fr,de", None, True, "fr+de (mixed, auto-detect)"),
    ],
)
def test_resolve_whisper_language(
    inp: str | None,
    exp_lang: str | None,
    has_prompt: bool,
    exp_profile: str | None,
) -> None:
    pytest.importorskip("whisper")
    from md_generator.media.whisper_language import resolve_whisper_language

    lang, prompt, profile = resolve_whisper_language(inp)
    assert lang == exp_lang
    assert (prompt is not None) == has_prompt
    assert profile == exp_profile
