from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal


WaitUntil = Literal["load", "domcontentloaded", "commit", "networkidle"]


@dataclass
class PlaywrightOptions:
    """Configuration for SPA fetch → Markdown pipeline."""

    verbose: bool = False
    navigation_timeout_ms: float = 60_000.0
    user_agent: str = (
        "mdengine-playwright/0.1 (+https://github.com/vishal7090/md-generator)"
    )
    wait_selector: str | None = None
    wait_until: WaitUntil = "networkidle"
    max_scroll_rounds: int = 12
    scroll_pause_ms: float = 400.0
    max_retries: int = 3
    retry_backoff_seconds: float = 1.5
    headless: bool = True
    use_readability: bool = True
    chunk_markdown: bool = True
    max_chunk_tokens: int = 900
    chars_per_token: int = 4
    max_images: int = 40
    max_image_bytes: int = 5 * 1024 * 1024
    asset_timeout_seconds: float = 30.0
    screenshot_path: Path | None = None
    save_raw_html_path: Path | None = None
