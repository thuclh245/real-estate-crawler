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
