from __future__ import annotations

import json
import re
import unicodedata
from collections.abc import Iterable
from typing import Any
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from crawler.crawl_config import expand_targets, get_target_location_path


DEFAULT_BASE_URL = "https://www.nhatot.com"

# Global in-memory cache for polymorphic API-to-web seamless integration
IN_MEMORY_AD_CACHE: dict[str, str] = {}

# Exact harvested mappings for Hà Nội districts to Chợ Tốt API area IDs
DISTRICT_MAPPING = {
    "quan-ba-dinh": 74,
    "quan-bac-tu-liem": 129,
    "quan-cau-giay": 79,
    "quan-dong-da": 75,
    "quan-ha-dong": 86,
    "quan-hai-ba-trung": 76,
    "quan-hoan-kiem": 73,
    "quan-hoang-mai": 80,
    "quan-long-bien": 81,
    "quan-nam-tu-liem": 121,
    "quan-tay-ho": 78,
    "quan-thanh-xuan": 77
}

# Mapping of targets to category IDs
CATEGORY_MAPPING = {
    "mua-ban-can-ho-chung-cu": 1010,
    "mua-ban-nha-dat": 1020
}

CATEGORY_SLUG_BY_ID = {value: key for key, value in CATEGORY_MAPPING.items()}


def clean_text(value: object) -> str | None:
    if value is None:
        return None
    text = " ".join(str(value).split()).strip()
    return text or None


def slugify_vi(value: object) -> str | None:
    text = clean_text(value)
    if not text:
        return None
    text = unicodedata.normalize("NFD", text)
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    text = text.replace("đ", "d").replace("Đ", "D")
    text = re.sub(r"[^A-Za-z0-9]+", "-", text).strip("-").lower()
    return text or None


def infer_category_slug(ad: dict[str, Any]) -> str:
    category_slug = clean_text(ad.get("category_slug"))
    if category_slug:
        return category_slug
    category_id = ad.get("category")
    if category_id is not None:
        try:
            return CATEGORY_SLUG_BY_ID.get(int(category_id), "mua-ban-nha-dat")
        except (TypeError, ValueError):
            return "mua-ban-nha-dat"
    return "mua-ban-nha-dat"


def infer_location_slug(ad: dict[str, Any]) -> str:
    location_slug = clean_text(ad.get("location_slug"))
    if location_slug:
        return location_slug
    parts = [
        slugify_vi(ad.get("area_name") or ad.get("district_name")),
        slugify_vi(ad.get("region_name") or ad.get("city_name")),
    ]
    inferred = "-".join(part for part in parts if part)
    return inferred or "viet-nam"


def transaction_param(target: dict[str, Any]) -> str | None:
    business_type = str(target.get("business_type") or "").lower()
    category = str(target.get("category") or "").lower()
    if business_type == "sale" or category.startswith("mua-ban"):
        return "s"
    if business_type in {"rent", "lease"} or category.startswith("cho-thue"):
        return "u"
    return None


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
    value = ad.get("ad_id") or ad.get("id") or ad.get("list_id")
    return str(value) if value is not None else None


def extract_public_listing_id(ad: dict[str, Any]) -> str | None:
    value = ad.get("list_id") or ad.get("ad_id") or ad.get("id")
    return str(value) if value is not None else None


def build_listing_url(ad: dict[str, Any], base_url: str = DEFAULT_BASE_URL) -> str | None:
    raw_url = clean_text(ad.get("listing_url") or ad.get("url") or ad.get("web_url"))
    if raw_url:
        return urljoin(base_url, raw_url)

    listing_id = extract_public_listing_id(ad)
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
        max_pages = config.get("crawl_settings", {}).get("max_pages_per_target", 1)
        urls: list[str] = []

        for target in expand_targets(config):
            category_slug = target.get("category")
            location_slug = target.get("location_slug")

            cg_id = CATEGORY_MAPPING.get(category_slug)
            area_id = DISTRICT_MAPPING.get(location_slug)

            # If both are matched in our API schema, generate high-performance API Seed URLs
            if cg_id and area_id:
                for page_number in range(1, max_pages + 1):
                    st = transaction_param(target)
                    transaction_query = f"&st={st}" if st else ""
                    api_url = (
                        f"https://gateway.chotot.com/v1/public/ad-listing"
                        f"?cg={cg_id}&region=12&area={area_id}&o={(page_number - 1) * 20}&limit=20"
                        f"{transaction_query}"
                    )
                    urls.append(api_url)
            else:
                # Fallback to old NextJS Web Scraping Page URL format (backward compatibility)
                base_url = config.get("base_url") or DEFAULT_BASE_URL
                seed_url = target.get("seed_url")
                if seed_url:
                    target_url = str(seed_url)
                else:
                    target_url = (
                        f"{base_url.rstrip('/')}/{target['category']}-"
                        f"{get_target_location_path(target)}"
                    )

                urls.extend(
                    _append_page_query(target_url, page_number)
                    for page_number in range(1, max_pages + 1)
                )

        return urls

    def parse_list_page(self, html: str) -> list[dict]:
        stripped = (html or "").strip()
        
        # Polymorphic check: If the response is Chợ Tốt API JSON
        if stripped.startswith("{") or stripped.startswith("["):
            try:
                data = json.loads(stripped)
                ads = data.get("ads", [])
                normalized_ads = []

                for ad in ads:
                    listing_id = extract_listing_id(ad)
                    if listing_id is None:
                        continue
                    category_slug = infer_category_slug(ad)
                    location_slug = infer_location_slug(ad)
                    public_listing_id = extract_public_listing_id(ad) or listing_id

                    # Generate the real public Web URL. Chotot/Nhatot API exposes
                    # both ad_id and list_id; public web detail URLs use list_id.
                    web_url = (
                        f"https://www.nhatot.com/{category_slug}-{location_slug}/"
                        f"{public_listing_id}.htm"
                    )

                    # Store the complete ad dictionary in our global cache, keying by the real web URL!
                    IN_MEMORY_AD_CACHE[web_url] = json.dumps(ad)

                    parts = [ad.get("ward_name"), ad.get("area_name"), ad.get("region_name")]
                    location_raw = ", ".join(str(part) for part in parts if part)

                    normalized = {
                        "source": "nhatot",
                        "source_code": "nhatot",
                        "listing_id": str(listing_id),
                        "listing_url": web_url,  # Point orchestrator to web URL (which intercepts standard fetch)
                        "listing_card_title": clean_text(ad.get("subject")),
                        "listing_card_price_raw": clean_text(ad.get("price_string")),
                        "listing_card_area_raw": f"{ad.get('size')} m2" if ad.get('size') else None,
                        "listing_card_location_raw": clean_text(location_raw),
                        "listing_card_description": clean_text(ad.get("body")),
                        "property_type_group": clean_text(ad.get("property_type_group")),
                        "city_raw": clean_text(ad.get("region_name")),
                        "district_raw": clean_text(ad.get("area_name")),
                        "ward_raw": clean_text(ad.get("ward_name")),
                        "bedroom_count": ad.get("rooms"),
                        "bathroom_count": ad.get("toilets"),
                        "price_vnd": ad.get("price"),
                        "area_m2": ad.get("size"),
                    }
                    normalized_ads.append(normalized)
                return normalized_ads
            except Exception as e:
                print(f"[NhatotAdapter] Failed to parse API JSON response: {e}")
                return []

        # Fallback to old NextJS HTML State parser
        state = extract_next_state(html)
        return [normalize_list_ad(ad) for ad in extract_ads_from_state(state)]

    def parse_detail_page(self, html: str) -> dict:
        stripped = (html or "").strip()

        # Polymorphic check: If the response is Chợ Tốt API JSON from our cache intercept
        if stripped.startswith("{") or stripped.startswith("["):
            try:
                ad = json.loads(stripped)
                title = clean_text(ad.get("subject"))
                address = clean_text(ad.get("detail_address") or ad.get("street_name"))
                city = clean_text(ad.get("region_name"))
                district = clean_text(ad.get("area_name"))
                ward = clean_text(ad.get("ward_name"))
                breadcrumb = " / ".join(part for part in [city, district, ward] if part) or None
                full_address = clean_text(
                    ", ".join(part for part in [address, ward, district, city] if part)
                )

                return {
                    "detail_title": title,
                    "detail_address_raw": full_address or address,
                    "breadcrumb_raw": breadcrumb,
                    "breadcrumb_location_raw": breadcrumb,
                    "detail_description": clean_text(ad.get("body")),
                }
            except Exception as e:
                print(f"[NhatotAdapter] Failed to parse API JSON detail: {e}")
                return {}

        # Fallback to Web HTML parser
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
