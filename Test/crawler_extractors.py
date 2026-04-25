import datetime as dt
import json
import re
from urllib.parse import urljoin, urlparse

from crawler_settings import BASE_URL


def normalize_space(value) -> str:
    """Collapse repeated whitespace and return fallback for empty values."""
    if not value:
        return "N/A"
    return re.sub(r"\s+", " ", str(value)).strip()


def extract_listing_links(html: str) -> list[str]:
    """Extract and filter listing detail links from a listing page HTML."""
    hrefs = re.findall(r'href=["\\\']([^"\\\']+)["\\\']', html or "", flags=re.IGNORECASE)
    filtered = []
    seen = set()

    for href in hrefs:
        if href.startswith("javascript:") or href.startswith("mailto:"):
            continue

        absolute = urljoin(BASE_URL, href)
        parsed = urlparse(absolute)
        if parsed.netloc and "batdongsan.com.vn" not in parsed.netloc:
            continue

        path = parsed.path.lower()
        if not re.search(r"-pr\d+", path):
            continue
        if not ("/ban-" in path or "/nha-dat-ban" in path):
            continue
        if any(ext in path for ext in [".css", ".js", ".png", ".jpg", ".jpeg", ".webp", ".svg"]):
            continue

        if absolute in seen:
            continue
        seen.add(absolute)
        filtered.append(absolute)

    return filtered


def listing_page_url(base_url: str, page_num: int) -> str:
    """Build URL for a paginated listing page."""
    if page_num <= 1:
        return base_url
    return f"{base_url}/p{page_num}"


def json_ld_candidates(html: str) -> list[dict]:
    """Collect JSON-LD blocks and parse valid dict candidates."""
    scripts = re.findall(
        r'<script[^>]*type=["\\\']application/ld\+json["\\\'][^>]*>(.*?)</script>',
        html or "",
        flags=re.IGNORECASE | re.DOTALL,
    )
    candidates = []

    for raw in scripts:
        data = raw.strip()
        if not data:
            continue
        try:
            parsed = json.loads(data)
        except json.JSONDecodeError:
            continue

        if isinstance(parsed, list):
            candidates.extend([x for x in parsed if isinstance(x, dict)])
        elif isinstance(parsed, dict):
            candidates.append(parsed)

    return candidates


def pick_price_from_jsonld(item: dict) -> str | None:
    """Extract price text from JSON-LD offers section when available."""
    offers = item.get("offers")
    if isinstance(offers, dict):
        price = offers.get("price")
        currency = offers.get("priceCurrency")
        if price is not None:
            return f"{price} {currency}" if currency else str(price)
    return None


def extract_number(text: str, pattern: str) -> str:
    """Extract first regex group from text or return fallback value."""
    match = re.search(pattern, text or "", flags=re.IGNORECASE)
    return normalize_space(match.group(1)) if match else "N/A"


def extract_listing_id(url: str) -> str:
    """Extract listing numeric id from URL suffix pattern -pr<id>."""
    match = re.search(r"-pr(\d+)", url)
    return match.group(1) if match else "N/A"


def best_jsonld_candidate(candidates: list[dict]) -> dict | None:
    """Pick the best JSON-LD object for listing data extraction."""

    def score(item: dict) -> int:
        value = 0
        item_type = str(item.get("@type", "")).lower()

        if "breadcrumb" in item_type:
            value -= 5
        if "article" in item_type or "residence" in item_type or "product" in item_type or "offer" in item_type:
            value += 3
        if item.get("offers"):
            value += 3
        if item.get("address"):
            value += 2
        if item.get("description"):
            value += 1
        if item.get("name"):
            value += 1

        return value

    if not candidates:
        return None
    return sorted(candidates, key=score, reverse=True)[0]


def guess_district_from_url(url: str) -> str:
    """Infer district name from URL slug when available."""
    path = urlparse(url).path.lower()
    district_matches = re.findall(r"-quan-([a-z0-9-]+)", path)
    if district_matches:
        return district_matches[0].replace("-", " ").title()
    return "N/A"


def guess_city_from_url(url: str) -> str:
    """Infer city slug from listing URL root pattern."""
    path = urlparse(url).path.lower()
    match = re.search(r"nha-dat-ban-([a-z0-9-]+)", path)
    if not match:
        return "N/A"

    slug = match.group(1)
    slug = re.sub(r"-quan-[a-z0-9-]+", "", slug)
    slug = re.sub(r"-huyen-[a-z0-9-]+", "", slug)
    slug = re.sub(r"-thi-xa-[a-z0-9-]+", "", slug)
    slug = re.sub(r"-thanh-pho-[a-z0-9-]+", "", slug)
    slug = re.sub(r"-tp-[a-z0-9-]+", "", slug)
    slug = slug.strip("-")

    return slug.replace("-", " ").title() if slug else "N/A"


def parse_detail(html: str, url: str) -> dict:
    """Parse one listing detail page into normalized output schema."""
    guessed_city = guess_city_from_url(url)
    guessed_district = guess_district_from_url(url)
    result = {
        "source": "batdongsan.com.vn",
        "scraped_at": dt.datetime.now(dt.UTC).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "title": "N/A",
        "description": "N/A",
        "city": guessed_city,
        "district": guessed_district,
        "ward": "N/A",
        "price": "N/A",
        "price_raw": "N/A",
        "address": "N/A",
        "property_size": "N/A",
        "property_size_raw": "N/A",
        "property_type": "N/A",
        "bedrooms": "N/A",
        "bathrooms": "N/A",
        "amenities": "",
        "currency": "VND",
        "listing_id": extract_listing_id(url),
        "crawl_status": "ok",
        "listing_url": url,
    }

    candidates = json_ld_candidates(html)
    best = best_jsonld_candidate(candidates)

    if best:
        name = best.get("name")
        if name:
            result["title"] = normalize_space(name)

        description = best.get("description")
        if description:
            result["description"] = normalize_space(description)

        address = best.get("address")
        if isinstance(address, dict):
            addr = address.get("streetAddress") or address.get("addressLocality")
            if addr:
                result["address"] = normalize_space(addr)

        prop_type = best.get("category")
        if prop_type:
            result["property_type"] = normalize_space(prop_type)

    for item in candidates:
        price = pick_price_from_jsonld(item)
        if price and result["price_raw"] == "N/A":
            result["price_raw"] = normalize_space(price)
            result["price"] = normalize_space(price)

        floor_size = item.get("floorSize")
        if isinstance(floor_size, dict):
            value = floor_size.get("value")
            unit = floor_size.get("unitCode")
            if value is not None and result["property_size"] == "N/A":
                size = normalize_space(f"{value} {unit or ''}")
                result["property_size"] = size
                result["property_size_raw"] = size

    text = normalize_space(re.sub(r"<[^>]+>", " ", html or ""))

    if result["price_raw"] == "N/A":
        price_match = re.search(r"(\d+[\d\.,]*)\s*(ty|trieu|nghin|tỷ|triệu)", text, flags=re.IGNORECASE)
        if price_match:
            price_text = normalize_space(" ".join(price_match.groups()))
            result["price_raw"] = price_text
            result["price"] = price_text

    if result["property_size_raw"] == "N/A":
        size_match = re.search(r"(\d+[\d\.,]*)\s*(m2|m²)", text, flags=re.IGNORECASE)
        if size_match:
            size_text = normalize_space(" ".join(size_match.groups()))
            result["property_size_raw"] = size_text
            result["property_size"] = size_text

    if result["title"] == "N/A":
        title_match = re.search(r"<title>(.*?)</title>", html or "", flags=re.IGNORECASE | re.DOTALL)
        if title_match:
            result["title"] = normalize_space(title_match.group(1))

    result["bedrooms"] = extract_number(text, r"(\d+)\s*(phong ngu|phòng ngủ)")
    result["bathrooms"] = extract_number(text, r"(\d+)\s*(wc|phong tam|phòng tắm)")

    if result["property_type"] == "N/A":
        lower_path = urlparse(url).path.lower()
        if "/ban-can-ho-chung-cu" in lower_path:
            result["property_type"] = "Apartment"
        elif "/ban-nha-rieng" in lower_path:
            result["property_type"] = "Private house"
        elif "/ban-nha-mat-pho" in lower_path:
            result["property_type"] = "Townhouse"
        elif "/ban-dat" in lower_path:
            result["property_type"] = "Land"

    return result
