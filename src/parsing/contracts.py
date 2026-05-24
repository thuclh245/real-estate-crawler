"""Typed contracts for parsing and transformation stages."""

from __future__ import annotations

from typing import TypedDict

from common.schema import BronzeMetadata, QuarantineRecord, RunSummary, SilverRecord


BronzeListingMetadata = BronzeMetadata
SilverListingRecord = SilverRecord


class GoldListingRecord(TypedDict, total=False):
    source: str
    crawl_date: str
    snapshot_date: str
    dedup_key: str
    listing_id: str
    listing_url: str
    price_vnd: int | None
    area_m2: float | None
    parse_status: str | None


__all__ = [
    "BronzeListingMetadata",
    "GoldListingRecord",
    "QuarantineRecord",
    "RunSummary",
    "SilverListingRecord",
]
