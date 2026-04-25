from pathlib import Path
import argparse
import json
import time
import asyncio
import sys
from datetime import datetime
import yaml
import requests
from urllib.parse import urljoin

from parser import html_to_text, extract_phase1_stub_fields
from storage import save_text_file, save_json_file, append_jsonl
from url_builder import build_seed_url
from utils import now_utc_iso, today_str


CRAWLER_VERSION = "v0.1"
PARSER_VERSION = "v0.1"


for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8")


def make_crawl_id(source_slug: str = "batdongsan") -> str:
    return f"{source_slug}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"


def is_blocked_page(http_status: int, html: str, listing_urls_found: int | None = None) -> bool:
    html_lower = (html or "").lower()

    if http_status in [403, 429]:
        return True

    block_signals = [
        "<title>just a moment",
        "cf-browser-verification",
        "/cdn-cgi/challenge-platform",
        "__cf_chl",
        "cf-chl-",
        "attention required! | cloudflare",
        "g-recaptcha",
        "h-captcha",
    ]

    has_block_signal = any(signal in html_lower for signal in block_signals)
    if not has_block_signal:
        return False

    # If listing URLs are already extracted from a listing page, treat content as usable.
    if listing_urls_found is not None and listing_urls_found > 0:
        return False

    return True


def increment_http_counters(summary: dict, http_status: int | None):
    if http_status == 403:
        summary["http_403_count"] += 1
    elif http_status == 429:
        summary["http_429_count"] += 1


def is_retryable_http_status(http_status: int | None) -> bool:
    return http_status in {408, 500, 502, 503, 504}


def classify_failure_status(http_status: int | None, error_message: str | None = None) -> str:
    error_lower = (error_message or "").lower()
    if http_status in {403, 429}:
        return "blocked"
    if http_status is not None:
        return "failed_http"
    if "timeout" in error_lower or "timed out" in error_lower:
        return "failed_timeout"
    return "failed_fetch"


def fetch_with_retry(
    url: str,
    mode: str,
    max_retries: int,
    retry_delay_seconds: float,
) -> tuple[int | None, str, int, str | None]:
    last_status = None
    last_html = ""
    last_error = None

    for attempt in range(max_retries + 1):
        try:
            status, html = fetch_html(url, mode=mode)
            if is_retryable_http_status(status) and attempt < max_retries:
                last_status = status
                last_html = html or ""
                last_error = f"HTTP {status}"
                time.sleep(retry_delay_seconds)
                continue
            return status, html or "", attempt, None
        except Exception as exc:
            last_error = str(exc)
            if attempt < max_retries:
                time.sleep(retry_delay_seconds)
                continue
            return last_status, last_html, attempt, last_error

    return last_status, last_html, max_retries, last_error


def save_list_page_debug(
    debug_list_root: Path,
    crawl_id: str,
    source: str,
    target: dict,
    page_url: str,
    page_number: int,
    fetch_mode: str,
    http_status: int | None,
    html: str,
    listing_urls_found: int,
    is_blocked: bool,
    error_message: str | None = None,
) -> tuple[Path, Path]:
    category = target["category"]
    district = target["district"]
    debug_stem = f"{category}_{district}_p{page_number}"
    debug_run_root = debug_list_root / f"crawl_id={crawl_id}"
    debug_html_path = debug_run_root / f"{debug_stem}.html"
    debug_metadata_path = debug_run_root / f"{debug_stem}.json"

    save_text_file(debug_html_path, html)
    save_json_file(debug_metadata_path, {
        "crawl_id": crawl_id,
        "source": source,
        "page_url": page_url,
        "page_number": page_number,
        "fetch_mode": fetch_mode,
        "http_status": http_status,
        "html_length": len(html or ""),
        "listing_urls_found": listing_urls_found,
        "is_blocked": is_blocked,
        "target_business_type": target.get("business_type"),
        "target_category": category,
        "target_category_label": target.get("category_label"),
        "target_property_type_group": target.get("property_type_group"),
        "target_city": target.get("city"),
        "target_city_label": target.get("city_label"),
        "target_district": district,
        "target_district_label": target.get("district_label"),
        "target_seed_url": target.get("seed_url"),
        "saved_html_path": str(debug_html_path),
        "error_message": error_message,
        "saved_at": now_utc_iso(),
    })
    return debug_html_path, debug_metadata_path


def load_config(config_path: str | Path) -> dict:
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def fetch_html_requests(url: str) -> tuple[int, str]:
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    }
    response = requests.get(url, headers=headers, timeout=30, allow_redirects=True)
    return response.status_code, response.text


async def fetch_html_crawl4ai_async(url: str) -> tuple[int, str]:
    try:
        from crawl4ai import AsyncWebCrawler
    except ImportError as exc:
        raise RuntimeError("crawl4ai is not installed in current environment") from exc

    async with AsyncWebCrawler() as crawler:
        result = await crawler.arun(url=url)

    html = (
        getattr(result, "html", None)
        or getattr(result, "cleaned_html", None)
        or getattr(result, "markdown", None)
        or ""
    )
    status_code = getattr(result, "status_code", None)
    if status_code is None:
        status_code = 200 if html else 0

    return int(status_code), html


def fetch_html_crawl4ai(url: str) -> tuple[int, str]:
    return asyncio.run(fetch_html_crawl4ai_async(url))


def fetch_html(url: str, mode: str = "requests") -> tuple[int, str]:
    mode = (mode or "requests").lower().strip()

    if mode == "requests":
        return fetch_html_requests(url)
    if mode == "crawl4ai":
        return fetch_html_crawl4ai(url)

    raise ValueError(f"Unsupported fetch mode: {mode}")

def extract_listing_urls_from_listing_page(html: str) -> list[str]:
    from bs4 import BeautifulSoup
    import re

    soup = BeautifulSoup(html or "", "lxml")
    urls = set()

    for a in soup.find_all("a", href=True):
        href = (a.get("href") or "").strip()
        if not href:
            continue

        absolute = urljoin("https://batdongsan.com.vn", href)
        if "batdongsan.com.vn" not in absolute:
            continue

        if re.search(r"pr\d+", absolute) and "ban-" in absolute:
            urls.add(absolute)

    return list(urls)

def run_crawler(config_path: str | Path):
    config = load_config(config_path)
    print(f"Starting crawler version {CRAWLER_VERSION} with config: {config}")

    # Placeholder: Implement actual crawling logic here
    # For example, loop through categories and districts, fetch listing pages, extract URLs, etc.

    print("Crawler finished.")

def run_crawl(config_path: str):
    config = load_config(config_path)

    source = config["source"]
    base_url = config["base_url"]
    settings = config.get("crawl_settings", {})

    crawl_date = today_str()
    crawl_id = make_crawl_id("batdongsan")

    max_pages = settings.get("max_pages_per_target", 2)
    max_listings = settings.get("max_listings_per_target", 50)
    delay = settings.get("request_delay_seconds", 2)
    fetch_mode = str(settings.get("fetch_mode", "requests"))
    stop_on_block = bool(settings.get("stop_on_block", True))
    crawler_version = settings.get("crawler_version", CRAWLER_VERSION)
    parser_version = settings.get("parser_version", PARSER_VERSION)
    max_retries = int(settings.get("max_retries", 1))
    retry_delay_seconds = float(settings.get("retry_delay_seconds", 10))

    bronze_root = (
        Path("data")
        / "bronze"
        / f"source=batdongsan"
        / f"crawl_date={crawl_date}"
        / f"crawl_id={crawl_id}"
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
        "records": []
    }

    crawl_log_path = bronze_root / "crawl_log" / f"crawl_log_{crawl_id}.jsonl"
    debug_list_root = Path("data") / "debug" / "list_pages"
    requested_detail_urls: list[str] = []
    written_raw_html_paths: list[Path] = []
    written_metadata_paths: list[Path] = []

    for target in config["targets"]:
        category = target["category"]
        city = target["city"]
        district = target["district"]

        target_listing_entries = []
        seed_url_override = target.get("seed_url")

        for page_number in range(1, max_pages + 1):
            if seed_url_override:
                page_url = seed_url_override if page_number == 1 else f"{seed_url_override}/p{page_number}"
            else:
                page_url = build_seed_url(base_url, category, district, page_number)

            summary["total_listing_pages_requested"] += 1

            print(f"[LIST PAGE] {page_url}")
            print(f"  Fetch mode: {fetch_mode}")

            try:
                http_status, html, retry_count, fetch_error = fetch_with_retry(
                    page_url,
                    mode=fetch_mode,
                    max_retries=max_retries,
                    retry_delay_seconds=retry_delay_seconds,
                )
                if fetch_error:
                    raise RuntimeError(fetch_error)

                html_length = len(html or "")
                html_preview = (html or "")[:300]

                print(f"  HTTP status: {http_status}")
                print(f"  HTML length: {html_length}")
                print(f"  First 300 chars: {html_preview}")

                time.sleep(delay)

                if http_status != 200:
                    list_page_blocked = is_blocked_page(http_status, html)
                    save_list_page_debug(
                        debug_list_root=debug_list_root,
                        crawl_id=crawl_id,
                        source=source,
                        target=target,
                        page_url=page_url,
                        page_number=page_number,
                        fetch_mode=fetch_mode,
                        http_status=http_status,
                        html=html,
                        listing_urls_found=0,
                        is_blocked=list_page_blocked,
                        error_message="Blocked by anti-bot protection" if list_page_blocked else f"HTTP {http_status}",
                    )

                    if list_page_blocked:
                        summary["blocked_count"] += 1
                        summary["failed_count"] += 1
                        summary["listing_page_failed_count"] += 1
                        increment_http_counters(summary, http_status)

                        append_jsonl(crawl_log_path, {
                            "crawl_id": crawl_id,
                            "type": "listing_page",
                            "url": page_url,
                            "crawl_status": "blocked",
                            "fetch_mode": fetch_mode,
                            "http_status": http_status,
                            "html_length": html_length,
                            "html_preview": html_preview,
                            "error_message": "Blocked by anti-bot protection",
                            "retry_count": retry_count,
                            "scraped_at": now_utc_iso()
                        })

                        print("  BLOCKED: anti-bot page detected.")
                        if stop_on_block:
                            print("  stop_on_block=true -> Stop this target.")
                            break
                        print("  stop_on_block=false -> Continue to next page.")
                        continue

                    summary["failed_count"] += 1
                    summary["listing_page_failed_count"] += 1
                    increment_http_counters(summary, http_status)

                    append_jsonl(crawl_log_path, {
                        "crawl_id": crawl_id,
                        "type": "listing_page",
                        "url": page_url,
                        "crawl_status": "failed_http",
                        "fetch_mode": fetch_mode,
                        "http_status": http_status,
                        "html_length": html_length,
                        "html_preview": html_preview,
                        "error_message": f"HTTP {http_status}",
                        "retry_count": retry_count,
                        "scraped_at": now_utc_iso()
                    })
                    continue

                listing_urls = extract_listing_urls_from_listing_page(html)
                print(f"  Listing URLs found: {len(listing_urls)}")

                list_page_blocked = is_blocked_page(http_status, html, listing_urls_found=len(listing_urls))
                save_list_page_debug(
                    debug_list_root=debug_list_root,
                    crawl_id=crawl_id,
                    source=source,
                    target=target,
                    page_url=page_url,
                    page_number=page_number,
                    fetch_mode=fetch_mode,
                    http_status=http_status,
                    html=html,
                    listing_urls_found=len(listing_urls),
                    is_blocked=list_page_blocked,
                    error_message="Blocked by anti-bot protection" if list_page_blocked else None,
                )

                if list_page_blocked:
                    summary["blocked_count"] += 1
                    summary["failed_count"] += 1
                    summary["listing_page_failed_count"] += 1
                    increment_http_counters(summary, http_status)

                    append_jsonl(crawl_log_path, {
                        "crawl_id": crawl_id,
                        "type": "listing_page",
                        "url": page_url,
                        "crawl_status": "blocked",
                        "fetch_mode": fetch_mode,
                        "http_status": http_status,
                        "html_length": html_length,
                        "html_preview": html_preview,
                        "error_message": "Blocked by anti-bot protection",
                        "retry_count": retry_count,
                        "scraped_at": now_utc_iso()
                    })

                    print("  BLOCKED: anti-bot page detected.")
                    if stop_on_block:
                        print("  stop_on_block=true -> Stop this target.")
                        break
                    print("  stop_on_block=false -> Continue to next page.")
                    continue

                if not listing_urls:
                    from bs4 import BeautifulSoup

                    soup = BeautifulSoup(html or "", "lxml")
                    sample_hrefs = [a.get("href") for a in soup.find_all("a", href=True)[:50]]
                    print("  First 50 hrefs:")
                    for idx, href in enumerate(sample_hrefs):
                        print(f"    {idx}: {href}")

                target_listing_entries.extend({
                    "listing_url": listing_url,
                    "page_url": page_url,
                    "page_number": page_number,
                    "crawl_seed_url": seed_url_override or build_seed_url(base_url, category, district, 1),
                } for listing_url in listing_urls)

            except Exception as e:
                summary["failed_count"] += 1
                summary["listing_page_failed_count"] += 1
                save_list_page_debug(
                    debug_list_root=debug_list_root,
                    crawl_id=crawl_id,
                    source=source,
                    target=target,
                    page_url=page_url,
                    page_number=page_number,
                    fetch_mode=fetch_mode,
                    http_status=None,
                    html="",
                    listing_urls_found=0,
                    is_blocked=False,
                    error_message=str(e),
                )

                append_jsonl(crawl_log_path, {
                    "crawl_id": crawl_id,
                    "type": "listing_page",
                    "url": page_url,
                    "crawl_status": classify_failure_status(None, str(e)),
                    "fetch_mode": fetch_mode,
                    "http_status": None,
                    "error_message": str(e),
                    "retry_count": max_retries,
                    "scraped_at": now_utc_iso()
                })

        # Dedup URL trong target, preserving the first page context where it appeared.
        deduped_entries_by_url = {}
        for entry in target_listing_entries:
            deduped_entries_by_url.setdefault(entry["listing_url"], entry)
        target_listing_entries = list(deduped_entries_by_url.values())[:max_listings]
        summary["total_listing_urls_found"] += len(target_listing_entries)

        for listing_entry in target_listing_entries:
            listing_url = listing_entry["listing_url"]
            summary["total_detail_pages_requested"] += 1
            requested_detail_urls.append(listing_url)

            scraped_at = now_utc_iso()

            try:
                http_status, detail_html, retry_count, fetch_error = fetch_with_retry(
                    listing_url,
                    mode=fetch_mode,
                    max_retries=max_retries,
                    retry_delay_seconds=retry_delay_seconds,
                )
                time.sleep(delay)

                if fetch_error:
                    raise RuntimeError(fetch_error)

                if http_status != 200:
                    crawl_status = classify_failure_status(http_status)
                    summary["failed_count"] += 1
                    if crawl_status == "blocked":
                        summary["blocked_count"] += 1
                    increment_http_counters(summary, http_status)
                    append_jsonl(crawl_log_path, {
                        "crawl_id": crawl_id,
                        "type": "detail_page",
                        "listing_url": listing_url,
                        "crawl_status": crawl_status,
                        "fetch_mode": fetch_mode,
                        "http_status": http_status,
                        "error_message": f"HTTP {http_status}",
                        "scraped_at": scraped_at,
                        "crawl_seed_url": listing_entry["crawl_seed_url"],
                        "page_url": listing_entry["page_url"],
                        "page_number": listing_entry["page_number"],
                        "retry_count": retry_count,
                    })
                    continue

                detail_text = html_to_text(detail_html)
                basic_fields = extract_phase1_stub_fields(detail_text, listing_url)

                listing_id = basic_fields.get("listing_id") or str(abs(hash(listing_url)))

                raw_html_path = bronze_root / "raw_html" / f"listing_id={listing_id}.html"
                raw_text_path = bronze_root / "raw_text" / f"listing_id={listing_id}.txt"
                raw_json_path = bronze_root / "raw_json" / f"listing_id={listing_id}.json"
                metadata_path = bronze_root / "metadata" / f"listing_id={listing_id}.json"

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
                    "crawl_district": district,
                    "crawl_district_label": target.get("district_label"),
                    "crawl_seed_url": listing_entry["crawl_seed_url"],
                    "page_url": listing_entry["page_url"],
                    "page_number": listing_entry["page_number"],
                    "parser_version": parser_version,
                    "crawler_version": crawler_version,
                    "error_message": None,
                    "retry_count": retry_count,
                }

                extracted_json = {
                    **metadata,
                    "extracted": basic_fields
                }

                save_text_file(raw_html_path, detail_html)
                save_text_file(raw_text_path, detail_text)
                save_json_file(raw_json_path, extracted_json)
                save_json_file(metadata_path, metadata)
                written_raw_html_paths.append(raw_html_path)
                written_metadata_paths.append(metadata_path)

                summary["success_count"] += 1

                append_jsonl(crawl_log_path, {
                    **metadata,
                    "type": "detail_page",
                })

            except Exception as e:
                crawl_status = classify_failure_status(None, str(e))
                summary["failed_count"] += 1
                append_jsonl(crawl_log_path, {
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
                    "crawl_district": district,
                    "crawl_seed_url": listing_entry["crawl_seed_url"],
                    "page_url": listing_entry["page_url"],
                    "page_number": listing_entry["page_number"],
                    "retry_count": max_retries,
                })

    summary["finished_at"] = now_utc_iso()

    total_requested = summary["total_detail_pages_requested"]
    if total_requested > 0:
        summary["crawl_success_rate"] = summary["success_count"] / total_requested
    else:
        summary["crawl_success_rate"] = 0

    total_listing_pages = summary["total_listing_pages_requested"]
    if total_listing_pages > 0:
        summary["listing_page_block_rate"] = summary["blocked_count"] / total_listing_pages
    else:
        summary["listing_page_block_rate"] = 0

    unique_urls = len(set(requested_detail_urls))
    summary["duplicate_url_count"] = len(requested_detail_urls) - unique_urls

    unique_written_raw_html = list(dict.fromkeys(written_raw_html_paths))
    unique_written_metadata = list(dict.fromkeys(written_metadata_paths))
    summary["raw_html_file_count"] = len(unique_written_raw_html)
    summary["metadata_file_count"] = len(unique_written_metadata)
    if unique_written_raw_html:
        summary["avg_html_size"] = sum(path.stat().st_size for path in unique_written_raw_html) / len(unique_written_raw_html)
    else:
        summary["avg_html_size"] = 0

    summary_path = bronze_root / "crawl_log" / f"crawl_summary_{crawl_id}.json"
    save_json_file(summary_path, summary)

    print("Crawl finished.")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"Audit command: python scripts\\audit_bronze.py --crawl-id {crawl_id}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run Batdongsan Bronze crawler.")
    parser.add_argument(
        "--config",
        default="configs/crawl_targets.yaml",
        help="Path to crawl target YAML config.",
    )
    args = parser.parse_args()
    run_crawl(args.config)


