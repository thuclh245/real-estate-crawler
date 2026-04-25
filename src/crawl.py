from pathlib import Path
import json
import time
import yaml
import requests
from urllib.parse import urljoin

from parser import html_to_text, extract_basic_fields
from storage import save_text_file, save_json_file, append_jsonl
from url_builder import build_seed_url
from utils import now_utc_iso, today_str


CRAWLER_VERSION = "v0.1"
PARSER_VERSION = "v0.1"

def load_config(config_path: str | Path) -> dict:
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def fetch_html(url: str) -> tuple[int, str]:
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    }
    response = requests.get(url, headers=headers, timeout=30, allow_redirects=True)
    return response.status_code, response.text

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
    crawl_id = f"batdongsan_{crawl_date.replace('-', '')}_001"

    max_pages = settings.get("max_pages_per_target", 2)
    max_listings = settings.get("max_listings_per_target", 50)
    delay = settings.get("request_delay_seconds", 2)

    bronze_root = Path("data") / "bronze" / f"source=batdongsan" / f"crawl_date={crawl_date}"

    summary = {
        "crawl_id": crawl_id,
        "source": source,
        "crawl_date": crawl_date,
        "started_at": now_utc_iso(),
        "total_listing_urls_found": 0,
        "total_detail_pages_requested": 0,
        "success_count": 0,
        "failed_count": 0,
        "records": []
    }

    crawl_log_path = bronze_root / "crawl_log" / f"crawl_log_{crawl_date.replace('-', '')}.jsonl"
    debug_list_root = Path("data") / "debug" / "list_pages"

    for target in config["targets"]:
        category = target["category"]
        city = target["city"]
        district = target["district"]

        target_listing_urls = []
        seed_url_override = target.get("seed_url")

        for page_number in range(1, max_pages + 1):
            if seed_url_override:
                page_url = seed_url_override if page_number == 1 else f"{seed_url_override}/p{page_number}"
            else:
                page_url = build_seed_url(base_url, category, district, page_number)

            print(f"[LIST PAGE] {page_url}")

            try:
                http_status, html = fetch_html(page_url)
                html_length = len(html or "")
                html_preview = (html or "")[:300]

                print(f"  HTTP status: {http_status}")
                print(f"  HTML length: {html_length}")
                print(f"  First 300 chars: {html_preview}")

                debug_list_path = debug_list_root / f"{category}_{district}_p{page_number}.html"
                save_text_file(debug_list_path, html)
                time.sleep(delay)

                if http_status != 200:
                    append_jsonl(crawl_log_path, {
                        "crawl_id": crawl_id,
                        "type": "listing_page",
                        "url": page_url,
                        "crawl_status": "failed",
                        "http_status": http_status,
                        "html_length": html_length,
                        "html_preview": html_preview,
                        "error_message": f"HTTP {http_status}",
                        "scraped_at": now_utc_iso()
                    })
                    continue

                listing_urls = extract_listing_urls_from_listing_page(html)
                print(f"  Listing URLs found: {len(listing_urls)}")

                if not listing_urls:
                    from bs4 import BeautifulSoup

                    soup = BeautifulSoup(html or "", "lxml")
                    sample_hrefs = [a.get("href") for a in soup.find_all("a", href=True)[:50]]
                    print("  First 50 hrefs:")
                    for idx, href in enumerate(sample_hrefs):
                        print(f"    {idx}: {href}")

                target_listing_urls.extend(listing_urls)

            except Exception as e:
                append_jsonl(crawl_log_path, {
                    "crawl_id": crawl_id,
                    "type": "listing_page",
                    "url": page_url,
                    "crawl_status": "failed",
                    "http_status": None,
                    "error_message": str(e),
                    "scraped_at": now_utc_iso()
                })

        # Dedup URL trong target
        target_listing_urls = list(dict.fromkeys(target_listing_urls))[:max_listings]
        summary["total_listing_urls_found"] += len(target_listing_urls)

        for listing_url in target_listing_urls:
            summary["total_detail_pages_requested"] += 1

            scraped_at = now_utc_iso()

            try:
                http_status, detail_html = fetch_html(listing_url)
                time.sleep(delay)

                if http_status != 200:
                    summary["failed_count"] += 1
                    append_jsonl(crawl_log_path, {
                        "crawl_id": crawl_id,
                        "type": "detail_page",
                        "listing_url": listing_url,
                        "crawl_status": "failed",
                        "http_status": http_status,
                        "error_message": f"HTTP {http_status}",
                        "scraped_at": scraped_at
                    })
                    continue

                detail_text = html_to_text(detail_html)
                basic_fields = extract_basic_fields(detail_text, listing_url)

                listing_id = basic_fields.get("listing_id") or str(abs(hash(listing_url)))

                raw_html_path = bronze_root / "raw_html" / f"listing_id={listing_id}.html"
                raw_text_path = bronze_root / "raw_text" / f"listing_id={listing_id}.txt"
                raw_json_path = bronze_root / "raw_json" / f"listing_id={listing_id}.json"

                metadata = {
                    "listing_id": listing_id,
                    "listing_url": listing_url,
                    "source": source,
                    "scraped_at": scraped_at,
                    "crawl_date": crawl_date,
                    "crawl_id": crawl_id,
                    "crawl_status": "ok",
                    "http_status": http_status,
                    "raw_html_path": str(raw_html_path),
                    "raw_text_path": str(raw_text_path),
                    "raw_json_path": str(raw_json_path),
                    "crawl_category": category,
                    "crawl_category_label": target.get("category_label"),
                    "crawl_city": city,
                    "crawl_city_label": target.get("city_label"),
                    "crawl_district": district,
                    "crawl_district_label": target.get("district_label"),
                    "page_number": None,
                    "parser_version": PARSER_VERSION,
                    "crawler_version": CRAWLER_VERSION
                }

                extracted_json = {
                    **metadata,
                    "extracted": basic_fields
                }

                save_text_file(raw_html_path, detail_html)
                save_text_file(raw_text_path, detail_text)
                save_json_file(raw_json_path, extracted_json)

                summary["success_count"] += 1

                append_jsonl(crawl_log_path, {
                    **metadata,
                    "type": "detail_page",
                    "error_message": None
                })

            except Exception as e:
                summary["failed_count"] += 1
                append_jsonl(crawl_log_path, {
                    "crawl_id": crawl_id,
                    "type": "detail_page",
                    "listing_url": listing_url,
                    "crawl_status": "failed",
                    "http_status": None,
                    "error_message": str(e),
                    "scraped_at": scraped_at,
                    "crawl_category": category,
                    "crawl_city": city,
                    "crawl_district": district
                })

    summary["finished_at"] = now_utc_iso()

    total_requested = summary["total_detail_pages_requested"]
    if total_requested > 0:
        summary["crawl_success_rate"] = summary["success_count"] / total_requested
    else:
        summary["crawl_success_rate"] = 0

    summary_path = bronze_root / "crawl_log" / f"crawl_summary_{crawl_date.replace('-', '')}.json"
    save_json_file(summary_path, summary)

    print("Crawl finished.")
    print(json.dumps(summary, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    run_crawl("configs/crawl_targets.yaml")


