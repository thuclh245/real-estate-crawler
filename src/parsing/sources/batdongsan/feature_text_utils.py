import math
import re
import unicodedata
from typing import Any

TEXT_FIELDS = [
    "title_raw",
    "description_raw",
    "location_raw",
    "property_type_raw",
    "project_raw",
]


def _is_blank(value: Any) -> bool:
    if value is None:
        return True

    if isinstance(value, float) and math.isnan(value):
        return True

    text = str(value)
    return not text.strip()


def normalize_text(text: str | None) -> str:
    if text is None:
        return ""

    value = str(text).lower()
    value = unicodedata.normalize("NFD", value)
    value = "".join(char for char in value if unicodedata.category(char) != "Mn")
    value = value.replace("đ", "d").replace("Đ", "d")
    value = value.replace("²", "2").replace("³", "3").replace("㎡", "m2").replace("㎥", "m3")
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def build_search_text(listing_row: dict | None) -> tuple[str, str]:
    if not isinstance(listing_row, dict):
        return "", ""

    parts = []
    for field in TEXT_FIELDS:
        value = listing_row.get(field)
        if not _is_blank(value):
            parts.append(str(value).strip())

    raw_text = " ".join(parts)
    return normalize_text(raw_text), raw_text
