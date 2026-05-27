import re
from typing import Dict, Any, Optional

from ...normalizers import (
    clean_text,
    normalize_price,
    normalize_area,
    calculate_unit_price,
    calculate_total_price,
    normalize_property_type,
)
from common.utils import now_utc_iso


def find_first_pattern(text: str, patterns: list[str]) -> Optional[str]:
    """
    Tìm giá trị đầu tiên match theo danh sách regex pattern.
    """
    if not text:
        return None

    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE | re.MULTILINE)
        if match:
            value = match.group(1).strip()
            return clean_text(value)

    return None


def extract_title(raw_text: str, metadata: Dict[str, Any]) -> Optional[str]:
    """
    Lấy title.
    Ưu tiên metadata nếu có.
    """
    for key in ["title", "listing_title", "title_raw"]:
        if metadata.get(key):
            return clean_text(metadata.get(key))

    lines = [line.strip() for line in raw_text.splitlines() if line.strip()]

    # Heuristic đơn giản: title thường nằm ở những dòng đầu
    for line in lines[:20]:
        if len(line) >= 15 and not line.lower().startswith(("mức giá", "diện tích", "địa chỉ")):
            return clean_text(line)

    return None


def extract_price_raw(raw_text: str, metadata: Dict[str, Any]) -> Optional[str]:
    """
    Lấy giá raw từ Batdongsan.

    Hỗ trợ:
    - Khoảng giá
      10,2 tỷ
    - Khoảng giá 10,2 tỷ ~81,93 triệu/m² Diện tích ...
    - Khoảng giá Thỏa thuận Diện tích ...
    """

    for key in ["price", "price_raw", "gia", "muc_gia"]:
        if metadata.get(key):
            return clean_text(metadata.get(key))

    if not raw_text:
        return None

    text = clean_text(raw_text) or ""

    # Case 1: raw_text có nhiều dòng đẹp
    lines = [line.strip() for line in raw_text.splitlines() if line.strip()]

    for i, line in enumerate(lines):
        line_lower = line.lower()

        if line_lower in ["khoảng giá", "mức giá"]:
            for next_line in lines[i + 1 : i + 5]:
                next_lower = next_line.lower()

                if (
                    "thỏa thuận" in next_lower
                    or "thoả thuận" in next_lower
                    or re.search(r"\d+(?:[.,]\d+)?\s*(tỷ|ty|triệu|trieu)", next_lower)
                ):
                    return clean_text(next_line)

        if line_lower.startswith("khoảng giá ") or line_lower.startswith("mức giá "):
            value = re.sub(r"^(khoảng giá|mức giá)\s*", "", line, flags=re.IGNORECASE).strip()
            if value:
                return clean_text(value)

    # Case 2: raw_text bị dính thành 1 dòng dài
    patterns = [
        r"(?:Khoảng giá|Mức giá)\s+(Thỏa thuận|Thoả thuận)",
        r"(?:Khoảng giá|Mức giá)\s+(\d+(?:[.,]\d+)?\s*(?:tỷ|ty|triệu|trieu))",
    ]

    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return clean_text(match.group(1))

    # Case 3: fallback từ mô tả/title, ví dụ "giá chỉ 10.2 tỷ", "3,799tỷ"
    fallback_patterns = [
        r"(?:giá chỉ|giá bán|giá)\s+(\d+(?:[.,]\d+)?\s*(?:tỷ|ty|triệu|trieu))",
        r"(\d+(?:[.,]\d+)?\s*(?:tỷ|ty))",
    ]

    for pattern in fallback_patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return clean_text(match.group(1))

    return None


def extract_area_raw(raw_text: str, metadata: Dict[str, Any]) -> Optional[str]:
    """
    Lấy diện tích raw.

    Hỗ trợ:
    - Diện tích
      124,5 m²
    - Diện tích 124,5 m² Phòng ngủ ...
    - DT 80m²
    """

    for key in ["area", "area_raw", "dien_tich"]:
        if metadata.get(key):
            return clean_text(metadata.get(key))

    if not raw_text:
        return None

    text = clean_text(raw_text) or ""

    # Case 1: raw_text có nhiều dòng
    lines = [line.strip() for line in raw_text.splitlines() if line.strip()]

    for i, line in enumerate(lines):
        line_lower = line.lower()

        if line_lower in ["diện tích", "dien tich"]:
            for next_line in lines[i + 1 : i + 4]:
                match = re.search(r"(\d+(?:[.,]\d+)?\s*m(?:²|2)?)", next_line, flags=re.IGNORECASE)
                if match:
                    return clean_text(match.group(1))

        if line_lower.startswith("diện tích ") or line_lower.startswith("dien tich "):
            match = re.search(
                r"diện tích\s+(\d+(?:[.,]\d+)?\s*m(?:²|2)?)", line, flags=re.IGNORECASE
            )
            if match:
                return clean_text(match.group(1))

    # Case 2: raw_text bị dính thành 1 dòng dài
    patterns = [
        r"Diện tích\s+(\d+(?:[.,]\d+)?\s*m(?:²|2)?)",
        r"Dien tich\s+(\d+(?:[.,]\d+)?\s*m(?:²|2)?)",
        r"\bDT\s+(\d+(?:[.,]\d+)?\s*m(?:²|2)?)",
        r"\bDT\s*(\d+(?:[.,]\d+)?\s*m(?:²|2)?)",
    ]

    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return clean_text(match.group(1))

    return None


def extract_location_raw(raw_text: str, metadata: Dict[str, Any]) -> tuple[Optional[str], str, str]:
    """
    Lấy location raw.

    Return:
    - location_raw
    - location_parse_method
    - location_confidence
    """

    # 1. Ưu tiên field có vẻ là địa chỉ thật trong metadata
    for key in ["address", "location", "location_raw", "detail_location_raw"]:
        if metadata.get(key):
            return clean_text(metadata.get(key)), "metadata_field", "high"

    # 2. Tìm trong raw_text
    patterns = [
        r"Địa chỉ\s*[:\-]?\s*([^\n\r]+)",
        r"Khu vực\s*[:\-]?\s*([^\n\r]+)",
        r"Vị trí\s*[:\-]?\s*([^\n\r]+)",
    ]

    location = find_first_pattern(raw_text, patterns)
    if location:
        return location, "detail_text_field", "high"

    # 3. Fallback từ crawl context
    district = metadata.get("crawl_district_label") or metadata.get("crawl_district")
    city = metadata.get("crawl_city_label") or metadata.get("crawl_city")

    fallback_parts = [part for part in [district, city] if part]

    if fallback_parts:
        return ", ".join(fallback_parts), "crawl_context", "medium"

    return None, "unknown", "unknown"


def normalize_location_simple(location_raw: Optional[str], metadata: Dict[str, Any]) -> dict:
    """
    Chuẩn hóa location bản đơn giản.
    Phase 2 bản đầu chưa cần quá phức tạp.
    """
    result = {
        "city_raw": None,
        "district_raw": None,
        "ward_raw": None,
        "street_raw": None,
        "project_raw": None,
        "city_norm": None,
        "district_norm": None,
        "ward_norm": None,
    }

    # Ưu tiên crawl context vì config của bạn đã biết city/district
    city = metadata.get("crawl_city_label") or metadata.get("crawl_city")
    district = metadata.get("crawl_district_label") or metadata.get("crawl_district")

    result["city_raw"] = clean_text(city)
    result["district_raw"] = clean_text(district)

    if city:
        city_text = str(city).lower()
        if "ha-noi" in city_text or "hà nội" in city_text or "ha noi" in city_text:
            result["city_norm"] = "Hà Nội"
        else:
            result["city_norm"] = clean_text(city)

    if district:
        result["district_norm"] = clean_text(district)

    # Nếu metadata không có thì thử tìm trong location_raw
    if location_raw and not result["city_norm"]:
        if "hà nội" in location_raw.lower() or "ha noi" in location_raw.lower():
            result["city_norm"] = "Hà Nội"

    return result


def extract_posted_date_raw(raw_text: str, metadata: Dict[str, Any]) -> Optional[str]:
    """
    Lấy ngày đăng raw nếu có.
    """
    for key in ["posted_date", "posted_date_raw", "ngay_dang"]:
        if metadata.get(key):
            return clean_text(metadata.get(key))

    patterns = [
        r"Ngày đăng\s*[:\-]?\s*([^\n\r]+)",
        r"Đăng ngày\s*[:\-]?\s*([^\n\r]+)",
    ]

    return find_first_pattern(raw_text, patterns)


def extract_bedroom_count(raw_text: str) -> Optional[int]:
    patterns = [
        r"(\d+)\s*phòng ngủ",
        r"Phòng ngủ\s*[:\-]?\s*(\d+)",
    ]

    value = find_first_pattern(raw_text, patterns)
    if value:
        try:
            return int(value)
        except ValueError:
            return None

    return None


def extract_bathroom_count(raw_text: str) -> Optional[int]:
    patterns = [
        r"(\d+)\s*phòng tắm",
        r"(\d+)\s*toilet",
        r"Phòng tắm\s*[:\-]?\s*(\d+)",
        r"Toilet\s*[:\-]?\s*(\d+)",
    ]

    value = find_first_pattern(raw_text, patterns)
    if value:
        try:
            return int(value)
        except ValueError:
            return None

    return None


def parse_listing(
    raw_html: str,
    raw_text: str,
    metadata: Dict[str, Any],
    parser_version: str = "phase2_v1",
) -> Dict[str, Any]:
    """
    Parse một listing từ Bronze sang record Silver.
    """

    title_raw = extract_title(raw_text, metadata)
    price_raw = extract_price_raw(raw_text, metadata)
    area_raw = extract_area_raw(raw_text, metadata)

    location_raw, location_parse_method, location_confidence = extract_location_raw(
        raw_text=raw_text, metadata=metadata
    )

    price_info = normalize_price(price_raw)
    area_info = normalize_area(area_raw)

    price_unit = price_info.get("price_unit")
    price_vnd_raw = price_info.get("price_vnd")
    area_m2 = area_info.get("area_m2")

    price_vnd = calculate_total_price(
        price_vnd=price_vnd_raw, area_m2=area_m2, price_unit=price_unit
    )

    unit_price_vnd_m2 = calculate_unit_price(
        price_vnd=price_vnd_raw, area_m2=area_m2, price_unit=price_unit
    )

    location_info = normalize_location_simple(location_raw, metadata)

    crawl_category = metadata.get("crawl_category")
    property_type_group = metadata.get("property_type_group") or normalize_property_type(
        category=crawl_category, title=title_raw
    )

    record = {
        # Identity / lineage
        "source": metadata.get("source"),
        "crawl_date": metadata.get("crawl_date"),
        "crawl_id": metadata.get("crawl_id"),
        "listing_id": metadata.get("listing_id"),
        "listing_url": metadata.get("listing_url"),
        # Raw fields
        "title_raw": title_raw,
        "description_raw": clean_text(raw_text[:3000]) if raw_text else None,
        "price_raw": price_raw,
        "area_raw": area_raw,
        "location_raw": location_raw,
        # Normalized price / area
        "price_value": price_info.get("price_value"),
        "price_unit": price_unit,
        "price_vnd": price_vnd,
        "area_m2": area_m2,
        "unit_price_vnd_m2": unit_price_vnd_m2,
        # Property type
        "property_type_raw": crawl_category,
        "property_type_group": property_type_group,
        "listing_business_type": metadata.get("listing_business_type"),
        # Location
        "city_raw": location_info.get("city_raw"),
        "district_raw": location_info.get("district_raw"),
        "ward_raw": location_info.get("ward_raw"),
        "street_raw": location_info.get("street_raw"),
        "project_raw": location_info.get("project_raw"),
        "city_norm": location_info.get("city_norm"),
        "district_norm": location_info.get("district_norm"),
        "ward_norm": location_info.get("ward_norm"),
        "location_confidence": location_confidence,
        "location_parse_method": location_parse_method,
        # Optional attributes
        "bedroom_count": extract_bedroom_count(raw_text),
        "bathroom_count": extract_bathroom_count(raw_text),
        "floor_count": None,
        # Seller metadata - Phase 2 giữ từ metadata nếu có
        "seller_type": metadata.get("seller_type"),
        "seller_years_on_platform": metadata.get("seller_years_on_platform"),
        "seller_active_listing_count": metadata.get("seller_active_listing_count"),
        "has_broker_certificate": metadata.get("has_broker_certificate"),
        "phone_masked": metadata.get("phone_masked"),
        # Image metadata
        "image_count": metadata.get("image_count"),
        "has_image": metadata.get("has_image"),
        # Dates
        "posted_date_raw": extract_posted_date_raw(raw_text, metadata),
        "expired_date_raw": metadata.get("expired_date_raw"),
        "posted_date": None,
        "expired_date": None,
        # Parse status
        "parse_status": "success",
        "parse_error_message": None,
        # Lineage paths
        "raw_html_path": metadata.get("raw_html_path"),
        "raw_text_path": metadata.get("raw_text_path"),
        "metadata_path": metadata.get("metadata_path"),
        "parser_version": parser_version,
        "processed_at": now_utc_iso(),
    }

    return record
