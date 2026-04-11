from __future__ import annotations

import sys
from pathlib import Path

import pytest
from PIL import Image

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.convert_impl import ConvertOptions, convert_images_recursive
from src.io_util import iter_image_paths_recursive


def test_iter_image_paths_recursive_finds_nested(tmp_path: Path) -> None:
    nested = tmp_path / "a" / "b"
    nested.mkdir(parents=True)
    Image.new("RGB", (1, 1), 0).save(nested / "deep.png")
    paths = iter_image_paths_recursive(tmp_path)
    assert len(paths) == 1
    assert paths[0].name == "deep.png"


def test_convert_images_recursive_nested_dir(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    nested = tmp_path / "x" / "y"
    nested.mkdir(parents=True)
    Image.new("RGB", (2, 2), 1).save(nested / "z.png")

    class _B:
        name = "Tesseract"

        def extract(self, image):
            return "ok"

    monkeypatch.setattr("src.convert_impl.build_backends", lambda _o: [_B()])
    out = tmp_path / "out.md"
    convert_images_recursive(
        tmp_path,
        out,
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
    assert "ok" in out.read_text(encoding="utf-8")
