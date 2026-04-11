"""Build ConvertOptions from HTTP query parameters."""

from __future__ import annotations

from typing import Literal, cast

from md_generator.image.api.settings import tesseract_cmd
from md_generator.image.convert_impl import ConvertOptions

_Strategy = Literal["compare", "best"]


def convert_options_from_query(
    *,
    engines: str = "tess,paddle,easy",
    strategy: str = "compare",
    title: str = "OCR extraction",
    lang: str = "eng",
    paddle_lang: str = "en",
    paddle_no_angle_cls: bool = False,
    easy_lang: str = "en",
) -> ConvertOptions:
    easy_langs = tuple(s.strip() for s in easy_lang.split(",") if s.strip())
    if not easy_langs:
        easy_langs = ("en",)
    eng = tuple(x.strip().lower() for x in engines.split(",") if x.strip())
    if not eng:
        raise ValueError("engines must list at least one of tess, paddle, easy")
    if strategy not in ("compare", "best"):
        raise ValueError("strategy must be compare or best")
    st: _Strategy = cast(_Strategy, strategy)
    return ConvertOptions(
        engines=eng,
        strategy=st,
        title=title,
        tess_lang=lang,
        tesseract_cmd=tesseract_cmd(),
        paddle_lang=paddle_lang,
        paddle_use_angle_cls=not paddle_no_angle_cls,
        easy_langs=easy_langs,
        verbose=False,
    )
