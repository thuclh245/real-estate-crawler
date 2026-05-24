"""Typed contracts for parsing and transformation stages."""

from __future__ import annotations

from typing import TypedDict


class BronzeListingMetadata(TypedDict, total=False):
    source: str
    crawl_date: str
    crawl_id: str
    listing_id: str
    listing_url: str
    crawl_category: str
    property_type_group: str
    crawl_city_label: str
    crawl_city: str
    crawl_district_label: str
    crawl_district: str
    seller_type: str
    seller_years_on_platform: int | float | str
    seller_active_listing_count: int | float | str
    has_broker_certificate: bool
    phone_masked: str
    image_count: int | float | str
    has_image: bool
    posted_date_raw: str
    expired_date_raw: str
    raw_html_path: str
    raw_text_path: str
    metadata_path: str


class SilverListingRecord(TypedDict, total=False):
    source: str
    crawl_date: str
    crawl_id: str
    listing_id: str
    listing_url: str
    title_raw: str | None
    description_raw: str | None
    price_raw: str | None
    area_raw: str | None
    location_raw: str | None
    price_value: float | int | None
    price_unit: str | None
    price_vnd: int | None
    area_m2: float | None
    unit_price_vnd_m2: float | None
    property_type_raw: str | None
    property_type_group: str | None
    listing_business_type: str | None
    city_raw: str | None
    district_raw: str | None
    ward_raw: str | None
    street_raw: str | None
    project_raw: str | None
    city_norm: str | None
    district_norm: str | None
    ward_norm: str | None
    location_confidence: str | None
    location_parse_method: str | None
    bedroom_count: int | None
    bathroom_count: int | None
    floor_count: int | None
    seller_type: str | None
    seller_years_on_platform: int | float | str | None
    seller_active_listing_count: int | float | str | None
    has_broker_certificate: bool | None
    phone_masked: str | None
    image_count: int | float | str | None
    has_image: bool | None
    posted_date_raw: str | None
    expired_date_raw: str | None
    posted_date: str | None
    expired_date: str | None
    parse_status: str | None
    parse_error_message: str | None
    raw_html_path: str | None
    raw_text_path: str | None
    metadata_path: str | None
    parser_version: str | None
    processed_at: str | None


class GoldListingRecord(TypedDict, total=False):
    """Minimal Gold contract for downstream aggregation tables."""

    source: str
    crawl_date: str
    snapshot_date: str
    dedup_key: str
    listing_id: str
    listing_url: str
    price_vnd: int | None
    area_m2: float | None
    parse_status: str | None
