import hashlib
import re
from typing import Dict, Any, Optional
from datetime import datetime, timezone

from crawler.parsing.normalizers import (
    clean_text,
    normalize_price,
    normalize_area,
    calculate_unit_price,
    calculate_total_price,
    normalize_property_type,
    normalize_posted_date,
    extract_project_from_location,
    normalize_floor_count,
    normalize_direction,
    normalize_legal_status,
    normalize_furniture,
)

SILVER_SCHEMA_VERSION = "v1.1"


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def find_first_pattern(text: str, patterns: list[str]) -> Optional[str]:
    if not text:
        return None
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE | re.MULTILINE)
        if match:
            value = match.group(1).strip()
            return clean_text(value)
    return None


def extract_section(text: str, section_name: str, end_markers: list[str] | None = None) -> Optional[str]:
    """Trích xuất nội dung của một section trong text Batdongsan."""
    if not text or not section_name:
        return None

    default_end_markers = [
        "Thông tin dự án",
        "Xem thêm",
        "Lịch sử giá",
        "Thông tin mô tả",
        "Xem trang cá nhân",
        "Ngày đăng",
        "Mã tin",
        "Hình ảnh",
        "Bản đồ",
        "Tính lãi suất",
    ]
    markers = end_markers or default_end_markers

    start_pattern = re.escape(section_name)
    match = re.search(start_pattern, text)
    if not match:
        return None

    start_pos = match.end()

    end_positions = []
    for marker in markers:
        if marker == section_name:
            continue
        end_match = re.search(re.escape(marker), text[start_pos:])
        if end_match:
            end_positions.append(start_pos + end_match.start())

    end_pos = min(end_positions) if end_positions else min(start_pos + 500, len(text))

    return text[start_pos:end_pos].strip()


def extract_title(raw_text: str, metadata: Dict[str, Any]) -> Optional[str]:
    # Uu tien metadata title da duoc BeautifulSoup extract san
    for key in ["title", "listing_title", "detail_title"]:
        val = metadata.get(key)
        if val:
            return clean_text(val)

    # Fallback: listing_card_title
    val = metadata.get("listing_card_title")
    if val:
        return clean_text(val)

    return None


def extract_description(raw_text: str, metadata: Dict[str, Any]) -> Optional[str]:
    """Lay mo ta thuc su, uu tien metadata description da duoc extract tu HTML."""
    # metadata description da duoc parse_detail_page_location_fields extract
    # tu .re__section-body, la mo ta sach
    desc = metadata.get("description") or metadata.get("detail_description")
    if desc:
        desc = clean_text(desc)
        if desc and len(desc) >= 15:
            return desc[:2000]

    # Fallback: extract tu raw_text
    if raw_text:
        section = extract_section(raw_text, "Thông tin mô tả")
        if section:
            section = clean_text(section)
            if section and len(section) >= 15:
                return section[:2000]

    return None


def extract_price_raw(raw_text: str, metadata: Dict[str, Any]) -> Optional[str]:
    # Uu tien listing_card_price_raw (da co san tu crawl phase)
    for key in ["listing_card_price_raw"]:
        val = metadata.get(key)
        if val:
            return clean_text(val)

    for key in ["price", "price_raw", "gia", "muc_gia"]:
        if metadata.get(key):
            return clean_text(metadata.get(key))

    if not raw_text:
        return None

    text = clean_text(raw_text) or ""

    # Case: raw_text co nhieu dong
    lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
    for i, line in enumerate(lines):
        line_lower = line.lower()
        if line_lower in ["khoảng giá", "mức giá"]:
            for next_line in lines[i + 1:i + 5]:
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

    # Case: text bi dinh thanh 1 dong
    patterns = [
        r"(?:Khoảng giá|Mức giá)\s+(Thỏa thuận|Thoả thuận)",
        r"(?:Khoảng giá|Mức giá)\s+(\d+(?:[.,]\d+)?\s*(?:tỷ|ty|triệu|trieu))",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return clean_text(match.group(1))

    return None


def extract_area_raw(raw_text: str, metadata: Dict[str, Any]) -> Optional[str]:
    # Uu tien listing_card_area_raw
    for key in ["listing_card_area_raw"]:
        val = metadata.get(key)
        if val:
            return clean_text(val)

    for key in ["area", "area_raw", "dien_tich"]:
        if metadata.get(key):
            return clean_text(metadata.get(key))

    if not raw_text:
        return None

    text = clean_text(raw_text) or ""
    lines = [line.strip() for line in raw_text.splitlines() if line.strip()]

    for i, line in enumerate(lines):
        line_lower = line.lower()
        if line_lower in ["diện tích", "dien tich"]:
            for next_line in lines[i + 1:i + 4]:
                match = re.search(r"(\d+(?:[.,]\d+)?\s*m(?:²|2)?)", next_line, flags=re.IGNORECASE)
                if match:
                    return clean_text(match.group(1))

        if line_lower.startswith("diện tích ") or line_lower.startswith("dien tich "):
            match = re.search(r"diện tích\s+(\d+(?:[.,]\d+)?\s*m(?:²|2)?)", line, flags=re.IGNORECASE)
            if match:
                return clean_text(match.group(1))

    patterns = [
        r"Diện tích\s+(\d+(?:[.,]\d+)?\s*m(?:²|2)?)",
        r"\bDT\s+(\d+(?:[.,]\d+)?\s*m(?:²|2)?)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return clean_text(match.group(1))

    return None


def extract_location_raw(raw_text: str, metadata: Dict[str, Any]) -> tuple[Optional[str], str, str]:
    # Uu tien detail_address_raw tu crawl phase
    for key in ["detail_location_raw", "detail_address_raw", "address", "location", "location_raw"]:
        if metadata.get(key):
            return clean_text(metadata.get(key)), "metadata_field", "high"

    if not raw_text:
        return None, "unknown", "unknown"

    patterns = [
        r"Địa chỉ\s*[:\-]?\s*([^\n\r]+)",
        r"Khu vực\s*[:\-]?\s*([^\n\r]+)",
        r"Vị trí\s*[:\-]?\s*([^\n\r]+)",
    ]
    location = find_first_pattern(raw_text, patterns)
    if location:
        return location, "detail_text_field", "high"

    district = metadata.get("crawl_district_label") or metadata.get("crawl_district")
    city = metadata.get("crawl_city_label") or metadata.get("crawl_city")
    fallback_parts = [part for part in [district, city] if part]
    if fallback_parts:
        return ", ".join(fallback_parts), "crawl_context", "medium"

    return None, "unknown", "unknown"


def normalize_location_simple(location_raw: Optional[str], metadata: Dict[str, Any]) -> dict:
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

    city = metadata.get("crawl_city_label") or metadata.get("crawl_city")
    district = metadata.get("crawl_district_label") or metadata.get("crawl_district")

    result["city_raw"] = clean_text(city)
    result["district_raw"] = clean_text(district)

    if city:
        city_text = str(city).lower()
        if "ha-noi" in city_text or "hà nội" in city_text or "ha noi" in city_text:
            result["city_norm"] = "Hà Nội"
        elif "ho-chi-minh" in city_text or "hồ chí minh" in city_text:
            result["city_norm"] = "Hồ Chí Minh"
        else:
            result["city_norm"] = clean_text(city)

    if district:
        result["district_norm"] = clean_text(district)

    # Parse ward/street tu location_raw
    if location_raw:
        if not result["city_norm"]:
            if "hà nội" in location_raw.lower() or "ha noi" in location_raw.lower():
                result["city_norm"] = "Hà Nội"
            elif "hồ chí minh" in location_raw.lower() or "ho chi minh" in location_raw.lower():
                result["city_norm"] = "Hồ Chí Minh"

        # Try trich xuat phuong/xa
        ward_match = re.search(r"(?:Phường|Ph\.|P\.)\s*([^,]+)", location_raw)
        if ward_match:
            result["ward_raw"] = clean_text(ward_match.group(1))

        # Try trich xuat duong/pho
        street_match = re.search(r"(?:Đường|Đ\.)\s*([^,]+)", location_raw)
        if street_match:
            result["street_raw"] = clean_text(street_match.group(1))

    # Extract project name
    breadcrumb = metadata.get("breadcrumb_raw")
    project = extract_project_from_location(location_raw, breadcrumb)
    result["project_raw"] = project

    return result


def extract_bedroom_count(raw_text: str) -> Optional[int]:
    """Lay so phong ngu tu section Dac diem BDS."""
    if not raw_text:
        return None

    section = extract_section(raw_text, "Đặc điểm bất động sản")
    search_text = section if section else raw_text

    patterns = [
        r"Số phòng ngủ\s*\n?\s*(\d+)",
        r"(\d+)\s*phòng ngủ",
        r"Phòng ngủ\s*[:\-]?\s*(\d+)",
    ]

    for pattern in patterns:
        match = re.search(pattern, search_text, flags=re.IGNORECASE)
        if match:
            try:
                value = int(match.group(1))
                if 1 <= value <= 50:
                    return value
            except ValueError:
                continue

    return None


def extract_bathroom_count(raw_text: str) -> Optional[int]:
    """Lay so phong tam tu section Dac diem BDS."""
    if not raw_text:
        return None

    section = extract_section(raw_text, "Đặc điểm bất động sản")
    search_text = section if section else raw_text

    patterns = [
        r"Số phòng tắm[,\s]*vệ sinh\s*\n?\s*(\d+)",
        r"Số phòng tắm\s*\n?\s*(\d+)",
        r"(\d+)\s*phòng tắm",
        r"(\d+)\s*toilet",
        r"Phòng tắm\s*[:\-]?\s*(\d+)",
        r"Toilet\s*[:\-]?\s*(\d+)",
    ]

    for pattern in patterns:
        match = re.search(pattern, search_text, flags=re.IGNORECASE)
        if match:
            try:
                value = int(match.group(1))
                if 1 <= value <= 50:
                    return value
            except ValueError:
                continue

    return None


def extract_floor_count(raw_text: str) -> Optional[int]:
    """Lay so tang tu raw text."""
    if not raw_text:
        return None

    section = extract_section(raw_text, "Đặc điểm bất động sản")
    search_text = section if section else raw_text

    return normalize_floor_count(search_text)


def extract_direction(raw_text: str) -> Optional[str]:
    """Lay huong nha/ban cong tu raw text."""
    if not raw_text:
        return None

    section = extract_section(raw_text, "Đặc điểm bất động sản")
    search_text = section if section else raw_text

    patterns = [
        r"Hướng ban công\s*\n?\s*([^\n]+)",
        r"Hướng nhà\s*\n?\s*([^\n]+)",
        r"Hướng cửa chính\s*\n?\s*([^\n]+)",
    ]

    for pattern in patterns:
        match = re.search(pattern, search_text, flags=re.IGNORECASE)
        if match:
            value = match.group(1).strip()
            result = normalize_direction(value)
            if result:
                return result

    return None


def extract_legal_status(raw_text: str) -> Optional[str]:
    """Lay tinh trang phap ly."""
    if not raw_text:
        return None

    section = extract_section(raw_text, "Đặc điểm bất động sản")
    search_text = section if section else raw_text

    match = re.search(r"Pháp lý\s*\n?\s*([^\n]+)", search_text)
    if match:
        return normalize_legal_status(match.group(1).strip())

    return None


def extract_furniture_status(raw_text: str) -> Optional[str]:
    """Lay tinh trang noi that."""
    if not raw_text:
        return None

    section = extract_section(raw_text, "Đặc điểm bất động sản")
    search_text = section if section else raw_text

    match = re.search(r"Nội thất\s*\n?\s*([^\n]+)", search_text)
    if match:
        return normalize_furniture(match.group(1).strip())

    return None


def extract_posted_date_raw(raw_text: str, metadata: Dict[str, Any]) -> Optional[str]:
    for key in ["posted_date", "posted_date_raw", "ngay_dang"]:
        if metadata.get(key):
            return clean_text(metadata.get(key))

    if not raw_text:
        return None

    patterns = [
        r"Ngày đăng\s*\n?\s*(\d{1,2}[/-]\d{1,2}[/-]\d{4})",
        r"Đăng ngày\s*[:\-]?\s*([^\n\r]+)",
    ]

    return find_first_pattern(raw_text, patterns)


def extract_expired_date_raw(raw_text: str, metadata: Dict[str, Any]) -> Optional[str]:
    for key in ["expired_date", "expired_date_raw", "ngay_het_han"]:
        if metadata.get(key):
            return clean_text(metadata.get(key))

    if not raw_text:
        return None

    match = re.search(r"Ngày hết hạn\s*\n?\s*(\d{1,2}[/-]\d{1,2}[/-]\d{4})", raw_text)
    if match:
        return clean_text(match.group(1))

    return None


def extract_listing_type(raw_text: str, metadata: Dict[str, Any]) -> Optional[str]:
    """Loai tin: Tin VIP Bac, Tin thuong, etc."""
    for key in ["listing_type", "loai_tin"]:
        if metadata.get(key):
            return clean_text(metadata.get(key))

    if not raw_text:
        return None

    match = re.search(r"Loại tin\s*\n?\s*([^\n]+)", raw_text)
    if match:
        return clean_text(match.group(1))

    return None


def extract_seller_info(raw_text: str) -> dict:
    """Trich xuat thong tin nguoi ban tu raw_text."""
    result = {
        "is_broker": None,
        "phone_raw": None,
    }

    if not raw_text:
        return result

    # Kiem tra co phai moi gioi khong
    text_lower = raw_text.lower()
    for marker in ["môi giới", "moi gioi", "môi giới chuyên nghiệp"]:
        # Check xem co trong phan mo ta khong (khong phai navigation)
        desc_section = extract_section(raw_text, "Thông tin mô tả")
        if desc_section and marker in desc_section.lower():
            result["is_broker"] = True
            break

    # Trich so dien thoai (ca masked number voi ***)
    phone_patterns = [
        r"(?:LH|liên hệ|hotline|ĐT|SĐT|call|zalo)[\s:]*\n?[\s]*(\d[\d\s\.\*\-\,]{8,16})",
        r"(\d{4}[\s\.]\d{3,4}[\s\.][\*\d]{3,4})",
        r"(\d{3,4}[\s\.]\d{3,4}[\s\.]\d{3,4})",
    ]
    for pattern in phone_patterns:
        match = re.search(pattern, raw_text, flags=re.IGNORECASE)
        if match:
            phone = re.sub(r"\s+", " ", match.group(1)).strip()
            phone = re.sub(r"[\s\.\,\-\;]+$", "", phone)
            digits_only = re.sub(r"[^\d]", "", phone)
            if len(digits_only) >= 9 or (len(digits_only) >= 6 and "***" in phone):
                result["phone_raw"] = phone
                break

    return result


def compute_dedup_key(metadata: Dict[str, Any], title_raw: Optional[str],
                       district_norm: Optional[str], area_m2: Optional[float],
                       price_vnd: Optional[float]) -> dict:
    """Tao dedup_key o lop Silver, su dung cung thuat toan nhu silver_to_gold."""
    source = (metadata.get("source") or "unknown_source")
    listing_id = metadata.get("listing_id")
    listing_url = metadata.get("listing_url")

    # Priority 1: listing_id
    if listing_id:
        normalized_id = str(listing_id).strip()
        if normalized_id:
            key = f"{source}::{normalized_id}"
            return {"dedup_key": key, "dedup_method": "listing_id"}

    # Priority 2: listing_url (normalized)
    if listing_url:
        normalized_url = re.sub(r"^[^?#]+", "", str(listing_url).lower())
        normalized_url = re.sub(r"/+$", "", normalized_url)
        if str(listing_url).strip():
            key = f"{source}::{normalized_url}"
            return {"dedup_key": key, "dedup_method": "listing_url"}

    # Priority 3: content hash
    fallback_parts = [
        str(source),
        str(title_raw or "").lower().strip(),
        str(district_norm or "").lower().strip(),
        str(area_m2) if area_m2 else "",
        str(price_vnd) if price_vnd else "",
    ]
    fallback_string = "||".join(fallback_parts)
    fallback_hash = hashlib.sha256(fallback_string.encode("utf-8")).hexdigest()
    key = f"{source}::{fallback_hash}"
    return {"dedup_key": key, "dedup_method": "content_hash"}


def parse_listing(
    raw_html: str,
    raw_text: str,
    metadata: Dict[str, Any],
    parser_version: str = "phase2_v1"
) -> Dict[str, Any]:
    title_raw = extract_title(raw_text, metadata)
    description_raw = extract_description(raw_text, metadata)
    price_raw = extract_price_raw(raw_text, metadata)
    area_raw = extract_area_raw(raw_text, metadata)

    location_raw, location_parse_method, location_confidence = extract_location_raw(
        raw_text=raw_text,
        metadata=metadata
    )

    price_info = normalize_price(price_raw)
    area_info = normalize_area(area_raw)

    price_unit = price_info.get("price_unit")
    price_vnd_raw = price_info.get("price_vnd")
    area_m2 = area_info.get("area_m2")

    price_vnd = calculate_total_price(
        price_vnd=price_vnd_raw,
        area_m2=area_m2,
        price_unit=price_unit
    )

    unit_price_vnd_m2 = calculate_unit_price(
        price_vnd=price_vnd_raw,
        area_m2=area_m2,
        price_unit=price_unit
    )

    location_info = normalize_location_simple(location_raw, metadata)

    crawl_category = metadata.get("crawl_category")
    property_type_group = metadata.get("property_type_group") or normalize_property_type(
        category=crawl_category,
        title=title_raw
    )

    # Extract structured fields from raw_text
    bedroom_count = extract_bedroom_count(raw_text)
    bathroom_count = extract_bathroom_count(raw_text)
    floor_count = extract_floor_count(raw_text)
    direction = extract_direction(raw_text)
    legal_status = extract_legal_status(raw_text)
    furniture_status = extract_furniture_status(raw_text)
    posted_date_raw = extract_posted_date_raw(raw_text, metadata)
    expired_date_raw = extract_expired_date_raw(raw_text, metadata)
    listing_type = extract_listing_type(raw_text, metadata)
    seller_info = extract_seller_info(raw_text)

    posted_date = normalize_posted_date(posted_date_raw)
    expired_date = normalize_posted_date(expired_date_raw)

    # Compute dedup_key at silver level
    dedup_info = compute_dedup_key(
        metadata=metadata,
        title_raw=title_raw,
        district_norm=location_info.get("district_norm"),
        area_m2=area_m2,
        price_vnd=price_vnd,
    )

    record = {
        # Identity / lineage
        "silver_schema_version": SILVER_SCHEMA_VERSION,
        "source": metadata.get("source"),
        "crawl_date": metadata.get("crawl_date"),
        "crawl_id": metadata.get("crawl_id"),
        "listing_id": metadata.get("listing_id"),
        "listing_url": metadata.get("listing_url"),
        "dedup_key": dedup_info["dedup_key"],
        "dedup_method": dedup_info["dedup_method"],

        # Raw fields
        "title_raw": title_raw,
        "description_raw": description_raw,
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
        "bedroom_count": bedroom_count,
        "bathroom_count": bathroom_count,
        "floor_count": floor_count,
        "direction": direction,
        "legal_status": legal_status,
        "furniture_status": furniture_status,

        # Seller metadata
        "seller_type": metadata.get("seller_type"),
        "seller_years_on_platform": metadata.get("seller_years_on_platform"),
        "seller_active_listing_count": metadata.get("seller_active_listing_count"),
        "has_broker_certificate": metadata.get("has_broker_certificate"),
        "phone_masked": metadata.get("phone_masked"),
        "is_broker": seller_info.get("is_broker"),
        "phone_raw": seller_info.get("phone_raw"),
        "listing_type": listing_type,

        # Image metadata
        "image_count": metadata.get("image_count"),
        "has_image": metadata.get("has_image"),

        # Dates
        "posted_date_raw": posted_date_raw,
        "expired_date_raw": expired_date_raw,
        "posted_date": posted_date,
        "expired_date": expired_date,

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
