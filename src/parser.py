import re

from bs4 import BeautifulSoup

from utils import get_listing_id_or_hash


def html_to_text(html: str) -> str:
    """Convert raw HTML into normalized plain text for regex-based extraction."""
    soup = BeautifulSoup(html or "", "lxml")
    text = soup.get_text(" ", strip=True)
    return re.sub(r"\s+", " ", text).strip()


def _extract_first(text: str, patterns: list[str], default: str = "N/A") -> str:
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return match.group(1).strip()
    return default


def extract_basic_fields(detail_text: str, listing_url: str) -> dict:
    """Extract lightweight fields from listing text with safe fallbacks."""
    text = detail_text or ""
    return {
        "listing_id": get_listing_id_or_hash(listing_url),
        "price": _extract_first(text, [r"Gi[áa]\s*[:\-]?\s*([^\|\n\r]{2,80})"]),
        "area": _extract_first(text, [r"Di[ệe]n\s*t[íi]ch\s*[:\-]?\s*([^\|\n\r]{2,40})"]),
        "address": _extract_first(text, [r"[ĐD]ịa\s*ch[ỉi]\s*[:\-]?\s*([^\|\n\r]{2,120})"]),
        "title": _extract_first(text, [r"^(.{10,180})$"], default="N/A"),
    }
import re

def extract_basic_fields(text: str, url: str) -> dict:
    listing_id = extract_listing_id(url)

    # Lấy title đơn giản: dòng đầu có vẻ là tiêu đề
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    title = lines[0] if lines else None

    price_raw = None
    area_raw = None

    # Tìm giá đơn giản
    price_patterns = [
        r"(\d+[,.]?\d*)\s*tỷ",
        r"(\d+[,.]?\d*)\s*triệu",
        r"Thỏa thuận"
    ]

    for pattern in price_patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            price_raw = match.group(0)
            break

    # Tìm diện tích
    area_match = re.search(r"(\d+[,.]?\d*)\s*m²|\s*m2", text, flags=re.IGNORECASE)
    if area_match:
        area_raw = area_match.group(0)

    return {
        "listing_id": listing_id,
        "title_raw": title,
        "price_raw": price_raw,
        "area_raw": area_raw
    }

def extract_listing_id(url: str) -> str | None:
    match = re.search(r"pr(\d+)", url)
    if match:
        return match.group(1)
    return None