from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
sys.path.insert(0, str(SRC_ROOT))

from crawler.detail_page_parser import parse_detail_page_location_fields  # noqa: E402
from crawler.list_page_parser import (
    extract_listing_entries_from_listing_page,
)  # noqa: E402
from crawler.crawl_audit import (  # noqa: E402
    audit_location,
    classify_category_match,
    safe_rate,
    write_audit_sample_csv,
)
from crawler.parser import html_to_text  # noqa: E402
from common.storage import save_json_file  # noqa: E402

BRONZE_SOURCE_ROOT = REPO_ROOT / "data" / "bronze" / "source=batdongsan"
DEBUG_LIST_ROOT = REPO_ROOT / "data" / "debug" / "list_pages"


def find_crawl_root(crawl_id: str) -> Path:
    matches = list(BRONZE_SOURCE_ROOT.glob(f"crawl_date=*/crawl_id={crawl_id}"))
    if not matches:
        raise FileNotFoundError(
            f"Cannot find Bronze crawl root for crawl_id={crawl_id}"
        )
    if len(matches) > 1:
        raise RuntimeError(
            f"Multiple crawl roots found for crawl_id={crawl_id}: {matches}"
        )
    return matches[0]


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict]:
    records = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def write_jsonl(path: Path, records: list[dict]):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")


def build_listing_card_map(crawl_id: str) -> dict[str, dict]:
    debug_root = DEBUG_LIST_ROOT / f"crawl_id={crawl_id}"
    listing_cards = {}
    if not debug_root.exists():
        return listing_cards

    for html_path in sorted(debug_root.glob("*.html")):
        html = html_path.read_text(encoding="utf-8", errors="ignore")
        for entry in extract_listing_entries_from_listing_page(html):
            listing_cards.setdefault(entry["listing_url"], entry)
    return listing_cards


def build_seed_audits(crawl_root: Path) -> list[dict]:
    seed_audits = {}
    for debug_json_path in sorted(
        (
            DEBUG_LIST_ROOT / f"crawl_id={crawl_root.name.removeprefix('crawl_id=')}"
        ).glob("*.json")
    ):
        record = load_json(debug_json_path)
        page_url = record.get("page_url")
        if not page_url:
            continue
        seed_audits.setdefault(
            page_url,
            {
                "seed_url": page_url,
                "final_url": record.get("final_url") or page_url,
                "target_location_path": record.get("target_location_path"),
                "target_location_label": record.get("target_location_label"),
                "target_category": record.get("target_category"),
                "http_status": record.get("http_status"),
                "is_seed_url_valid": record.get("is_seed_url_valid"),
            },
        )
    return list(seed_audits.values())


def update_raw_json(raw_json_path: Path, metadata: dict):
    raw_json = load_json(raw_json_path) if raw_json_path.exists() else {}
    extracted = raw_json.get("extracted", {})
    raw_json.update(metadata)
    raw_json["extracted"] = extracted
    save_json_file(raw_json_path, raw_json)


def backfill_crawl(crawl_id: str) -> dict:
    crawl_root = find_crawl_root(crawl_id)
    metadata_dir = crawl_root / "metadata"
    crawl_log_dir = crawl_root / "crawl_log"
    summary_path = crawl_log_dir / f"crawl_summary_{crawl_id}.json"
    crawl_log_path = crawl_log_dir / f"crawl_log_{crawl_id}.jsonl"

    summary = load_json(summary_path)
    listing_cards = build_listing_card_map(crawl_id)
    metadata_paths = sorted(metadata_dir.glob("listing_id=*.json"))
    metadata_records = [load_json(path) for path in metadata_paths]
    known_location_labels = sorted(
        {
            record.get("crawl_location_label") or record.get("crawl_district_label")
            for record in metadata_records
            if record.get("crawl_location_label") or record.get("crawl_district_label")
        }
    )

    detail_audits = []
    audit_samples = []
    updated_by_listing_id = {}

    for metadata_path in metadata_paths:
        metadata = load_json(metadata_path)
        listing_url = metadata["listing_url"]
        listing_card = listing_cards.get(listing_url, {})

        raw_html_path = REPO_ROOT / metadata["raw_html_path"]
        detail_html = raw_html_path.read_text(encoding="utf-8", errors="ignore")
        detail_text = html_to_text(detail_html)
        detail_fields = parse_detail_page_location_fields(detail_html)

        title = (
            detail_fields.get("detail_title")
            or listing_card.get("listing_card_title")
            or metadata.get("title")
        )
        description = (
            detail_fields.get("detail_description")
            or listing_card.get("listing_card_description")
            or metadata.get("description")
        )
        target = {
            "location_label": metadata.get("crawl_location_label")
            or metadata.get("crawl_district_label"),
            "location_slug": metadata.get("crawl_location_slug")
            or metadata.get("crawl_district"),
            "location_path": metadata.get("crawl_location_path")
            or metadata.get("crawl_district"),
            "district_label": metadata.get("crawl_district_label"),
            "district": metadata.get("crawl_district"),
        }
        location_audit = audit_location(
            {
                **listing_card,
                **detail_fields,
                "listing_url": listing_url,
                "final_detail_url": metadata.get("final_detail_url") or listing_url,
                "is_seed_url_valid": metadata.get("is_seed_url_valid"),
                "title": title,
                "description": description,
            },
            target,
            known_location_labels=known_location_labels,
        )
        category_match_status, category_match_confidence = classify_category_match(
            detail_text,
            metadata.get("crawl_category") or "",
        )

        updates = {
            "title": title,
            "description": description,
            "listing_card_title": listing_card.get("listing_card_title"),
            "listing_card_price_raw": listing_card.get("listing_card_price_raw"),
            "listing_card_area_raw": listing_card.get("listing_card_area_raw"),
            "listing_card_location_raw": listing_card.get("listing_card_location_raw"),
            "listing_card_old_district_raw": listing_card.get(
                "listing_card_old_district_raw"
            ),
            "breadcrumb_raw": detail_fields.get("breadcrumb_raw"),
            "breadcrumb_location_raw": detail_fields.get("breadcrumb_location_raw"),
            "detail_location_raw": location_audit.get("detail_location_raw"),
            "detail_address_raw": detail_fields.get("detail_address_raw"),
            "location_evidence_text": location_audit.get("location_evidence_text"),
            "location_evidence_source": location_audit.get("location_evidence_source"),
            "location_match_status": location_audit["location_match_status"],
            "location_match_confidence": location_audit["location_match_confidence"],
            "location_match_method": location_audit["location_match_method"],
            "category_match_status": category_match_status,
            "category_match_confidence": category_match_confidence,
        }
        metadata.update(updates)

        raw_json_path = REPO_ROOT / metadata["raw_json_path"]
        save_json_file(metadata_path, metadata)
        update_raw_json(raw_json_path, metadata)
        updated_by_listing_id[metadata["listing_id"]] = metadata

        detail_audit = {
            "listing_id": metadata["listing_id"],
            "listing_url": listing_url,
            "source_seed_url": metadata.get("source_seed_url")
            or metadata.get("crawl_seed_url"),
            "final_seed_url": metadata.get("final_seed_url"),
            "is_seed_url_valid": metadata.get("is_seed_url_valid"),
            "crawl_category": metadata.get("crawl_category"),
            "crawl_location_path": metadata.get("crawl_location_path"),
            "crawl_location_label": metadata.get("crawl_location_label"),
            "listing_card_location_raw": metadata.get("listing_card_location_raw"),
            "listing_card_old_district_raw": metadata.get(
                "listing_card_old_district_raw"
            ),
            "detail_address_raw": metadata.get("detail_address_raw"),
            "breadcrumb_location_raw": metadata.get("breadcrumb_location_raw"),
            "detail_location_raw": metadata.get("detail_location_raw"),
            "location_evidence_text": metadata.get("location_evidence_text"),
            "location_evidence_source": metadata.get("location_evidence_source"),
            "location_match_status": metadata.get("location_match_status"),
            "location_match_confidence": metadata.get("location_match_confidence"),
            "location_match_method": metadata.get("location_match_method"),
            "category_match_status": metadata.get("category_match_status"),
            "category_match_confidence": metadata.get("category_match_confidence"),
        }
        detail_audits.append(detail_audit)

        if len(audit_samples) < 20:
            audit_samples.append(
                {
                    **detail_audit,
                    "title": metadata.get("title"),
                    "price_raw": metadata.get("listing_card_price_raw"),
                    "area_raw": metadata.get("listing_card_area_raw"),
                }
            )

    if crawl_log_path.exists():
        log_records = load_jsonl(crawl_log_path)
        for record in log_records:
            if record.get("type") != "detail_page":
                continue
            listing_id = record.get("listing_id")
            if listing_id in updated_by_listing_id:
                record.update(updated_by_listing_id[listing_id])
        write_jsonl(crawl_log_path, log_records)

    seed_audits = build_seed_audits(crawl_root)
    if not seed_audits:
        seed_urls = {}
        for record in metadata_records:
            seed_url = record.get("source_seed_url") or record.get("crawl_seed_url")
            if seed_url:
                seed_urls.setdefault(
                    seed_url,
                    {
                        "seed_url": seed_url,
                        "final_url": record.get("final_seed_url") or seed_url,
                        "target_location_path": record.get("crawl_location_path"),
                        "target_location_label": record.get("crawl_location_label"),
                        "target_category": record.get("crawl_category"),
                        "http_status": 200,
                        "is_seed_url_valid": record.get("is_seed_url_valid"),
                    },
                )
        seed_audits = list(seed_urls.values())

    valid_seed_urls = sum(
        1 for record in seed_audits if record.get("is_seed_url_valid") is True
    )
    invalid_seed_urls = len(seed_audits) - valid_seed_urls
    location_matched_count = sum(
        1
        for record in detail_audits
        if record.get("location_match_status") == "matched"
    )
    location_assumed_from_seed_count = sum(
        1
        for record in detail_audits
        if record.get("location_match_status") == "assumed_from_seed"
    )
    location_mismatch_count = sum(
        1
        for record in detail_audits
        if record.get("location_match_status") == "mismatch"
    )
    location_unknown_count = sum(
        1
        for record in detail_audits
        if record.get("location_match_status") == "unknown"
    )
    category_matched_count = sum(
        1
        for record in detail_audits
        if record.get("category_match_status") == "matched"
    )
    category_mismatch_count = sum(
        1
        for record in detail_audits
        if record.get("category_match_status") not in {"matched", None}
    )
    audit_pass_count = location_matched_count + location_assumed_from_seed_count

    location_audit = {
        "crawl_id": crawl_id,
        "source": summary.get("source"),
        "crawl_date": summary.get("crawl_date"),
        "total_seed_urls": len(seed_audits),
        "valid_seed_urls": valid_seed_urls,
        "invalid_seed_urls": invalid_seed_urls,
        "total_listing_urls_found": summary.get("total_listing_urls_found"),
        "detail_pages_crawled": summary.get("success_count"),
        "detail_records_audited": len(detail_audits),
        "location_matched_count": location_matched_count,
        "location_assumed_from_seed_count": location_assumed_from_seed_count,
        "location_mismatch_count": location_mismatch_count,
        "location_unknown_count": location_unknown_count,
        "category_matched_count": category_matched_count,
        "category_mismatch_count": category_mismatch_count,
        "audit_pass_rate": safe_rate(audit_pass_count, len(detail_audits)),
        "seed_url_audits": seed_audits,
        "detail_audit_records": detail_audits,
    }

    summary.update(
        {
            "valid_seed_urls": valid_seed_urls,
            "invalid_seed_urls": invalid_seed_urls,
            "detail_records_audited": len(detail_audits),
            "location_matched_count": location_matched_count,
            "location_assumed_from_seed_count": location_assumed_from_seed_count,
            "location_mismatch_count": location_mismatch_count,
            "location_unknown_count": location_unknown_count,
            "category_matched_count": category_matched_count,
            "category_mismatch_count": category_mismatch_count,
            "audit_pass_rate": location_audit["audit_pass_rate"],
        }
    )

    location_audit_path = crawl_log_dir / f"crawl_location_audit_{crawl_id}.json"
    audit_sample_path = crawl_log_dir / f"audit_sample_{crawl_id}.csv"
    save_json_file(summary_path, summary)
    save_json_file(location_audit_path, location_audit)
    write_audit_sample_csv(audit_sample_path, audit_samples)

    return {
        "crawl_id": crawl_id,
        "metadata_updated": len(metadata_paths),
        "listing_cards_loaded": len(listing_cards),
        "location_audit_path": str(location_audit_path),
        "audit_sample_path": str(audit_sample_path),
        "summary": {
            "valid_seed_urls": valid_seed_urls,
            "invalid_seed_urls": invalid_seed_urls,
            "detail_records_audited": len(detail_audits),
            "location_matched_count": location_matched_count,
            "location_assumed_from_seed_count": location_assumed_from_seed_count,
            "location_mismatch_count": location_mismatch_count,
            "location_unknown_count": location_unknown_count,
            "category_matched_count": category_matched_count,
            "category_mismatch_count": category_mismatch_count,
            "audit_pass_rate": location_audit["audit_pass_rate"],
        },
    }


def main():
    parser = argparse.ArgumentParser(
        description="Backfill location/category audit fields for an existing Bronze crawl."
    )
    parser.add_argument("--crawl-id", required=True)
    args = parser.parse_args()
    result = backfill_crawl(args.crawl_id)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
