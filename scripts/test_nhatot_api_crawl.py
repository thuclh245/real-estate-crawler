import sys
import time
import requests
import json
from typing import Callable

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Harvested mapping for Hà Nội
DISTRICT_MAPPING = {
    "quan-ba-dinh": 74,
    "quan-bac-tu-liem": 129,
    "quan-cau-giay": 79,
    "quan-dong-da": 75,
    "quan-ha-dong": 86,
    "quan-hai-ba-trung": 76,
    "quan-hoan-kiem": 73,
    "quan-hoang-mai": 80,
    "quan-long-bien": 81,
    "quan-nam-tu-liem": 121,
    "quan-tay-ho": 78,
    "quan-thanh-xuan": 77
}

CATEGORY_MAPPING = {
    "mua-ban-can-ho-chung-cu": 1010,
    "mua-ban-nha-dat": 1020
}

# Global in-memory cache for listing details
IN_MEMORY_AD_CACHE = {}

def clean_text(value):
    if value is None:
        return None
    return " ".join(str(value).split()).strip() or None

class NhatotApiAdapter:
    source_code = "nhatot"
    
    def build_seed_urls(self, config: dict) -> list[str]:
        urls = []
        targets = config.get("targets", [])
        max_pages = config.get("crawl_settings", {}).get("max_pages_per_target", 1)
        
        for target in targets:
            category_slug = target.get("category")
            location_slug = target.get("location_slug")
            
            cg_id = CATEGORY_MAPPING.get(category_slug, 1000)
            area_id = DISTRICT_MAPPING.get(location_slug)
            
            if not area_id:
                print(f"[WARNING] Location slug {location_slug} not found in district mapping!")
                continue
                
            for page in range(1, max_pages + 1):
                api_url = f"https://gateway.chotot.com/v1/public/ad-listing?cg={cg_id}&region=12&area={area_id}&page={page}&limit=5"
                urls.append(api_url)
        return urls

    def parse_list_page(self, html: str) -> list[dict]:
        try:
            data = json.loads(html)
            ads = data.get("ads", [])
            normalized_ads = []
            
            for ad in ads:
                ad_id = ad.get("ad_id") or ad.get("list_id")
                category_slug = ad.get("category_slug") or "mua-ban-nha-dat"
                location_slug = ad.get("location_slug") or "viet-nam"
                
                # Mock URL that we will intercept in our custom fetcher
                mock_url = f"https://www.nhatot.com/detail-mock/{ad_id}"
                
                # Store the complete ad dictionary in our global cache
                IN_MEMORY_AD_CACHE[mock_url] = json.dumps(ad)
                
                # Public web URL for final storage/audit
                web_url = f"https://www.nhatot.com/{category_slug}-{location_slug}/{ad_id}.htm"
                
                parts = [ad.get("ward_name"), ad.get("area_name"), ad.get("region_name")]
                location_raw = ", ".join(str(part) for part in parts if part)
                
                normalized = {
                    "source": "nhatot",
                    "source_code": "nhatot",
                    "listing_id": str(ad_id),
                    "listing_url": mock_url,       # Point to mock URL for orchestrator fetching
                    "web_url": web_url,           # Real public URL for final storage
                    "listing_card_title": clean_text(ad.get("subject")),
                    "listing_card_price_raw": clean_text(ad.get("price_string")),
                    "listing_card_area_raw": f"{ad.get('size')} m²" if ad.get('size') else None,
                    "listing_card_location_raw": clean_text(location_raw),
                    "listing_card_description": clean_text(ad.get("body")),
                    "property_type_group": clean_text(ad.get("property_type_group")),
                    "city_raw": clean_text(ad.get("region_name")),
                    "district_raw": clean_text(ad.get("area_name")),
                    "ward_raw": clean_text(ad.get("ward_name")),
                    "bedroom_count": ad.get("rooms"),
                    "bathroom_count": ad.get("toilets"),
                    "price_vnd": ad.get("price"),
                    "area_m2": ad.get("size"),
                }
                normalized_ads.append(normalized)
            return normalized_ads
        except Exception as e:
            print(f"[ERROR] Failed to parse API listing page: {e}")
            return []

    def parse_detail_page(self, html: str) -> dict:
        try:
            ad = json.loads(html)
            title = clean_text(ad.get("subject"))
            address = clean_text(ad.get("street_name"))
            city = clean_text(ad.get("region_name"))
            district = clean_text(ad.get("area_name"))
            ward = clean_text(ad.get("ward_name"))
            breadcrumb = " / ".join(part for part in [city, district, ward] if part) or None
            
            return {
                "detail_title": title,
                "detail_address_raw": address,
                "breadcrumb_raw": breadcrumb,
                "breadcrumb_location_raw": breadcrumb,
                "detail_description": clean_text(ad.get("body")),
            }
        except Exception as e:
            print(f"[ERROR] Failed to parse API detail page: {e}")
            return {}

# Define a custom fetcher that intercepts mock detail URLs
def custom_fetch_with_retry(
    url: str,
    mode: str,
    max_retries: int,
    retry_delay_seconds: float,
) -> tuple[int | None, str, str | None, int, str | None]:
    
    # INTERCEPT MOCK URLs from cache
    if url.startswith("https://www.nhatot.com/detail-mock/"):
        if url in IN_MEMORY_AD_CACHE:
            # Instant cache hit, no network call!
            cached_json = IN_MEMORY_AD_CACHE[url]
            return 200, cached_json, url, 0, None
        else:
            return 404, "", url, 0, "Mock URL not found in cache"
            
    # Standard network call for real API listing URLs
    headers = {
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 Chotot/4.5.0",
        "Accept": "application/json, text/plain, */*",
        "X-Chotot-Platform": "IOS",
        "X-Chotot-Region": "VN",
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=15)
        return response.status_code, response.text, response.url, 0, None
    except Exception as e:
        return None, "", url, 0, str(e)

def test_full_flow():
    # Simulate a small smoke crawl on Ba Dinh (quan-ba-dinh)
    config = {
        "source": "nhatot",
        "crawl_settings": {
            "max_pages_per_target": 1,
            "max_listings_per_target": 3,
        },
        "targets": [
            {
                "business_type": "sale",
                "category": "mua-ban-can-ho-chung-cu",
                "location_slug": "quan-ba-dinh",
            }
        ]
    }
    
    adapter = NhatotApiAdapter()
    
    print("\n--- Phase 1: Generating and fetching seed URLs ---")
    seed_urls = adapter.build_seed_urls(config)
    print(f"Seed URLs generated: {seed_urls}")
    
    # 1. Fetch listing JSON via custom fetcher
    print(f"Fetching listing API: {seed_urls[0]}")
    status, html_content, final_url, attempts, err = custom_fetch_with_retry(
        seed_urls[0], mode="api", max_retries=1, retry_delay_seconds=1
    )
    print(f"Status Code: {status}")
    
    # 2. Parse listing JSON
    listing_cards = adapter.parse_list_page(html_content)
    print(f"Parsed {len(listing_cards)} listings from JSON.")
    
    # Take first 3 listings
    listings_to_fetch = listing_cards[:3]
    
    print("\n--- Phase 2: Fetching and parsing detail pages (Mock Cache) ---")
    for idx, card in enumerate(listings_to_fetch):
        mock_detail_url = card["listing_url"]
        web_url = card["web_url"]
        
        print(f"\nListing {idx+1}:")
        print(f"  - Subject: {card['listing_card_title']}")
        print(f"  - Web URL: {web_url}")
        print(f"  - Mock Detail URL: {mock_detail_url}")
        
        # Fetch detail JSON (will hit cache instantly)
        start_time = time.perf_counter()
        detail_status, detail_html, _, _, _ = custom_fetch_with_retry(
            mock_detail_url, mode="api", max_retries=1, retry_delay_seconds=1
        )
        duration_ms = (time.perf_counter() - start_time) * 1000
        
        print(f"  - Fetch status: {detail_status} (Cache hit duration: {duration_ms:.2f} ms)")
        
        # Parse detail JSON
        detail_fields = adapter.parse_detail_page(detail_html)
        
        # Merge fields
        metadata = {
            **card,
            **detail_fields,
            "listing_url": web_url  # Point it back to web URL for final Bronze storage
        }
        
        print("  - Fully Reconstructed Metadata:")
        print(f"    * Title: {metadata['detail_title']}")
        print(f"    * Address/Street: {metadata['detail_address_raw']}")
        print(f"    * Price: {metadata['price_vnd']} VND ({metadata['listing_card_price_raw']})")
        print(f"    * Area: {metadata['area_m2']} m2")
        print(f"    * Location Match: {metadata['breadcrumb_raw']}")
        print(f"    * Description preview: {metadata['detail_description'][:80]}...")
        
    print("\n[SUCCESS] Custom Cache Mocking Integration Flow completed successfully!")

if __name__ == "__main__":
    test_full_flow()
