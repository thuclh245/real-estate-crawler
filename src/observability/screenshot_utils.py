"""Utilities for dashboard screenshot storage."""

from __future__ import annotations

import re
from pathlib import Path


def generate_screenshot_filename(tab_name: str, date_str: str) -> str:
    """Generate a normalized screenshot filename for a dashboard tab."""
    normalized_tab_name = re.sub(r"[^a-z0-9]+", "_", tab_name.lower()).strip("_")
    if not normalized_tab_name:
        normalized_tab_name = "dashboard"
    return f"{normalized_tab_name}_{date_str}.png"


def ensure_screenshot_dir(base_path: Path | str = Path("docs/screenshots")) -> Path:
    """Create and return the screenshot directory."""
    screenshot_dir = Path(base_path)
    screenshot_dir.mkdir(parents=True, exist_ok=True)
    return screenshot_dir
