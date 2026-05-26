from __future__ import annotations

from typing import Any

from parsing.sources.batdongsan.silver_parser import parse_listing as parse_batdongsan_listing
from parsing.sources.nhatot.silver_parser import parse_listing as parse_nhatot_listing


def parse_listing(
    raw_html: str,
    raw_text: str,
    metadata: dict[str, Any],
    parser_version: str = "phase2_v1",
) -> dict[str, Any]:
    source = str(metadata.get("source_code") or metadata.get("source") or "").lower().strip()
    if source == "nhatot":
        return parse_nhatot_listing(
            raw_html=raw_html,
            raw_text=raw_text,
            metadata=metadata,
            parser_version=parser_version,
        )
    return parse_batdongsan_listing(
        raw_html=raw_html,
        raw_text=raw_text,
        metadata=metadata,
        parser_version=parser_version,
    )
