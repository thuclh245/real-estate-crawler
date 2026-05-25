"""Small Crawl4AI smoke crawler for Nhatot listing pages.

This script is intentionally separate from the production Batdongsan pipeline.
It checks whether Nhatot pages can be fetched and whether listing records can
be extracted from the Next.js state embedded in listing pages.
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import re
import sys
import unittest
from datetime import datetime
from pathlib import Path

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from crawler.sources.nhatot import NhatotAdapter

BASE_URL = "https://www.nhatot.com"

DISTRICTS = [
    {"name": "Quận Ba Đình", "slug": "quan-ba-dinh"},
    {"name": "Quận Bắc Từ Liêm", "slug": "quan-bac-tu-liem"},
    {"name": "Quận Cầu Giấy", "slug": "quan-cau-giay"},
    {"name": "Quận Đống Đa", "slug": "quan-dong-da"},
    {"name": "Quận Hà Đông", "slug": "quan-ha-dong"},
    {"name": "Quận Hai Bà Trưng", "slug": "quan-hai-ba-trung"},
    {"name": "Quận Hoàn Kiếm", "slug": "quan-hoan-kiem"},
    {"name": "Quận Hoàng Mai", "slug": "quan-hoang-mai"},
    {"name": "Quận Long Biên", "slug": "quan-long-bien"},
    {"name": "Quận Nam Từ Liêm", "slug": "quan-nam-tu-liem"},
    {"name": "Quận Tây Hồ", "slug": "quan-tay-ho"},
]

CATEGORIES = [
    {
        "name": "Căn hộ/Chung cư",
        "slug": "mua-ban-can-ho-chung-cu",
        "category_id": 1010,
        "property_type_group": "apartment",
    },
    {
        "name": "Nhà ở",
        "slug": "mua-ban-nha-dat",
        "category_id": 1020,
        "property_type_group": "house",
    },
    {
        "name": "Đất",
        "slug": "mua-ban-dat",
        "category_id": 1040,
        "property_type_group": "land",
    },
    {
        "name": "Văn phòng, mặt bằng kinh doanh",
        "slug": "sang-nhuong-van-phong-mat-bang-kinh-doanh",
        "category_id": 1030,
        "property_type_group": "commercial",
    },
]


for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8")


def clean_text(value: object) -> str | None:
    if value is None:
        return None
    value = " ".join(str(value).split()).strip()
    return value or None


def safe_stem(value: str) -> str:
    value = value.lower()
    value = re.sub(r"[^a-z0-9]+", "_", value)
    return value.strip("_") or "page"


def default_page_for_date(run_date: datetime, page_cycle: int) -> int:
    if page_cycle <= 1:
        return 1
    return ((run_date.day - 1) % page_cycle) + 1


def build_page_url(district: dict, category: dict, page: int) -> str:
    url = f"{BASE_URL}/{category['slug']}-{district['slug']}-ha-noi"
    if page > 1:
        url = f"{url}?page={page}"
    return url


def extract_next_state(html: str) -> dict | None:
    soup = BeautifulSoup(html or "", "lxml")
    tag = soup.find("script", id="__NEXT_DATA__")
    if not tag or not tag.string:
        return None
    try:
        return json.loads(tag.string)
    except json.JSONDecodeError:
        return None


def extract_ads_from_state(state: dict | None) -> list[dict]:
    if not state:
        return []
    props = state.get("props") or {}
    candidates = [
        props.get("initialState", {}),
        props.get("pageProps", {}).get("initialState", {}),
    ]
    for candidate in candidates:
        ads = candidate.get("adlisting", {}).get("data", {}).get("ads", [])
        if isinstance(ads, list) and ads:
            return [ad for ad in ads if isinstance(ad, dict)]
    return []


def extract_listing_id(ad: dict) -> str | None:
    value = ad.get("list_id") or ad.get("ad_id")
    return str(value) if value is not None else None


def build_listing_url(ad: dict, district: dict, category: dict) -> str | None:
    listing_id = extract_listing_id(ad)
    if not listing_id:
        return None
    return f"{BASE_URL}/{category['slug']}-{district['slug']}-ha-noi/{listing_id}.htm"


def param_value(ad: dict, param_id: str) -> str | None:
    for param in ad.get("params") or []:
        if isinstance(param, dict) and param.get("id") == param_id:
            return clean_text(param.get("value"))
    return None


def parse_listing_rows(
    html: str,
    page_url: str,
    district: dict,
    category: dict,
    page: int,
    limit: int,
) -> list[dict]:
    rows = []
    ads = extract_ads_from_state(extract_next_state(html))

    for index, ad in enumerate(ads, start=1):
        image_list = ad.get("images") if isinstance(ad.get("images"), list) else []
        row = {
            "source": "nhatot.com",
            "district_name": district["name"],
            "district_slug": district["slug"],
            "category_name": category["name"],
            "category_slug": category["slug"],
            "category_id": category["category_id"],
            "property_type_group": category["property_type_group"],
            "page": page,
            "page_url": page_url,
            "card_index": index,
            "listing_id": extract_listing_id(ad),
            "ad_id": clean_text(ad.get("ad_id")),
            "listing_url": build_listing_url(ad, district, category),
            "title_raw": clean_text(ad.get("subject")),
            "description_raw": clean_text(ad.get("body")),
            "price_raw": clean_text(ad.get("price_string")),
            "price_vnd": ad.get("price"),
            "price_million_per_m2": ad.get("price_million_per_m2"),
            "area_m2": ad.get("size"),
            "area_raw": clean_text(ad.get("size_unit_string"))
            or (f"{ad.get('size')} m2" if ad.get("size") is not None else None),
            "bedroom_count": ad.get("rooms"),
            "bathroom_count": ad.get("toilets"),
            "floor_count": ad.get("floornumber"),
            "property_subtype_raw": clean_text(
                param_value(ad, "apartment_type") or param_value(ad, "house_type")
            ),
            "legal_status_raw": clean_text(param_value(ad, "property_legal_document")),
            "furniture_level_raw": clean_text(param_value(ad, "furnishing_sell")),
            "city_raw": clean_text(ad.get("region_name")),
            "district_raw": clean_text(ad.get("area_name")),
            "ward_raw": clean_text(ad.get("ward_name")),
            "street_raw": clean_text(ad.get("street_name")),
            "address_raw": clean_text(ad.get("detail_address")),
            "latitude": ad.get("latitude"),
            "longitude": ad.get("longitude"),
            "posted_date_raw": clean_text(ad.get("date")),
            "seller_name": clean_text(ad.get("account_name") or ad.get("full_name")),
            "seller_active_listing_count": ad.get("sold_ads"),
            "phone_masked": clean_text(ad.get("phone")),
            "image_count": ad.get("number_of_images") or len(image_list),
            "image_url": clean_text(ad.get("image") or ad.get("thumbnail_image")),
            "image_urls": "|".join(str(url) for url in image_list if url),
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

    run_id = f"nhatot_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    output_root = Path(args.output_dir) / run_id
    raw_html_dir = output_root / "raw_html"
    clean_text_dir = output_root / "clean_text"
    raw_html_dir.mkdir(parents=True, exist_ok=True)
    clean_text_dir.mkdir(parents=True, exist_ok=True)

    run_date = (
        datetime.strptime(args.run_date, "%Y-%m-%d")
        if args.run_date
        else datetime.now()
    )
    page = args.page or default_page_for_date(run_date, args.page_cycle)
    selected_districts = DISTRICTS[: args.max_districts]
    selected_categories = CATEGORIES[: args.max_categories]

    page_summaries = []
    all_rows = []

    async with AsyncWebCrawler(verbose=False) as crawler:
        for district in selected_districts:
            for category in selected_categories:
                requested_page = page
                used_page = requested_page
                page_url = build_page_url(district, category, used_page)
                page_stem = f"{safe_stem(district['slug'])}_{safe_stem(category['slug'])}_page_{requested_page}"
                print(
                    f"[FETCH] {district['name']} | {category['name']} | page={requested_page} | {page_url}"
                )

                try:
                    status, html, markdown, final_url = await fetch_page(
                        crawler, page_url
                    )
                    rows = parse_listing_rows(
                        html,
                        page_url,
                        district,
                        category,
                        used_page,
                        args.limit_per_group,
                    )
                    if not rows and args.fallback_to_page_one and requested_page != 1:
                        fallback_url = build_page_url(district, category, 1)
                        print(
                            f"[FALLBACK] no listings on page={requested_page}; trying page=1 | {fallback_url}"
                        )
                        status, html, markdown, final_url = await fetch_page(
                            crawler, fallback_url
                        )
                        used_page = 1
                        page_url = fallback_url
                        rows = parse_listing_rows(
                            html,
                            page_url,
                            district,
                            category,
                            used_page,
                            args.limit_per_group,
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
                    "district_slug": district["slug"],
                    "category_name": category["name"],
                    "category_slug": category["slug"],
                    "property_type_group": category["property_type_group"],
                    "requested_page": requested_page,
                    "used_page": used_page,
                    "page_url": page_url,
                    "final_url": final_url,
                    "status_code": status,
                    "html_length": len(html),
                    "markdown_length": len(markdown),
                    "listing_count": len(rows),
                    "listing_limit": args.limit_per_group,
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
        "run_date": run_date.date().isoformat(),
        "requested_page": page,
        "page_cycle": args.page_cycle,
        "fallback_to_page_one": args.fallback_to_page_one,
        "districts_requested": len(selected_districts),
        "categories_requested": len(selected_categories),
        "pages_requested": len(page_summaries),
        "pages_success": sum(1 for row in page_summaries if row["is_success"]),
        "total_listings_extracted": len(all_rows),
        "limit_per_group": args.limit_per_group,
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
        description="Test crawl Nhatot listing pages with Crawl4AI"
    )
    parser.add_argument("--output-dir", default="data/test/nhatot_crawl")
    parser.add_argument("--limit-per-group", type=int, default=5)
    parser.add_argument("--max-districts", type=int, default=len(DISTRICTS))
    parser.add_argument("--max-categories", type=int, default=len(CATEGORIES))
    parser.add_argument(
        "--page",
        type=int,
        default=None,
        help="Explicit page number. Defaults to run-date page cycle.",
    )
    parser.add_argument(
        "--page-cycle",
        type=int,
        default=5,
        help="Rotate pages by day. 2026-05-19 maps to page 4.",
    )
    parser.add_argument(
        "--run-date",
        default=None,
        help="YYYY-MM-DD date used for page rotation. Defaults to today.",
    )
    parser.add_argument("--delay-seconds", type=float, default=0.5)
    parser.add_argument(
        "--no-fallback-to-page-one",
        action="store_false",
        dest="fallback_to_page_one",
        help="Disable retrying page 1 when the rotated page has no listings.",
    )
    args = parser.parse_args()
    if args.max_districts < 1 or args.max_categories < 1:
        parser.error("--max-districts and --max-categories must be positive")
    if args.limit_per_group < 1:
        parser.error("--limit-per-group must be positive")
    if args.page is not None and args.page < 1:
        parser.error("--page must be positive")
    return args


class NhatotDiscoveryFixtureTest(unittest.TestCase):
    def test_fixture_extraction_matches_adapter_baseline(self):
        fixture = ROOT / "tests" / "fixtures" / "nhatot" / "list_page_sample.html"
        html = fixture.read_text(encoding="utf-8")
        district = {"name": "Cau Giay", "slug": "quan-cau-giay"}
        category = {
            "name": "Can ho",
            "slug": "mua-ban-can-ho-chung-cu",
            "category_id": 1010,
            "property_type_group": "apartment",
        }

        discovery_rows = parse_listing_rows(
            html=html,
            page_url=build_page_url(district, category, 1),
            district=district,
            category=category,
            page=1,
            limit=2,
        )
        adapter_rows = NhatotAdapter().parse_list_page(html)

        self.assertEqual(len(discovery_rows), 2)
        self.assertEqual(len(adapter_rows), 2)
        self.assertEqual(adapter_rows[0]["source"], "nhatot")
        self.assertEqual(discovery_rows[0]["listing_id"], adapter_rows[0]["listing_id"])
        self.assertEqual(discovery_rows[0]["title_raw"], adapter_rows[0]["listing_card_title"])


if __name__ == "__main__":
    asyncio.run(run(parse_args()))
