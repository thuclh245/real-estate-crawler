from __future__ import annotations

from typing import Any

from common.utils import now_utc_iso
from parsing.normalizers import (
    calculate_total_price,
    calculate_unit_price,
    clean_text,
    normalize_area,
    normalize_price,
)


def _first_nonempty(*values: object) -> object | None:
    for value in values:
        if value is None:
            continue
        if isinstance(value, str) and not value.strip():
            continue
        return value
    return None


def _to_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_int(value: object) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _dedup_key(source: object, listing_id: object, listing_url: object) -> tuple[str | None, str | None]:
    source_code = clean_text(str(source or "nhatot")) or "nhatot"
    listing_id_text = clean_text(str(listing_id)) if listing_id is not None else None
    if listing_id_text:
        return f"{source_code}::{listing_id_text}", "listing_id"

    listing_url_text = clean_text(str(listing_url)) if listing_url is not None else None
    if listing_url_text:
        return f"{source_code}::{listing_url_text.split('?', 1)[0]}", "listing_url"

    return None, None


def parse_listing(
    raw_html: str,
    raw_text: str,
    metadata: dict[str, Any],
    parser_version: str = "phase2_v1",
) -> dict[str, Any]:
    source = metadata.get("source") or metadata.get("source_code") or "nhatot"
    listing_id = metadata.get("listing_id")
    listing_url = metadata.get("listing_url")
    title_raw = clean_text(_first_nonempty(metadata.get("title"), metadata.get("listing_card_title")))
    description_raw = clean_text(
        _first_nonempty(metadata.get("description"), metadata.get("listing_card_description"), raw_text[:3000] if raw_text else None)
    )

    price_raw = clean_text(metadata.get("listing_card_price_raw"))
    area_raw = clean_text(metadata.get("listing_card_area_raw"))
    price_info = normalize_price(price_raw)
    area_info = normalize_area(area_raw)

    price_vnd = _to_int(_first_nonempty(metadata.get("price_vnd"), price_info.get("price_vnd")))
    area_m2 = _to_float(_first_nonempty(metadata.get("area_m2"), area_info.get("area_m2")))
    price_unit = price_info.get("price_unit")
    total_price_vnd = calculate_total_price(price_vnd, area_m2, price_unit)
    unit_price_vnd_m2 = calculate_unit_price(price_vnd, area_m2, price_unit)

    location_raw = clean_text(
        _first_nonempty(
            metadata.get("detail_address_raw"),
            metadata.get("listing_card_location_raw"),
            metadata.get("breadcrumb_location_raw"),
            metadata.get("crawl_location_label"),
        )
    )
    city_raw = clean_text(_first_nonempty(metadata.get("city_raw"), metadata.get("crawl_city_label"), metadata.get("crawl_city")))
    district_raw = clean_text(
        _first_nonempty(
            metadata.get("district_raw"),
            metadata.get("crawl_district_label"),
            metadata.get("crawl_location_label"),
        )
    )
    ward_raw = clean_text(metadata.get("ward_raw"))
    city_norm = city_raw
    district_norm = district_raw
    ward_norm = ward_raw
    dedup_key, dedup_method = _dedup_key(source, listing_id, listing_url)

    return {
        "source": source,
        "source_code": metadata.get("source_code") or source,
        "crawl_date": metadata.get("crawl_date"),
        "crawl_id": metadata.get("crawl_id"),
        "listing_id": listing_id,
        "listing_url": listing_url,
        "dedup_key": dedup_key,
        "dedup_method": dedup_method,
        "title_raw": title_raw,
        "description_raw": description_raw,
        "price_raw": price_raw,
        "area_raw": area_raw,
        "location_raw": location_raw,
        "price_value": price_info.get("price_value"),
        "price_unit": price_unit,
        "price_vnd": total_price_vnd,
        "area_m2": area_m2,
        "unit_price_vnd_m2": unit_price_vnd_m2,
        "property_type_raw": metadata.get("crawl_category"),
        "property_type_group": metadata.get("property_type_group") or "unknown",
        "listing_business_type": metadata.get("listing_business_type"),
        "city_raw": city_raw,
        "district_raw": district_raw,
        "ward_raw": ward_raw,
        "street_raw": metadata.get("street_raw"),
        "project_raw": metadata.get("project_raw"),
        "city_norm": city_norm,
        "district_norm": district_norm,
        "ward_norm": ward_norm,
        "location_confidence": metadata.get("location_match_confidence") or "medium",
        "location_parse_method": metadata.get("location_match_method") or "metadata_field",
        "bedroom_count": _to_int(metadata.get("bedroom_count")),
        "bathroom_count": _to_int(metadata.get("bathroom_count")),
        "floor_count": _to_int(metadata.get("floor_count")),
        "seller_type": metadata.get("seller_type"),
        "seller_years_on_platform": metadata.get("seller_years_on_platform"),
        "seller_active_listing_count": metadata.get("seller_active_listing_count"),
        "has_broker_certificate": metadata.get("has_broker_certificate"),
        "phone_masked": metadata.get("phone_masked"),
        "image_count": metadata.get("image_count"),
        "has_image": metadata.get("has_image"),
        "posted_date_raw": metadata.get("posted_date_raw"),
        "expired_date_raw": metadata.get("expired_date_raw"),
        "posted_date": None,
        "expired_date": None,
        "parse_status": "success",
        "parse_error_message": None,
        "raw_html_path": metadata.get("raw_html_path"),
        "raw_text_path": metadata.get("raw_text_path"),
        "metadata_path": metadata.get("metadata_path"),
        "parser_version": parser_version,
        "processed_at": now_utc_iso(),
    }
