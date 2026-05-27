import logging
import re
from typing import Any, Callable

from .feature_patterns import FEATURE_PATTERNS
from .feature_text_utils import build_search_text

logger = logging.getLogger(__name__)

FEATURE_OUTPUT_KEYS = [
    "has_legal_info",
    "legal_status_raw",
    "has_red_pink_book",
    "floor_count",
    "seller_type",
    "furniture_level",
    "frontage_width",
    "bathroom_count",
    "project_name",
    "bedroom_count",
    "is_business_suitable",
    "has_urban_area_flag",
    "has_security_flag",
    "has_educated_community_flag",
    "has_high_intellect_flag",
    "has_residential_area_flag",
    "has_subdivision_flag",
    "direction",
    "is_price_negotiable",
    "has_car_access",
    "car_access_type",
    "building_name",
]

PROPERTY_TYPE_SKIP_MAP = {
    "apartment": {"floor_count", "frontage_width", "car_access"},
    "land": {"floor_count", "bedroom_count"},
}


def _empty_result(value: Any = None) -> dict[str, Any]:
    return {key: value for key in FEATURE_OUTPUT_KEYS}


def _valid_int(value: str | int | None, minimum: int, maximum: int) -> int | None:
    if value is None:
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if minimum <= parsed <= maximum else None


def _valid_float(value: str | float | None, minimum: float, maximum: float) -> float | None:
    if value is None:
        return None
    try:
        parsed = float(str(value).replace(",", "."))
    except (TypeError, ValueError):
        return None
    return parsed if minimum <= parsed <= maximum else None


def _truncate_words(value: str, max_chars: int) -> str:
    value = re.sub(r"\s+", " ", value).strip()
    if len(value) <= max_chars:
        return value
    truncated = value[:max_chars].rsplit(" ", 1)[0].strip()
    return truncated or value[:max_chars].strip()


def _first_match(patterns: list[tuple[str, re.Pattern]], text: str) -> tuple[str, re.Match] | None:
    matches = []
    for name, pattern in patterns:
        match = pattern.search(text)
        if match:
            matches.append((match.start(), name, match))
    if not matches:
        return None
    _, name, match = sorted(matches, key=lambda item: item[0])[0]
    return name, match


def extract_legal_status(search_text: str) -> dict[str, Any]:
    patterns = FEATURE_PATTERNS["legal_status"]
    match = patterns["keywords"].search(search_text or "")
    has_red_pink_book = bool(patterns["red_pink_book"].search(search_text or ""))
    if not match:
        return {
            "has_legal_info": False,
            "legal_status_raw": None,
            "has_red_pink_book": False,
        }
    return {
        "has_legal_info": True,
        "legal_status_raw": match.group(1)[:100],
        "has_red_pink_book": has_red_pink_book,
    }


def extract_floor_count(search_text: str) -> int | None:
    patterns = FEATURE_PATTERNS["floor_count"]
    compound = patterns["tret_lau"].search(search_text or "")
    standard = patterns["standard"].search(search_text or "")

    candidates: list[tuple[int, int]] = []
    if compound:
        candidates.append((compound.start(), 1 + int(compound.group(1))))
    if standard:
        value = standard.group(1) or standard.group(2)
        candidates.append((standard.start(), int(value)))

    if not candidates:
        return None
    _, value = sorted(candidates, key=lambda item: item[0])[0]
    return _valid_int(value, 1, 50)


def extract_seller_type(search_text: str) -> str | None:
    text = search_text or ""
    patterns = FEATURE_PATTERNS["seller_type"]
    if patterns["owner_negation"].search(text):
        return "owner"
    if patterns["owner"].search(text):
        return "owner"
    if patterns["broker"].search(text):
        return "broker"
    return None


def extract_furniture_level(search_text: str) -> str | None:
    text = search_text or ""
    patterns = FEATURE_PATTERNS["furniture"]
    for level in ["full", "basic", "raw", "mentioned"]:
        if patterns[level].search(text):
            return level
    return None


def extract_frontage_width(search_text: str) -> float | None:
    matches = []
    for pattern in FEATURE_PATTERNS["frontage_width"]["patterns"]:
        match = pattern.search(search_text or "")
        if match:
            matches.append((match.start(), match.group(1)))
    if not matches:
        return None
    _, value = sorted(matches, key=lambda item: item[0])[0]
    return _valid_float(value, 1.0, 100.0)


def extract_bathroom_count(search_text: str) -> int | None:
    matches = []
    for pattern in FEATURE_PATTERNS["bathroom_count"]["patterns"]:
        match = pattern.search(search_text or "")
        if match:
            matches.append((match.start(), match.group(1)))
    if not matches:
        return None
    _, value = sorted(matches, key=lambda item: item[0])[0]
    return _valid_int(value, 1, 20)


def extract_project_name(raw_text: str) -> str | None:
    for pattern in FEATURE_PATTERNS["project_name"]["patterns"]:
        match = pattern.search(raw_text or "")
        if match:
            return _truncate_words(match.group(1), 100)
    return None


def extract_bedroom_count(search_text: str) -> int | None:
    matches = []
    for pattern in FEATURE_PATTERNS["bedroom_count"]["patterns"]:
        match = pattern.search(search_text or "")
        if match:
            matches.append((match.start(), match.group(1)))
    if not matches:
        return None
    _, value = sorted(matches, key=lambda item: item[0])[0]
    return _valid_int(value, 1, 30)


def extract_business_suitability(search_text: str) -> bool:
    return bool(FEATURE_PATTERNS["business"]["keywords"].search(search_text or ""))


def extract_location_context(search_text: str) -> dict[str, bool]:
    patterns = FEATURE_PATTERNS["location_context"]
    high_intellect = bool(patterns["educated"].search(search_text or ""))
    return {
        "has_urban_area_flag": bool(patterns["urban"].search(search_text or "")),
        "has_security_flag": bool(patterns["security"].search(search_text or "")),
        "has_educated_community_flag": high_intellect,
        "has_high_intellect_flag": high_intellect,
        "has_residential_area_flag": bool(patterns["residential"].search(search_text or "")),
        "has_subdivision_flag": bool(patterns["subdivision"].search(search_text or "")),
    }


def extract_direction(search_text: str) -> str | None:
    match = FEATURE_PATTERNS["direction"]["pattern"].search(search_text or "")
    if not match:
        return None

    direction = match.group(1).replace(" ", "_")
    aliases = {
        "dn": "dong_nam",
        "tb": "tay_bac",
        "db": "dong_bac",
        "tn": "tay_nam",
    }
    return aliases.get(direction, direction)


def extract_negotiable_price(search_text: str) -> bool:
    text = search_text or ""
    pattern = FEATURE_PATTERNS["negotiable_price"]["keywords"]
    negation = FEATURE_PATTERNS["negotiable_price"]["negation_window"]
    for match in pattern.finditer(text):
        prefix = text[: match.start()].split()
        window = " ".join(prefix[-3:]) + " " if prefix else ""
        if negation.search(window):
            continue
        return True
    return False


def extract_car_access(search_text: str) -> dict[str, Any]:
    patterns = FEATURE_PATTERNS["car_access"]
    match = _first_match(
        [
            ("car_can_enter", patterns["enter"]),
            ("car_can_park", patterns["park"]),
            ("car_can_pass", patterns["pass"]),
        ],
        search_text or "",
    )
    if not match:
        return {"has_car_access": False, "car_access_type": None}
    return {"has_car_access": True, "car_access_type": match[0]}


def extract_building_name(raw_text: str) -> str | None:
    match = FEATURE_PATTERNS["building_name"]["pattern"].search(raw_text or "")
    if not match:
        return None
    name = re.split(r",|\n|\r|\.\s", match.group(1), maxsplit=1)[0]
    return _truncate_words(name, 50)


def _run(feature_name: str, fn: Callable[[], Any], default: Any = None) -> Any:
    try:
        return fn()
    except Exception as exc:  # pragma: no cover - defensive pipeline isolation
        logger.warning("Extractor '%s' failed: %s", feature_name, exc)
        return default


def extract_features(listing_row: dict | None) -> dict[str, Any]:
    if not isinstance(listing_row, dict):
        return _empty_result()

    search_text, raw_text = build_search_text(listing_row)
    if not raw_text:
        return _empty_result()

    result = _empty_result()
    property_type_group = listing_row.get("property_type_group")
    skip_set = PROPERTY_TYPE_SKIP_MAP.get(property_type_group, set())

    legal = _run("legal_status", lambda: extract_legal_status(search_text), {})
    result.update(legal)

    result["seller_type"] = _run(
        "seller_type", lambda: extract_seller_type(search_text)
    ) or listing_row.get("seller_type")
    result["furniture_level"] = _run(
        "furniture_level", lambda: extract_furniture_level(search_text)
    )
    result["bathroom_count"] = listing_row.get("bathroom_count") or _run(
        "bathroom_count", lambda: extract_bathroom_count(search_text)
    )
    result["project_name"] = listing_row.get("project_raw") or _run(
        "project_name", lambda: extract_project_name(raw_text)
    )
    result["is_business_suitable"] = _run(
        "business_suitability", lambda: extract_business_suitability(search_text), False
    )

    location_context = _run("location_context", lambda: extract_location_context(search_text), {})
    result.update(location_context)

    result["direction"] = _run("direction", lambda: extract_direction(search_text))
    result["is_price_negotiable"] = _run(
        "negotiable_price", lambda: extract_negotiable_price(search_text), False
    )
    result["building_name"] = _run("building_name", lambda: extract_building_name(raw_text))

    if "floor_count" not in skip_set:
        result["floor_count"] = _run("floor_count", lambda: extract_floor_count(search_text))
    if "frontage_width" not in skip_set:
        result["frontage_width"] = _run(
            "frontage_width", lambda: extract_frontage_width(search_text)
        )
    if "bedroom_count" not in skip_set:
        result["bedroom_count"] = listing_row.get("bedroom_count") or _run(
            "bedroom_count", lambda: extract_bedroom_count(search_text)
        )
    if "car_access" not in skip_set:
        result.update(_run("car_access", lambda: extract_car_access(search_text), {}))

    return {key: result.get(key) for key in FEATURE_OUTPUT_KEYS}
