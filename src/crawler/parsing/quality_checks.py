from typing import Dict, Any


def apply_quality_flags(record: Dict[str, Any]) -> Dict[str, Any]:
    """
    Gắn các cờ chất lượng dữ liệu cho một listing Silver record.
    """

    price_vnd = record.get("price_vnd")
    price_unit = record.get("price_unit")
    area_m2 = record.get("area_m2")
    location_raw = record.get("location_raw")
    district_norm = record.get("district_norm")
    city_norm = record.get("city_norm")

    # Price flags
    record["is_price_negotiable"] = price_unit == "negotiable"
    record["is_missing_price"] = price_vnd is None and not record["is_price_negotiable"]

    # Other missing flags
    record["is_missing_area"] = area_m2 is None
    record["is_missing_location"] = not bool(location_raw or district_norm or city_norm)

    # Default quality flags
    record["is_invalid_price"] = False
    record["is_invalid_area"] = False
    record["is_outlier_price"] = False
    record["is_outlier_area"] = False

    # Price validation: chỉ check khi có giá số
    if price_vnd is not None:
        try:
            price_vnd_num = float(price_vnd)

            if price_vnd_num <= 0:
                record["is_invalid_price"] = True

            if price_vnd_num < 100_000_000 or price_vnd_num > 1_000_000_000_000:
                record["is_outlier_price"] = True

        except (TypeError, ValueError):
            record["is_invalid_price"] = True

    # Area validation
    if area_m2 is not None:
        try:
            area_m2_num = float(area_m2)

            if area_m2_num <= 0:
                record["is_invalid_area"] = True

            if area_m2_num < 5 or area_m2_num > 10_000:
                record["is_outlier_area"] = True

        except (TypeError, ValueError):
            record["is_invalid_area"] = True

    # Parse status
    if record.get("parse_error_message"):
        record["parse_status"] = "failed"
    elif (
        record["is_missing_price"]
        or record["is_missing_area"]
        or record["is_missing_location"]
    ):
        record["parse_status"] = "partial_success"
    else:
        record["parse_status"] = "success"

    return record