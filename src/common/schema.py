"""Minimal data contracts for Stage 3 transform and reporting layers.

These contracts are intentionally lightweight: TypedDicts only, no validation
runtime dependency, and no forced rewrite of existing parser outputs.
"""

from __future__ import annotations

from typing import TypedDict


class BronzeMetadata(TypedDict, total=False):
    schema_version: str
    source: str
    run_id: str
    crawl_date: str
    crawl_id: str
    listing_id: str
    listing_url: str
    crawl_category: str
    property_type_group: str
    raw_html_path: str
    raw_text_path: str
    metadata_path: str


class SilverRecord(TypedDict, total=False):
    schema_version: str
    source: str
    crawl_date: str
    crawl_id: str
    run_id: str
    listing_id: str
    listing_url: str
    title_raw: str | None
    description_raw: str | None
    price_raw: str | None
    area_raw: str | None
    location_raw: str | None
    price_vnd: int | None
    area_m2: float | None
    parse_status: str | None
    parse_error_message: str | None
    processed_at: str | None
    # --- NLP / Regex extracted features (from extract_features()) ---
    has_legal_info: bool | None
    legal_status_raw: str | None
    has_red_pink_book: bool | None
    floor_count: int | None
    seller_type: str | None
    furniture_level: str | None
    frontage_width: float | None
    bathroom_count: int | None
    project_name: str | None
    bedroom_count: int | None
    is_business_suitable: bool | None
    has_urban_area_flag: bool | None
    has_security_flag: bool | None
    has_educated_community_flag: bool | None
    has_high_intellect_flag: bool | None
    has_residential_area_flag: bool | None
    has_subdivision_flag: bool | None
    direction: str | None
    is_price_negotiable: bool | None
    has_car_access: bool | None
    car_access_type: str | None
    building_name: str | None


class RunSummary(TypedDict, total=False):
    schema_version: str
    run_id: str
    source: str | None
    crawl_date: str | None
    crawl_id: str | None
    total_records: int
    success_count: int
    failure_count: int
    quarantine_count: int
    processed_at: str


class QuarantineRecord(TypedDict, total=False):
    schema_version: str
    quarantine_id: str
    run_id: str
    source: str
    crawl_date: str
    crawl_id: str | None
    rejection_stage: str
    rejection_reason: str
    error_message: str | None
    input_path: str | None
    record_identity: str | None
    parser_version: str | None
    captured_at: str
    raw_reference_path: str | None
    extra: dict[str, object] | None


SCHEMA_VERSION = "v1"
