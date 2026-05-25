from __future__ import annotations

import json
from collections.abc import Iterable
from typing import Any
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from crawler.crawl_config import expand_targets, get_target_location_path


DEFAULT_BASE_URL = "https://www.nhatot.com"


def clean_text(value: object) -> str | None:
    if value is None:
        return None
    text = " ".join(str(value).split()).strip()
    return text or None


def extract_next_state(html: str) -> dict[str, Any] | None:
    soup = BeautifulSoup(html or "", "lxml")
    tag = soup.find("script", id="__NEXT_DATA__")
    if not tag:
        return None

    payload = tag.string or tag.get_text()
    if not payload:
        return None

    try:
        state = json.loads(payload)
    except json.JSONDecodeError:
        return None
    return state if isinstance(state, dict) else None


def _nested_get(payload: dict[str, Any], path: Iterable[str]) -> Any:
    current: Any = payload
    for key in path:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def extract_ads_from_state(state: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not state:
        return []

    candidate_paths = [
        ["props", "initialState", "adlisting", "data", "ads"],
        ["props", "pageProps", "initialState", "adlisting", "data", "ads"],
    ]
    for path in candidate_paths:
        ads = _nested_get(state, path)
        if isinstance(ads, list):
            return [ad for ad in ads if isinstance(ad, dict)]
    return []


def param_value(ad: dict[str, Any], param_id: str) -> str | None:
    for param in ad.get("params") or []:
        if isinstance(param, dict) and param.get("id") == param_id:
            return clean_text(param.get("value"))
    return None


def extract_listing_id(ad: dict[str, Any]) -> str | None:
    value = ad.get("list_id") or ad.get("ad_id") or ad.get("id")
    return str(value) if value is not None else None


def build_listing_url(ad: dict[str, Any], base_url: str = DEFAULT_BASE_URL) -> str | None:
    raw_url = clean_text(ad.get("listing_url") or ad.get("url") or ad.get("web_url"))
    if raw_url:
        return urljoin(base_url, raw_url)

    listing_id = extract_listing_id(ad)
    if not listing_id:
        return None

    category_slug = clean_text(ad.get("category_slug")) or "mua-ban-nha-dat"
    location_slug = (
        clean_text(ad.get("location_slug"))
        or clean_text(ad.get("district_slug"))
        or "viet-nam"
    )
    return f"{base_url.rstrip('/')}/{category_slug}-{location_slug}/{listing_id}.htm"


def _format_area(ad: dict[str, Any]) -> str | None:
    explicit = clean_text(ad.get("area_raw") or ad.get("size_unit_string"))
    if explicit:
        return explicit
    size = ad.get("size")
    return f"{size} m2" if size is not None else None


def _format_location(ad: dict[str, Any]) -> str | None:
    parts = [
        ad.get("ward_name"),
        ad.get("area_name") or ad.get("district_name"),
        ad.get("region_name") or ad.get("city_name"),
    ]
    return clean_text(", ".join(str(part) for part in parts if clean_text(part)))


def normalize_list_ad(ad: dict[str, Any], base_url: str = DEFAULT_BASE_URL) -> dict[str, Any]:
    return {
        "source": "nhatot",
        "source_code": "nhatot",
        "listing_id": extract_listing_id(ad),
        "listing_url": build_listing_url(ad, base_url=base_url),
        "listing_card_title": clean_text(ad.get("subject") or ad.get("title")),
        "listing_card_price_raw": clean_text(ad.get("price_string") or ad.get("price_raw")),
        "listing_card_area_raw": _format_area(ad),
        "listing_card_location_raw": _format_location(ad),
        "listing_card_description": clean_text(ad.get("body") or ad.get("description")),
        "property_type_group": clean_text(ad.get("property_type_group")),
        "city_raw": clean_text(ad.get("region_name") or ad.get("city_name")),
        "district_raw": clean_text(ad.get("area_name") or ad.get("district_name")),
        "ward_raw": clean_text(ad.get("ward_name")),
        "bedroom_count": ad.get("rooms"),
        "bathroom_count": ad.get("toilets"),
        "price_vnd": ad.get("price"),
        "area_m2": ad.get("size"),
    }


def _append_page_query(url: str, page_number: int) -> str:
    if page_number <= 1:
        return url
    separator = "&" if "?" in url else "?"
    return f"{url}{separator}page={page_number}"


def _iter_dicts(value: Any) -> Iterable[dict[str, Any]]:
    if isinstance(value, dict):
        yield value
        for nested in value.values():
            yield from _iter_dicts(nested)
    elif isinstance(value, list):
        for item in value:
            yield from _iter_dicts(item)


def _find_detail_ad(state: dict[str, Any] | None) -> dict[str, Any] | None:
    if not state:
        return None
    for candidate in _iter_dicts(state):
        if any(key in candidate for key in ["subject", "body", "detail_address"]):
            return candidate
    return None


class NhatotAdapter:
    source_code = "nhatot"

    def build_seed_urls(self, config: dict) -> list[str]:
        base_url = config.get("base_url") or DEFAULT_BASE_URL
        max_pages = config.get("crawl_settings", {}).get("max_pages_per_target", 1)
        urls: list[str] = []

        for target in expand_targets(config):
            seed_url = target.get("seed_url")
            if seed_url:
                target_url = str(seed_url)
            else:
                target_url = (
                    f"{base_url.rstrip('/')}/{target['category']}-"
                    f"{get_target_location_path(target)}"
                )

            urls.extend(_append_page_query(target_url, page_number) for page_number in range(1, max_pages + 1))

        return urls

    def parse_list_page(self, html: str) -> list[dict]:
        state = extract_next_state(html)
        return [normalize_list_ad(ad) for ad in extract_ads_from_state(state)]

    def parse_detail_page(self, html: str) -> dict:
        ad = _find_detail_ad(extract_next_state(html)) or {}
        title = clean_text(ad.get("subject") or ad.get("title"))
        address = clean_text(ad.get("detail_address") or ad.get("address"))
        city = clean_text(ad.get("region_name") or ad.get("city_name"))
        district = clean_text(ad.get("area_name") or ad.get("district_name"))
        ward = clean_text(ad.get("ward_name"))
        breadcrumb = " / ".join(part for part in [city, district, ward] if part) or None

        return {
            "detail_title": title,
            "detail_address_raw": address,
            "breadcrumb_raw": breadcrumb,
            "breadcrumb_location_raw": breadcrumb,
            "detail_description": clean_text(ad.get("body") or ad.get("description")),
        }
