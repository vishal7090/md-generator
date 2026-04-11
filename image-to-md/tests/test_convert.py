from __future__ import annotations

from pathlib import Path

import pytest

from PIL import Image

from src.convert_impl import ConvertOptions, convert_images


def _write_minimal_png(path: Path) -> None:
    Image.new("RGB", (2, 2), color=(10, 20, 30)).save(path, format="PNG")


class _FakeBackend:
    def __init__(self, name: str, text: str) -> None:
        self.name = name
        self._text = text

    def extract(self, image):
        return self._text


def test_convert_images_compare_uses_backends(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    img_dir = tmp_path / "in"
    img_dir.mkdir()
    _write_minimal_png(img_dir / "b.png")
    _write_minimal_png(img_dir / "a.png")

    monkeypatch.setattr(
        "src.convert_impl.build_backends",
        lambda _opts: [_FakeBackend("Tesseract", "tx"), _FakeBackend("EasyOCR", "ex")],
    )

    out_md = tmp_path / "out.md"
    convert_images(
        img_dir,
        out_md,
        ConvertOptions(
            engines=("tess", "easy"),
            strategy="compare",
            title="Doc",
            tess_lang="eng",
            tesseract_cmd=None,
            paddle_lang="en",
            paddle_use_angle_cls=True,
            easy_langs=("en",),
            verbose=False,
        ),
    )

    text = out_md.read_text(encoding="utf-8")
    assert "# Doc" in text
    # Sorted by filename: a.png then b.png
    assert text.index("a.png") < text.index("b.png")
    assert "### Tesseract" in text and "tx" in text
    assert "### EasyOCR" in text and "ex" in text


def test_convert_images_best_strategy(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    p = tmp_path / "one.png"
    _write_minimal_png(p)

    monkeypatch.setattr(
        "src.convert_impl.build_backends",
        lambda _opts: [
            _FakeBackend("Tesseract", "short"),
            _FakeBackend("EasyOCR", "much longer text"),
        ],
    )

    out_md = tmp_path / "best.md"
    convert_images(
        p,
        out_md,
        ConvertOptions(
            engines=("tess", "easy"),
            strategy="best",
            title="B",
            tess_lang="eng",
            tesseract_cmd=None,
            paddle_lang="en",
            paddle_use_angle_cls=True,
            easy_langs=("en",),
            verbose=False,
        ),
    )
    body = out_md.read_text(encoding="utf-8")
    assert "much longer text" in body
    assert "###" not in body


def test_iter_image_paths_empty_dir_errors(tmp_path: Path) -> None:
    empty = tmp_path / "e"
    empty.mkdir()
    with pytest.raises(ValueError, match="No supported images"):
        convert_images(
            empty,
            tmp_path / "o.md",
            ConvertOptions(
                engines=("tess",),
                strategy="best",
                title="T",
                tess_lang="eng",
                tesseract_cmd=None,
                paddle_lang="en",
                paddle_use_angle_cls=True,
                easy_langs=("en",),
                verbose=False,
            ),
        )


def test_io_util_rejects_non_image_file(tmp_path: Path) -> None:
    from src.io_util import iter_image_paths

    f = tmp_path / "x.txt"
    f.write_text("nope", encoding="utf-8")
    with pytest.raises(ValueError):
        iter_image_paths(f)
