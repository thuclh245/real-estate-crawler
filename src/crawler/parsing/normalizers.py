import re
from datetime import datetime
from typing import Optional


def clean_text(value: Optional[str]) -> Optional[str]:
    """
    Chuẩn hóa text cơ bản:
    - None thì trả về None
    - Xóa khoảng trắng thừa
    """
    if value is None:
        return None

    value = str(value).strip()
    value = re.sub(r"\s+", " ", value)

    return value if value else None


def parse_vietnamese_number(text: str) -> Optional[float]:
    """
    Lấy số từ chuỗi tiếng Việt.
    Ví dụ:
    - '3.5 tỷ' -> 3.5
    - '3,5 tỷ' -> 3.5
    - '120 m²' -> 120
    """
    if not text:
        return None

    text = text.lower().strip()

    match = re.search(r"(\d+(?:[.,]\d+)?)", text)
    if not match:
        return None

    number_text = match.group(1).replace(",", ".")

    try:
        return float(number_text)
    except ValueError:
        return None


def normalize_price(price_raw: Optional[str]) -> dict:
    """
    Chuẩn hóa giá từ Batdongsan.

    Output:
    {
        "price_value": 3.5,
        "price_unit": "ty",
        "price_vnd": 3500000000
    }
    """
    price_raw = clean_text(price_raw)

    result = {
        "price_value": None,
        "price_unit": None,
        "price_vnd": None,
    }

    if not price_raw:
        return result

    text = price_raw.lower()

    if "thỏa thuận" in text or "thoả thuận" in text:
        result["price_unit"] = "negotiable"
        return result

    number = parse_vietnamese_number(text)
    if number is None:
        return result

    result["price_value"] = number

    if "tỷ" in text or "ty" in text:
        result["price_unit"] = "ty"
        result["price_vnd"] = int(number * 1_000_000_000)

    elif "triệu" in text or "trieu" in text:
        if "/m" in text or "m²" in text or "m2" in text:
            result["price_unit"] = "million_per_m2"
            result["price_vnd"] = int(number * 1_000_000)
        else:
            result["price_unit"] = "million"
            result["price_vnd"] = int(number * 1_000_000)

    elif "đ" in text or "vnd" in text:
        result["price_unit"] = "vnd"
        result["price_vnd"] = int(number)

    return result


def normalize_area(area_raw: Optional[str]) -> dict:
    """
    Chuẩn hóa diện tích.

    Output:
    {
        "area_m2": 35.0
    }
    """
    area_raw = clean_text(area_raw)

    result = {
        "area_m2": None
    }

    if not area_raw:
        return result

    number = parse_vietnamese_number(area_raw)

    if number is not None:
        result["area_m2"] = float(number)

    return result


def calculate_unit_price(
    price_vnd: Optional[int],
    area_m2: Optional[float],
    price_unit: Optional[str] = None
) -> Optional[float]:
    """
    Tính đơn giá VND/m2.

    Nếu price_unit là million_per_m2 thì price_vnd đang chính là đơn giá/m2.
    """
    if price_vnd is None:
        return None

    if price_unit == "million_per_m2":
        return float(price_vnd)

    if area_m2 is None or area_m2 <= 0:
        return None

    return float(price_vnd) / float(area_m2)

def calculate_total_price(
    price_vnd: Optional[int],
    area_m2: Optional[float],
    price_unit: Optional[str] = None
) -> Optional[int]:
    """
    Tính tổng giá VND.

    Nếu price_unit là million_per_m2 thì price_vnd đang là đơn giá/m2,
    cần nhân với diện tích để ra tổng giá.
    """
    if price_vnd is None:
        return None

    if price_unit == "million_per_m2":
        if area_m2 is None or area_m2 <= 0:
            return None
        return int(float(price_vnd) * float(area_m2))

    return int(price_vnd)


def normalize_property_type(category: Optional[str], title: Optional[str] = None) -> Optional[str]:
    """
    Chuẩn hóa loại bất động sản từ crawl_category hoặc title.
    """
    text = f"{category or ''} {title or ''}".lower()

    if "can-ho" in text or "chung cư" in text or "chung-cu" in text:
        return "apartment"

    if "nha-rieng" in text or "nhà riêng" in text:
        return "house"

    if "ban-dat" in text or "bán đất" in text:
        return "land"

    if "biet-thu" in text or "biệt thự" in text or "lien-ke" in text or "liền kề" in text:
        return "villa_townhouse"

    if "mat-pho" in text or "mặt phố" in text:
        return "street_house"

    return "unknown"


def normalize_posted_date(date_str: Optional[str]) -> Optional[str]:
    """
    Chuyển đổi ngày tháng tiếng Việt sang ISO 8601.
    Hỗ trợ: dd/mm/yyyy, dd-mm-yyyy, yyyy-mm-dd
    """
    if not date_str:
        return None

    date_str = str(date_str).strip()

    formats = [
        "%d/%m/%Y",
        "%d-%m-%Y",
        "%Y-%m-%d",
    ]

    for fmt in formats:
        try:
            parsed = datetime.strptime(date_str, fmt)
            return parsed.strftime("%Y-%m-%d")
        except ValueError:
            continue

    return None


def extract_project_from_location(location_raw: Optional[str], breadcrumb_raw: Optional[str] = None) -> Optional[str]:
    """
    Trích xuất tên dự án/khu đô thị từ location hoặc breadcrumb.
    Batdongsan format breadcrumb: "Bán / Hà Nội / Thanh Xuân / Căn hộ chung cư tại Khu nhà ở 90 Nguyễn Tuân"
    Location format: "Khu nhà ở 90 Nguyễn Tuân, Đường Nguyễn Tuân, Phường Thanh Xuân, Hà Nội"
    """
    if not location_raw and not breadcrumb_raw:
        return None

    candidates = []

    if breadcrumb_raw:
        match = re.search(r"tại\s+(.+?)$", str(breadcrumb_raw))
        if match:
            candidates.append(match.group(1).strip())

    if location_raw:
        parts = str(location_raw).split(",")
        if parts:
            first_part = clean_text(parts[0])
            if first_part and len(first_part) > 3:
                candidates.append(first_part)

    for candidate in candidates:
        if candidate and not re.match(r"^\d", candidate):
            return candidate

    if candidates:
        return candidates[0]

    return None


def normalize_floor_count(text: Optional[str]) -> Optional[int]:
    """
    Trích xuất số tầng từ text như '5 tầng', 'tầng 16', 'Số tầng 3'.
    """
    if not text:
        return None

    text = str(text).lower()

    patterns = [
        r"số\s*tầng\s*[:\-]?\s*(\d+)",
        r"(\d+)\s*tầng",
        r"tầng\s*(\d+)",
    ]

    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            try:
                value = int(match.group(1))
                if 1 <= value <= 200:
                    return value
            except ValueError:
                continue

    return None


def normalize_direction(text: Optional[str]) -> Optional[str]:
    """
    Chuẩn hóa hướng nhà/ban công.
    """
    if not text:
        return None

    text = str(text).lower().strip()

    direction_map = {
        "đông bắc": "Đông Bắc",
        "đông nam": "Đông Nam",
        "tây bắc": "Tây Bắc",
        "tây nam": "Tây Nam",
        "dong bac": "Đông Bắc",
        "dong nam": "Đông Nam",
        "tay bac": "Tây Bắc",
        "tay nam": "Tây Nam",
        "đông": "Đông",
        "tây": "Tây",
        "nam": "Nam",
        "bắc": "Bắc",
        "dong": "Đông",
        "tay": "Tây",
        "bac": "Bắc",
    }

    for key, value in direction_map.items():
        if key in text:
            return value

    return None


def normalize_legal_status(text: Optional[str]) -> Optional[str]:
    """
    Chuẩn hóa tình trạng pháp lý.
    """
    if not text:
        return None

    text = str(text).lower().strip()

    if "sổ đỏ" in text or "sổ hồng" in text or "so do" in text or "so hong" in text:
        return "have_certificate"

    if "đang chờ" in text or "dang cho" in text or "chưa có" in text or "chua co" in text:
        return "pending_certificate"

    if "hợp đồng" in text or "hop dong" in text:
        return "contract_only"

    return "other"


def normalize_furniture(text: Optional[str]) -> Optional[str]:
    """
    Chuẩn hóa tình trạng nội thất.
    """
    if not text:
        return None

    text = str(text).lower().strip()

    if "đầy đủ" in text or "day du" in text or "full" in text:
        return "full"

    if "cơ bản" in text or "co ban" in text or "basic" in text:
        return "basic"

    if "trống" in text or "trong" in text or "không" in text or "khong" in text:
        return "empty"

    return "other"