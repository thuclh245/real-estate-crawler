from __future__ import annotations

from dataclasses import dataclass, field
import json
from datetime import datetime
from pathlib import Path
from typing import Callable

from crawler.block_detector import (
    classify_failure_status,
    increment_http_counters,
    is_blocked_page,
)
from crawler.bronze_writer import (
    build_listing_paths,
    write_metadata_json,
    write_raw_html,
)
from crawler.crawl_audit import (
    audit_location,
    classify_category_match,
    print_error,
    print_warning,
    safe_rate,
    validate_seed_url,
    write_audit_sample_csv,
)
from crawler.crawl_config import (
    expand_targets,
    get_target_city,
    get_target_location_label,
    get_target_location_path,
    get_target_location_slug,
)
from crawler.fetcher import fetch_with_retry
from crawler.parser import extract_phase1_stub_fields, html_to_text
from crawler.sources.base import SourceAdapter
from crawler.sources.batdongsan import BatdongsanAdapter
from crawler.url_builder import build_seed_url
from common.paths import bronze_partition_path
from common.storage import append_jsonl, save_json_file, save_text_file
from common.utils import get_listing_id_or_hash, now_utc_iso, today_str

"""
khởi tạo summary
loop target
  loop list page
    fetch
    validate seed URL
    detect block
    ghi debug list page
    append crawl log
    parse listing cards
  loop detail listing
    fetch detail
    detect block
    html_to_text
    parse detail fields
    audit location/category
    build metadata lớn
    write raw_html/raw_text/raw_json/metadata
    append crawl log
tính summary cuối
ghi crawl_summary
ghi location_audit
ghi audit_sample_csv
"""


@dataclass
class CrawlDependencies:
    fetch_with_retry_fn: Callable[
        ..., tuple[int | None, str, str | None, int, str | None]
    ] = fetch_with_retry
    source_adapter: SourceAdapter = field(default_factory=BatdongsanAdapter)


class CrawlOrchestrator:
    def __init__(
        self,
        config: dict,
        *,
        base_dir: Path | str = Path("data"),
        dependencies: CrawlDependencies | None = None,
    ) -> None:
        self.config = config
        self.base_dir = Path(base_dir)
        self.dependencies = dependencies or CrawlDependencies()

    def run(self) -> dict:
        source = self.config["source"]
        base_url = self.config["base_url"]
        settings = self.config.get("crawl_settings", {})

        crawl_date = today_str()
        crawl_id = f"{source}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        max_pages = settings.get("max_pages_per_target", 2)
        max_listings = settings.get("max_listings_per_target", 50)
        delay = settings.get("request_delay_seconds", 2)
        fetch_mode = str(settings.get("fetch_mode", "requests"))
        stop_on_block = bool(settings.get("stop_on_block", True))
        crawler_version = settings.get("crawler_version", "v0.1")
        parser_version = settings.get("parser_version", "v0.1")
        max_retries = int(settings.get("max_retries", 1))
        retry_delay_seconds = float(settings.get("retry_delay_seconds", 10))

        bronze_root = bronze_partition_path(
            source=source,
            crawl_date=crawl_date,
            crawl_id=crawl_id,
            base_dir=self.base_dir,
        )

        summary = {
            "crawl_id": crawl_id,
            "source": source,
            "crawl_date": crawl_date,
            "started_at": now_utc_iso(),
            "total_listing_pages_requested": 0,
            "listing_page_failed_count": 0,
            "total_listing_urls_found": 0,
            "total_detail_pages_requested": 0,
            "success_count": 0,
            "failed_count": 0,
            "blocked_count": 0,
            "http_403_count": 0,
            "http_429_count": 0,
            "duplicate_url_count": 0,
            "raw_html_file_count": 0,
            "metadata_file_count": 0,
            "avg_html_size": 0,
            "crawler_version": crawler_version,
            "parser_version": parser_version,
            "bronze_layout": "crawl_id_partitioned",
            "max_retries": max_retries,
            "retry_delay_seconds": retry_delay_seconds,
            "records": [],
        }

        crawl_log_path = bronze_root / "crawl_log" / f"crawl_log_{crawl_id}.jsonl"
        debug_list_root = self.base_dir / "debug" / "list_pages"
        requested_detail_urls: list[str] = []
        written_raw_html_paths: list[Path] = []
        written_metadata_paths: list[Path] = []
        seed_url_audits: list[dict] = []
        detail_audits: list[dict] = []
        audit_samples: list[dict] = []
        expanded_targets = expand_targets(self.config)
        known_location_labels = sorted(
            {
                label
                for label in (
                    get_target_location_label(target) for target in expanded_targets
                )
                if label
            }
        )

        for target in expanded_targets:
            category = target["category"]
            city = get_target_city(target)
            location_path = get_target_location_path(target)
            location_slug = get_target_location_slug(target)
            location_label = get_target_location_label(target)

            target_listing_entries = []
            seed_url_override = target.get("seed_url")
            current_seed_url = seed_url_override or build_seed_url(
                base_url, category, location_path, 1
            )
            current_final_seed_url = None
            current_is_seed_url_valid = None

            for page_number in range(1, max_pages + 1):
                if seed_url_override:
                    page_url = (
                        seed_url_override
                        if page_number == 1
                        else f"{seed_url_override}/p{page_number}"
                    )
                else:
                    page_url = build_seed_url(
                        base_url, category, location_path, page_number
                    )

                summary["total_listing_pages_requested"] += 1

                try:
                    http_status, html, final_url, retry_count, fetch_error = (
                        self.dependencies.fetch_with_retry_fn(
                            page_url,
                            mode=fetch_mode,
                            max_retries=max_retries,
                            retry_delay_seconds=retry_delay_seconds,
                        )
                    )
                    if fetch_error:
                        raise RuntimeError(fetch_error)

                    html_length = len(html or "")
                    html_preview = (html or "")[:300]

                    is_seed_url_valid = validate_seed_url(
                        page_url, final_url or "", location_path
                    )
                    if page_number == 1:
                        current_final_seed_url = final_url
                        current_is_seed_url_valid = is_seed_url_valid
                        seed_url_audits.append(
                            {
                                "seed_url": page_url,
                                "final_url": final_url,
                                "target_location_path": location_path,
                                "target_location_label": location_label,
                                "target_category": category,
                                "http_status": http_status,
                                "is_seed_url_valid": is_seed_url_valid,
                            }
                        )

                    if not is_seed_url_valid:
                        summary["failed_count"] += 1
                        summary["listing_page_failed_count"] += 1
                        error_message = f"Invalid seed URL redirect: seed={page_url}, final={final_url}"
                        self._save_list_page_debug(
                            debug_list_root=debug_list_root,
                            crawl_id=crawl_id,
                            source=source,
                            target=target,
                            page_url=page_url,
                            page_number=page_number,
                            fetch_mode=fetch_mode,
                            http_status=http_status,
                            final_url=final_url,
                            is_seed_url_valid=False,
                            html=html,
                            listing_urls_found=0,
                            is_blocked=False,
                            error_message=error_message,
                        )
                        append_jsonl(
                            crawl_log_path,
                            {
                                "crawl_id": crawl_id,
                                "type": "listing_page",
                                "url": page_url,
                                "final_url": final_url,
                                "crawl_status": "invalid_seed_url",
                                "fetch_mode": fetch_mode,
                                "http_status": http_status,
                                "html_length": html_length,
                                "html_preview": html_preview,
                                "target_location_path": location_path,
                                "target_location_label": location_label,
                                "target_category": category,
                                "is_seed_url_valid": False,
                                "error_message": error_message,
                                "retry_count": retry_count,
                                "scraped_at": now_utc_iso(),
                            },
                        )
                        break

                    if delay:
                        import time

                        time.sleep(delay)

                    if http_status != 200:
                        list_page_blocked = is_blocked_page(http_status, html)
                        self._save_list_page_debug(
                            debug_list_root=debug_list_root,
                            crawl_id=crawl_id,
                            source=source,
                            target=target,
                            page_url=page_url,
                            page_number=page_number,
                            fetch_mode=fetch_mode,
                            http_status=http_status,
                            final_url=final_url,
                            is_seed_url_valid=is_seed_url_valid,
                            html=html,
                            listing_urls_found=0,
                            is_blocked=list_page_blocked,
                            error_message=(
                                "Blocked by anti-bot protection"
                                if list_page_blocked
                                else f"HTTP {http_status}"
                            ),
                        )

                        if list_page_blocked:
                            summary["blocked_count"] += 1
                            summary["failed_count"] += 1
                            summary["listing_page_failed_count"] += 1
                            increment_http_counters(summary, http_status)

                            append_jsonl(
                                crawl_log_path,
                                {
                                    "crawl_id": crawl_id,
                                    "type": "listing_page",
                                    "url": page_url,
                                    "final_url": final_url,
                                    "crawl_status": "blocked",
                                    "fetch_mode": fetch_mode,
                                    "http_status": http_status,
                                    "html_length": html_length,
                                    "html_preview": html_preview,
                                    "error_message": "Blocked by anti-bot protection",
                                    "retry_count": retry_count,
                                    "is_seed_url_valid": is_seed_url_valid,
                                    "scraped_at": now_utc_iso(),
                                },
                            )

                            if stop_on_block:
                                break
                            continue

                        summary["failed_count"] += 1
                        summary["listing_page_failed_count"] += 1
                        increment_http_counters(summary, http_status)

                        append_jsonl(
                            crawl_log_path,
                            {
                                "crawl_id": crawl_id,
                                "type": "listing_page",
                                "url": page_url,
                                "final_url": final_url,
                                "crawl_status": "failed_http",
                                "fetch_mode": fetch_mode,
                                "http_status": http_status,
                                "html_length": html_length,
                                "html_preview": html_preview,
                                "error_message": f"HTTP {http_status}",
                                "retry_count": retry_count,
                                "is_seed_url_valid": is_seed_url_valid,
                                "scraped_at": now_utc_iso(),
                            },
                        )
                        continue

                    listing_entries = self.dependencies.source_adapter.parse_list_page(
                        html
                    )

                    list_page_blocked = is_blocked_page(
                        http_status, html, listing_urls_found=len(listing_entries)
                    )
                    self._save_list_page_debug(
                        debug_list_root=debug_list_root,
                        crawl_id=crawl_id,
                        source=source,
                        target=target,
                        page_url=page_url,
                        page_number=page_number,
                        fetch_mode=fetch_mode,
                        http_status=http_status,
                        final_url=final_url,
                        is_seed_url_valid=is_seed_url_valid,
                        html=html,
                        listing_urls_found=len(listing_entries),
                        is_blocked=list_page_blocked,
                        error_message=(
                            "Blocked by anti-bot protection"
                            if list_page_blocked
                            else None
                        ),
                    )

                    if list_page_blocked:
                        summary["blocked_count"] += 1
                        summary["failed_count"] += 1
                        summary["listing_page_failed_count"] += 1
                        increment_http_counters(summary, http_status)

                        append_jsonl(
                            crawl_log_path,
                            {
                                "crawl_id": crawl_id,
                                "type": "listing_page",
                                "url": page_url,
                                "final_url": final_url,
                                "crawl_status": "blocked",
                                "fetch_mode": fetch_mode,
                                "http_status": http_status,
                                "html_length": html_length,
                                "html_preview": html_preview,
                                "error_message": "Blocked by anti-bot protection",
                                "retry_count": retry_count,
                                "is_seed_url_valid": is_seed_url_valid,
                                "scraped_at": now_utc_iso(),
                            },
                        )

                        if stop_on_block:
                            break
                        continue

                    if not listing_entries:
                        from bs4 import BeautifulSoup

                        soup = BeautifulSoup(html or "", "lxml")
                        sample_hrefs = [
                            a.get("href") for a in soup.find_all("a", href=True)[:50]
                        ]
                        for _idx, _href in enumerate(sample_hrefs):
                            pass

                    target_listing_entries.extend(
                        {
                            **listing_entry,
                            "page_url": page_url,
                            "page_number": page_number,
                            "crawl_seed_url": current_seed_url,
                            "final_seed_url": current_final_seed_url or final_url,
                            "is_seed_url_valid": (
                                current_is_seed_url_valid
                                if current_is_seed_url_valid is not None
                                else is_seed_url_valid
                            ),
                        }
                        for listing_entry in listing_entries
                    )

                except Exception as e:
                    summary["failed_count"] += 1
                    summary["listing_page_failed_count"] += 1
                    self._save_list_page_debug(
                        debug_list_root=debug_list_root,
                        crawl_id=crawl_id,
                        source=source,
                        target=target,
                        page_url=page_url,
                        page_number=page_number,
                        fetch_mode=fetch_mode,
                        http_status=None,
                        final_url=None,
                        is_seed_url_valid=False,
                        html="",
                        listing_urls_found=0,
                        is_blocked=False,
                        error_message=str(e),
                    )

                    append_jsonl(
                        crawl_log_path,
                        {
                            "crawl_id": crawl_id,
                            "type": "listing_page",
                            "url": page_url,
                            "final_url": None,
                            "crawl_status": classify_failure_status(None, str(e)),
                            "fetch_mode": fetch_mode,
                            "http_status": None,
                            "error_message": str(e),
                            "retry_count": max_retries,
                            "is_seed_url_valid": False,
                            "scraped_at": now_utc_iso(),
                        },
                    )

            deduped_entries_by_url = {}
            for entry in target_listing_entries:
                deduped_entries_by_url.setdefault(entry["listing_url"], entry)
            target_listing_entries = list(deduped_entries_by_url.values())[
                :max_listings
            ]
            summary["total_listing_urls_found"] += len(target_listing_entries)

            for listing_entry in target_listing_entries:
                listing_url = listing_entry["listing_url"]
                summary["total_detail_pages_requested"] += 1
                requested_detail_urls.append(listing_url)

                scraped_at = now_utc_iso()

                try:
                    (
                        http_status,
                        detail_html,
                        final_detail_url,
                        retry_count,
                        fetch_error,
                    ) = self.dependencies.fetch_with_retry_fn(
                        listing_url,
                        mode=fetch_mode,
                        max_retries=max_retries,
                        retry_delay_seconds=retry_delay_seconds,
                    )
                    if fetch_error:
                        raise RuntimeError(fetch_error)

                    detail_text = html_to_text(detail_html)
                    basic_fields = extract_phase1_stub_fields(detail_text, listing_url)
                    detail_fields = self.dependencies.source_adapter.parse_detail_page(
                        detail_html
                    )
                    title = (
                        detail_fields.get("detail_title")
                        or listing_entry.get("listing_card_title")
                        or basic_fields.get("title_raw")
                    )
                    description = detail_fields.get(
                        "detail_description"
                    ) or listing_entry.get("listing_card_description")
                    location_audit = audit_location(
                        {
                            **listing_entry,
                            **detail_fields,
                            "listing_url": listing_url,
                            "final_detail_url": final_detail_url,
                            "title": title,
                            "description": description,
                        },
                        target,
                        known_location_labels=known_location_labels,
                    )
                    detail_location_raw = location_audit.get("detail_location_raw")
                    location_match_status = location_audit["location_match_status"]
                    location_match_confidence = location_audit[
                        "location_match_confidence"
                    ]
                    location_match_method = location_audit["location_match_method"]
                    category_match_status, category_match_confidence = (
                        classify_category_match(detail_text, category)
                    )

                    if location_match_status in {"mismatch", "unknown"}:
                        print_error(
                            f"  LOCATION AUDIT: {location_match_status} for {listing_url}"
                        )
                    elif location_match_status == "assumed_from_seed":
                        print_warning(
                            f"  LOCATION AUDIT: assumed_from_seed for {listing_url}"
                        )

                    if category_match_status != "matched":
                        print_warning(
                            f"  CATEGORY AUDIT: {category_match_status} for {listing_url}"
                        )

                    listing_id = basic_fields.get(
                        "listing_id"
                    ) or get_listing_id_or_hash(listing_url)

                    paths = build_listing_paths(
                        listing_id=listing_id,
                        source=source,
                        crawl_date=crawl_date,
                        crawl_id=crawl_id,
                        base_dir=self.base_dir,
                    )
                    raw_html_path = paths["raw_html"]
                    raw_text_path = paths["raw_text"]
                    raw_json_path = paths["raw_json"]
                    metadata_path = paths["metadata"]

                    metadata = {
                        "listing_id": listing_id,
                        "listing_url": listing_url,
                        "source": source,
                        "scraped_at": scraped_at,
                        "crawl_date": crawl_date,
                        "crawl_id": crawl_id,
                        "crawl_status": "ok",
                        "http_status": http_status,
                        "fetch_mode": fetch_mode,
                        "raw_html_path": str(raw_html_path),
                        "raw_text_path": str(raw_text_path),
                        "raw_json_path": str(raw_json_path),
                        "metadata_path": str(metadata_path),
                        "listing_business_type": target.get("business_type"),
                        "property_type_group": target.get("property_type_group"),
                        "crawl_category": category,
                        "crawl_category_label": target.get("category_label"),
                        "crawl_city": city,
                        "crawl_city_label": target.get("city_label"),
                        "crawl_city_slug": target.get("city_slug"),
                        "crawl_location_slug": location_slug,
                        "crawl_location_path": target.get("location_path"),
                        "crawl_location_label": location_label,
                        "crawl_location_level": target.get("location_level"),
                        "priority_group": target.get("priority_group"),
                        "crawl_district": location_slug,
                        "crawl_district_label": location_label,
                        "title": title,
                        "description": description,
                        "crawl_seed_url": listing_entry["crawl_seed_url"],
                        "source_seed_url": listing_entry["crawl_seed_url"],
                        "final_seed_url": listing_entry.get("final_seed_url"),
                        "is_seed_url_valid": listing_entry.get("is_seed_url_valid"),
                        "final_detail_url": final_detail_url,
                        "page_url": listing_entry["page_url"],
                        "page_number": listing_entry["page_number"],
                        "listing_card_title": listing_entry.get("listing_card_title"),
                        "listing_card_price_raw": listing_entry.get(
                            "listing_card_price_raw"
                        ),
                        "listing_card_area_raw": listing_entry.get(
                            "listing_card_area_raw"
                        ),
                        "listing_card_location_raw": listing_entry.get(
                            "listing_card_location_raw"
                        ),
                        "listing_card_old_district_raw": listing_entry.get(
                            "listing_card_old_district_raw"
                        ),
                        "breadcrumb_raw": detail_fields.get("breadcrumb_raw"),
                        "breadcrumb_location_raw": detail_fields.get(
                            "breadcrumb_location_raw"
                        ),
                        "detail_location_raw": detail_location_raw,
                        "detail_address_raw": detail_fields.get("detail_address_raw"),
                        "location_evidence_text": location_audit.get(
                            "location_evidence_text"
                        ),
                        "location_evidence_source": location_audit.get(
                            "location_evidence_source"
                        ),
                        "location_match_status": location_match_status,
                        "location_match_confidence": location_match_confidence,
                        "location_match_method": location_match_method,
                        "category_match_status": category_match_status,
                        "category_match_confidence": category_match_confidence,
                        "parser_version": parser_version,
                        "crawler_version": crawler_version,
                        "error_message": None,
                        "retry_count": retry_count,
                    }

                    extracted_json = {**metadata, "extracted": basic_fields}

                    write_raw_html(
                        html=detail_html,
                        listing_id=listing_id,
                        source=source,
                        crawl_date=crawl_date,
                        crawl_id=crawl_id,
                        base_dir=self.base_dir,
                    )
                    save_text_file(raw_text_path, detail_text)
                    save_json_file(raw_json_path, extracted_json)
                    write_metadata_json(
                        metadata=metadata,
                        listing_id=listing_id,
                        source=source,
                        crawl_date=crawl_date,
                        crawl_id=crawl_id,
                        base_dir=self.base_dir,
                    )
                    written_raw_html_paths.append(raw_html_path)
                    written_metadata_paths.append(metadata_path)

                    summary["success_count"] += 1
                    detail_audit = {
                        "listing_id": listing_id,
                        "listing_url": listing_url,
                        "source_seed_url": listing_entry["crawl_seed_url"],
                        "final_seed_url": listing_entry.get("final_seed_url"),
                        "is_seed_url_valid": listing_entry.get("is_seed_url_valid"),
                        "crawl_category": category,
                        "crawl_location_path": target.get("location_path"),
                        "crawl_location_label": location_label,
                        "listing_card_location_raw": listing_entry.get(
                            "listing_card_location_raw"
                        ),
                        "listing_card_old_district_raw": listing_entry.get(
                            "listing_card_old_district_raw"
                        ),
                        "detail_address_raw": detail_fields.get("detail_address_raw"),
                        "breadcrumb_location_raw": detail_fields.get(
                            "breadcrumb_location_raw"
                        ),
                        "detail_location_raw": detail_location_raw,
                        "location_evidence_text": location_audit.get(
                            "location_evidence_text"
                        ),
                        "location_evidence_source": location_audit.get(
                            "location_evidence_source"
                        ),
                        "location_match_status": location_match_status,
                        "location_match_confidence": location_match_confidence,
                        "location_match_method": location_match_method,
                        "category_match_status": category_match_status,
                        "category_match_confidence": category_match_confidence,
                    }
                    detail_audits.append(detail_audit)
                    if len(audit_samples) < 20:
                        audit_samples.append(
                            {
                                **detail_audit,
                                "title": title,
                                "price_raw": listing_entry.get("listing_card_price_raw")
                                or basic_fields.get("price_raw"),
                                "area_raw": listing_entry.get("listing_card_area_raw")
                                or basic_fields.get("area_raw"),
                            }
                        )

                    append_jsonl(
                        crawl_log_path,
                        {
                            **metadata,
                            "type": "detail_page",
                        },
                    )

                except Exception as e:
                    crawl_status = classify_failure_status(None, str(e))
                    summary["failed_count"] += 1
                    append_jsonl(
                        crawl_log_path,
                        {
                            "crawl_id": crawl_id,
                            "type": "detail_page",
                            "listing_url": listing_url,
                            "crawl_status": crawl_status,
                            "fetch_mode": fetch_mode,
                            "http_status": None,
                            "error_message": str(e),
                            "scraped_at": scraped_at,
                            "crawl_category": category,
                            "crawl_city": city,
                            "crawl_city_slug": target.get("city_slug"),
                            "crawl_location_slug": location_slug,
                            "crawl_location_path": target.get("location_path"),
                            "crawl_location_label": location_label,
                            "crawl_location_level": target.get("location_level"),
                            "priority_group": target.get("priority_group"),
                            "crawl_district": location_slug,
                            "crawl_seed_url": listing_entry["crawl_seed_url"],
                            "source_seed_url": listing_entry["crawl_seed_url"],
                            "final_seed_url": listing_entry.get("final_seed_url"),
                            "is_seed_url_valid": listing_entry.get("is_seed_url_valid"),
                            "page_url": listing_entry["page_url"],
                            "page_number": listing_entry["page_number"],
                            "retry_count": max_retries,
                        },
                    )

        summary["finished_at"] = now_utc_iso()

        total_requested = summary["total_detail_pages_requested"]
        if total_requested > 0:
            summary["crawl_success_rate"] = summary["success_count"] / total_requested
        else:
            summary["crawl_success_rate"] = 0

        total_listing_pages = summary["total_listing_pages_requested"]
        if total_listing_pages > 0:
            summary["listing_page_block_rate"] = (
                summary["blocked_count"] / total_listing_pages
            )
        else:
            summary["listing_page_block_rate"] = 0

        unique_urls = len(set(requested_detail_urls))
        summary["duplicate_url_count"] = len(requested_detail_urls) - unique_urls

        unique_written_raw_html = list(dict.fromkeys(written_raw_html_paths))
        unique_written_metadata = list(dict.fromkeys(written_metadata_paths))
        summary["raw_html_file_count"] = len(unique_written_raw_html)
        summary["metadata_file_count"] = len(unique_written_metadata)
        if unique_written_raw_html:
            summary["avg_html_size"] = sum(
                path.stat().st_size for path in unique_written_raw_html
            ) / len(unique_written_raw_html)
        else:
            summary["avg_html_size"] = 0

        valid_seed_urls = sum(
            1 for record in seed_url_audits if record.get("is_seed_url_valid")
        )
        invalid_seed_urls = len(seed_url_audits) - valid_seed_urls
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
            "source": source,
            "crawl_date": crawl_date,
            "total_seed_urls": len(seed_url_audits),
            "valid_seed_urls": valid_seed_urls,
            "invalid_seed_urls": invalid_seed_urls,
            "total_listing_urls_found": summary["total_listing_urls_found"],
            "detail_pages_crawled": summary["success_count"],
            "location_matched_count": location_matched_count,
            "location_assumed_from_seed_count": location_assumed_from_seed_count,
            "location_mismatch_count": location_mismatch_count,
            "location_unknown_count": location_unknown_count,
            "category_matched_count": category_matched_count,
            "category_mismatch_count": category_mismatch_count,
            "audit_pass_rate": safe_rate(audit_pass_count, len(detail_audits)),
            "seed_url_audits": seed_url_audits,
            "detail_audit_records": detail_audits,
        }

        summary["valid_seed_urls"] = valid_seed_urls
        summary["invalid_seed_urls"] = invalid_seed_urls
        summary["location_matched_count"] = location_matched_count
        summary["location_assumed_from_seed_count"] = location_assumed_from_seed_count
        summary["location_mismatch_count"] = location_mismatch_count
        summary["location_unknown_count"] = location_unknown_count
        summary["category_matched_count"] = category_matched_count
        summary["category_mismatch_count"] = category_mismatch_count
        summary["audit_pass_rate"] = location_audit["audit_pass_rate"]

        summary_path = bronze_root / "crawl_log" / f"crawl_summary_{crawl_id}.json"
        location_audit_path = (
            bronze_root / "crawl_log" / f"crawl_location_audit_{crawl_id}.json"
        )
        audit_sample_path = bronze_root / "crawl_log" / f"audit_sample_{crawl_id}.csv"
        save_json_file(summary_path, summary)
        save_json_file(location_audit_path, location_audit)
        write_audit_sample_csv(audit_sample_path, audit_samples)

        print("Crawl finished.")
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        print(f"Location audit: {location_audit_path}")
        print(f"Audit sample CSV: {audit_sample_path}")
        print(f"Audit command: python scripts\\audit_bronze.py --crawl-id {crawl_id}")

        return summary

    def _save_list_page_debug(
        self,
        *,
        debug_list_root: Path,
        crawl_id: str,
        source: str,
        target: dict,
        page_url: str,
        page_number: int,
        fetch_mode: str,
        http_status: int | None,
        final_url: str | None,
        is_seed_url_valid: bool | None,
        html: str,
        listing_urls_found: int,
        is_blocked: bool,
        error_message: str | None = None,
    ) -> tuple[Path, Path]:
        category = target["category"]
        location_slug = target.get("location_slug") or target.get("district")
        debug_stem = f"{category}_{location_slug}_p{page_number}"
        debug_run_root = debug_list_root / f"crawl_id={crawl_id}"
        debug_html_path = debug_run_root / f"{debug_stem}.html"
        debug_metadata_path = debug_run_root / f"{debug_stem}.json"

        save_text_file(debug_html_path, html)
        save_json_file(
            debug_metadata_path,
            {
                "crawl_id": crawl_id,
                "source": source,
                "page_url": page_url,
                "page_number": page_number,
                "fetch_mode": fetch_mode,
                "http_status": http_status,
                "final_url": final_url,
                "is_seed_url_valid": is_seed_url_valid,
                "html_length": len(html or ""),
                "listing_urls_found": listing_urls_found,
                "is_blocked": is_blocked,
                "target_business_type": target.get("business_type"),
                "target_category": category,
                "target_category_label": target.get("category_label"),
                "target_property_type_group": target.get("property_type_group"),
                "target_city": target.get("city"),
                "target_city_label": target.get("city_label"),
                "target_city_slug": target.get("city_slug"),
                "target_location_slug": target.get("location_slug"),
                "target_location_path": target.get("location_path"),
                "target_location_label": target.get("location_label"),
                "target_location_level": target.get("location_level"),
                "target_priority_group": target.get("priority_group"),
                "target_district": target.get("district"),
                "target_district_label": target.get("district_label"),
                "target_seed_url": target.get("seed_url"),
                "saved_html_path": str(debug_html_path),
                "error_message": error_message,
                "saved_at": now_utc_iso(),
            },
        )
        return debug_html_path, debug_metadata_path
