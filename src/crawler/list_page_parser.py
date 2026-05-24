import re
from urllib.parse import urljoin

from parsing.normalizers import clean_text


def parse_listing_card_old_district(location_raw: str | None) -> str | None:
    if not location_raw:
        return None
    match = re.search(r"\(([^)]*(?:cu|cũ)[^)]*)\)", location_raw, flags=re.IGNORECASE)
    return clean_text(match.group(1)) if match else None


def extract_listing_entries_from_listing_page(html: str) -> list[dict]:
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html or "", "lxml")
    entries_by_url = {}

    cards = soup.select(".js__card-listing")
    if not cards:
        cards = [
            a.parent
            for a in soup.find_all("a", href=True)
            if "pr" in (a.get("href") or "")
        ]

    for card in cards:
        if not card:
            continue

        link = card.select_one("a[href*='pr'][href*='ban-']") or card.find(
            "a", href=True
        )
        href = (link.get("href") or "").strip() if link else ""
        if not href:
            continue

        absolute = urljoin("https://batdongsan.com.vn", href)
        if "batdongsan.com.vn" not in absolute or not re.search(r"pr\d+", absolute):
            continue

        title_el = card.select_one(".js__card-title, .pr-title, .re__card-title")
        price_el = card.select_one(".re__card-config-price")
        area_el = card.select_one(".re__card-config-area")
        location_el = card.select_one(".re__card-location")
        description_el = card.select_one(".js__card-description, .re__card-description")

        location_raw = (
            clean_text(location_el.get_text(" ", strip=True)) if location_el else None
        )
        entry = {
            "listing_url": absolute,
            "listing_card_title": (
                clean_text(title_el.get_text(" ", strip=True)) if title_el else None
            ),
            "listing_card_price_raw": (
                clean_text(price_el.get_text(" ", strip=True)) if price_el else None
            ),
            "listing_card_area_raw": (
                clean_text(area_el.get_text(" ", strip=True)) if area_el else None
            ),
            "listing_card_location_raw": location_raw,
            "listing_card_old_district_raw": parse_listing_card_old_district(
                location_raw
            ),
            "listing_card_description": (
                clean_text(description_el.get_text(" ", strip=True))
                if description_el
                else None
            ),
        }
        entries_by_url.setdefault(absolute, entry)

    return list(entries_by_url.values())


def extract_listing_urls_from_listing_page(html: str) -> list[str]:
    return [
        entry["listing_url"]
        for entry in extract_listing_entries_from_listing_page(html)
    ]
