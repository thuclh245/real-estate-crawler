import re
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