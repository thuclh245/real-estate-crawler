"""Small Crawl4AI smoke crawler for Alonhadat listing pages.

This script is intentionally separate from the production Batdongsan pipeline.
It checks whether Alonhadat pages can be fetched and whether listing cards can
be extracted for a small multi-district, multi-property-type sample.
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup

BASE_URL = "https://alonhadat.com.vn"

DISTRICTS = [
    {"name": "Quận Ba Đình", "code": "407", "slug": "quan-ba-dinh"},
    {"name": "Quận Bắc Từ Liêm", "code": "704", "slug": "quan-bac-tu-liem"},
    {"name": "Quận Cầu Giấy", "code": "408", "slug": "quan-cau-giay"},
    {"name": "Quận Đống Đa", "code": "409", "slug": "quan-dong-da"},
    {"name": "Quận Hà Đông", "code": "410", "slug": "quan-ha-dong"},
    {"name": "Quận Hai Bà Trưng", "code": "411", "slug": "quan-hai-ba-trung"},
    {"name": "Quận Hoàn Kiếm", "code": "412", "slug": "hoan-kiem"},
    {"name": "Quận Hoàng Mai", "code": "413", "slug": "quan-hoang-mai"},
    {"name": "Quận Long Biên", "code": "414", "slug": "quan-long-bien"},
    {"name": "Quận Nam Từ Liêm", "code": "434", "slug": "quan-nam-tu-liem"},
    {"name": "Quận Tây Hồ", "code": "415", "slug": "quan-tay-ho"},
    {"name": "Quận Thanh Xuân", "code": "416", "slug": "quan-thanh-xuan"},
]

CATEGORIES = [
    {
        "name": "Nhà mặt tiền",
        "slug": "nha-mat-tien",
        "property_type_group": "street_house",
    },
    {
        "name": "Nhà trong hẻm",
        "slug": "nha-trong-hem",
        "property_type_group": "alley_house",
    },
    {
        "name": "Biệt thự, nhà liền kề",
        "slug": "biet-thu-nha-lien-ke",
        "property_type_group": "villa_townhouse",
    },
    {
        "name": "Căn hộ chung cư",
        "slug": "can-ho-chung-cu",
        "property_type_group": "apartment",
    },
]


for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8")


def clean_text(value: str | None) -> str | None:
    if value is None:
        return None
    value = " ".join(value.split()).strip()
    return value or None


def build_page_url(district: dict, category: dict) -> str:
    return (
        f"{BASE_URL}/nha-dat/can-ban/{category['slug']}/ha-noi/"
        f"{district['code']}/{district['slug']}.html"
    )


def safe_stem(value: str) -> str:
    value = value.lower()
    value = re.sub(r"[^a-z0-9]+", "_", value)
    return value.strip("_") or "page"


def extract_listing_id(url: str) -> str | None:
    match = re.search(r"-(\d+)\.html(?:$|\?)", url)
    return match.group(1) if match else None


def parse_listing_cards(
    html: str,
    page_url: str,
    district: dict,
    category: dict,
    limit: int,
) -> list[dict]:
    soup = BeautifulSoup(html or "", "lxml")
    rows = []

    for index, card in enumerate(soup.select("article.property-item"), start=1):
        link = card.select_one("a.link[href]")
        href = link.get("href") if link else None
        listing_url = urljoin(BASE_URL, href) if href else None
        title = (
            clean_text(card.select_one(".property-title").get_text(" ", strip=True))
            if card.select_one(".property-title")
            else None
        )
        image = card.select_one(".thumbnail img")
        image_url = (
            urljoin(BASE_URL, image.get("src")) if image and image.get("src") else None
        )
        created = card.select_one(".created-date")

        row = {
            "source": "alonhadat.com.vn",
            "district_name": district["name"],
            "district_code": district["code"],
            "district_slug": district["slug"],
            "category_name": category["name"],
            "category_slug": category["slug"],
            "property_type_group": category["property_type_group"],
            "page_url": page_url,
            "card_index": index,
            "listing_id": extract_listing_id(listing_url or ""),
            "listing_url": listing_url,
            "title_raw": title,
            "description_raw": (
                clean_text(card.select_one(".brief").get_text(" ", strip=True))
                if card.select_one(".brief")
                else None
            ),
            "price_raw": (
                clean_text(card.select_one(".price").get_text(" ", strip=True))
                if card.select_one(".price")
                else None
            ),
            "area_raw": (
                clean_text(card.select_one(".area").get_text(" ", strip=True))
                if card.select_one(".area")
                else None
            ),
            "street_width_raw": (
                clean_text(card.select_one(".street-width").get_text(" ", strip=True))
                if card.select_one(".street-width")
                else None
            ),
            "floor_count_raw": (
                clean_text(card.select_one(".floors").get_text(" ", strip=True))
                if card.select_one(".floors")
                else None
            ),
            "bedroom_count_raw": (
                clean_text(card.select_one(".bedroom").get_text(" ", strip=True))
                if card.select_one(".bedroom")
                else None
            ),
            "parking_raw": (
                clean_text(card.select_one(".parking").get_text(" ", strip=True))
                if card.select_one(".parking")
                else None
            ),
            "new_address_raw": (
                clean_text(card.select_one(".new-address").get_text(" ", strip=True))
                if card.select_one(".new-address")
                else None
            ),
            "old_address_raw": (
                clean_text(card.select_one(".old-address").get_text(" ", strip=True))
                if card.select_one(".old-address")
                else None
            ),
            "posted_date_raw": (
                clean_text(created.get_text(" ", strip=True)) if created else None
            ),
            "posted_date": created.get("datetime") if created else None,
            "image_url": image_url,
        }
        rows.append(row)

        if len(rows) >= limit:
            break

    return rows


async def fetch_page(crawler, url: str) -> tuple[int | None, str, str, str]:
    result = await crawler.arun(url=url)
    html = getattr(result, "html", None) or getattr(result, "cleaned_html", None) or ""
    markdown = getattr(result, "markdown", None) or ""
    status = getattr(result, "status_code", None)
    final_url = (
        getattr(result, "url", None)
        or getattr(result, "final_url", None)
        or getattr(result, "response_url", None)
        or url
    )
    return status, html, markdown, final_url


async def run(args: argparse.Namespace) -> Path:
    from crawl4ai import AsyncWebCrawler

    run_id = f"alonhadat_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    output_root = Path(args.output_dir) / run_id
    raw_html_dir = output_root / "raw_html"
    clean_text_dir = output_root / "clean_text"
    raw_html_dir.mkdir(parents=True, exist_ok=True)
    clean_text_dir.mkdir(parents=True, exist_ok=True)

    page_summaries = []
    all_rows = []
    group_count = min(args.max_districts, len(DISTRICTS)) * min(
        args.max_categories, len(CATEGORIES)
    )
    target_total = args.target_total_listings
    if target_total is not None and group_count > 0:
        base_limit = target_total // group_count
        extra_groups = target_total % group_count
    else:
        base_limit = args.limit_per_group
        extra_groups = 0
    group_index = 0

    async with AsyncWebCrawler(verbose=False) as crawler:
        for district in DISTRICTS[: args.max_districts]:
            for category in CATEGORIES[: args.max_categories]:
                group_limit = base_limit + (1 if group_index < extra_groups else 0)
                group_index += 1
                page_url = build_page_url(district, category)
                page_stem = f"{district['code']}_{safe_stem(district['slug'])}_{safe_stem(category['slug'])}"
                print(f"[FETCH] {district['name']} | {category['name']} | {page_url}")

                try:
                    status, html, markdown, final_url = await fetch_page(
                        crawler, page_url
                    )
                    rows = parse_listing_cards(
                        html, page_url, district, category, group_limit
                    )
                    error_message = None
                except Exception as exc:
                    status, html, markdown, final_url, rows = None, "", "", page_url, []
                    error_message = str(exc)

                (raw_html_dir / f"{page_stem}.html").write_text(html, encoding="utf-8")
                (clean_text_dir / f"{page_stem}.md").write_text(
                    markdown, encoding="utf-8"
                )

                page_summary = {
                    "district_name": district["name"],
                    "district_code": district["code"],
                    "district_slug": district["slug"],
                    "category_name": category["name"],
                    "category_slug": category["slug"],
                    "property_type_group": category["property_type_group"],
                    "page_url": page_url,
                    "final_url": final_url,
                    "status_code": status,
                    "html_length": len(html),
                    "markdown_length": len(markdown),
                    "listing_count": len(rows),
                    "listing_limit": group_limit,
                    "is_success": bool(status == 200 and rows),
                    "error_message": error_message,
                }
                page_summaries.append(page_summary)
                all_rows.extend(rows)
                print(f"[RESULT] status={status} listings={len(rows)} html={len(html)}")

                if args.delay_seconds > 0:
                    await asyncio.sleep(args.delay_seconds)

    (output_root / "listings.json").write_text(
        json.dumps(all_rows, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (output_root / "page_summary.json").write_text(
        json.dumps(page_summaries, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    csv_path = output_root / "listings.csv"
    if all_rows:
        with csv_path.open("w", encoding="utf-8-sig", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=list(all_rows[0].keys()))
            writer.writeheader()
            writer.writerows(all_rows)
    else:
        csv_path.write_text("", encoding="utf-8-sig")

    summary = {
        "run_id": run_id,
        "output_root": str(output_root),
        "districts_requested": min(args.max_districts, len(DISTRICTS)),
        "categories_requested": min(args.max_categories, len(CATEGORIES)),
        "pages_requested": len(page_summaries),
        "pages_success": sum(1 for row in page_summaries if row["is_success"]),
        "total_listings_extracted": len(all_rows),
        "limit_per_group": args.limit_per_group,
        "target_total_listings": target_total,
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }
    (output_root / "run_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return output_root


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Test crawl Alonhadat listing pages with Crawl4AI"
    )
    parser.add_argument("--output-dir", default="data/test/alonhadat_crawl")
    parser.add_argument("--limit-per-group", type=int, default=5)
    parser.add_argument(
        "--target-total-listings",
        type=int,
        default=120,
        help="Balanced total listing target across district/category groups. Use 0 to disable.",
    )
    parser.add_argument("--max-districts", type=int, default=len(DISTRICTS))
    parser.add_argument("--max-categories", type=int, default=len(CATEGORIES))
    parser.add_argument("--delay-seconds", type=float, default=0.5)
    args = parser.parse_args()
    if args.target_total_listings == 0:
        args.target_total_listings = None
    return args


if __name__ == "__main__":
    asyncio.run(run(parse_args()))
