from typing import Dict, Any


def apply_quality_flags(record: Dict[str, Any]) -> Dict[str, Any]:
    """
    Gan co chat luong du lieu cho mot listing Silver record.
    """

    price_vnd = record.get("price_vnd")
    price_unit = record.get("price_unit")
    area_m2 = record.get("area_m2")
    unit_price_vnd_m2 = record.get("unit_price_vnd_m2")
    location_raw = record.get("location_raw")
    district_norm = record.get("district_norm")
    city_norm = record.get("city_norm")
    description_raw = record.get("description_raw")
    bedroom_count = record.get("bedroom_count")
    property_type_group = record.get("property_type_group")

    # Price flags
    record["is_price_negotiable"] = price_unit == "negotiable"
    record["is_missing_price"] = price_vnd is None and not record["is_price_negotiable"]

    # Other missing flags
    record["is_missing_area"] = area_m2 is None
    record["is_missing_location"] = not bool(location_raw or district_norm or city_norm)

    # Default quality flags
    record["is_invalid_price"] = False
    record["is_invalid_area"] = False
    record["is_invalid_unit_price"] = False
    record["is_outlier_price"] = False
    record["is_outlier_area"] = False
    record["is_outlier_unit_price"] = False
    record["is_suspicious_bedroom_count"] = False
    record["is_description_too_short"] = False
    record["is_inconsistent_price_area"] = False

    # Price validation
    if price_vnd is not None:
        try:
            price_vnd_num = float(price_vnd)
            if price_vnd_num <= 0:
                record["is_invalid_price"] = True
            # VND: tu 100 trieu den 1,000 ty
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

    # Unit price validation (VND/m2)
    if unit_price_vnd_m2 is not None:
        try:
            unit_price_num = float(unit_price_vnd_m2)
            if unit_price_num <= 0:
                record["is_invalid_unit_price"] = True
            # Ha Noi: don gia thuc te tu ~5M/m2 den ~500M/m2
            if unit_price_num < 5_000_000 or unit_price_num > 500_000_000:
                record["is_outlier_unit_price"] = True
        except (TypeError, ValueError):
            record["is_invalid_unit_price"] = True

    # Cross-field consistency: price va area rieng le OK nhung unit price bat thuong
    if (price_vnd is not None and area_m2 is not None
            and not record["is_invalid_price"] and not record["is_invalid_area"]
            and unit_price_vnd_m2 is not None):
        try:
            computed_unit_price = float(price_vnd) / float(area_m2)
            if computed_unit_price < 1_000_000 or computed_unit_price > 1_000_000_000:
                record["is_inconsistent_price_area"] = True
        except (TypeError, ValueError, ZeroDivisionError):
            record["is_inconsistent_price_area"] = True

    # Suspicious bedroom count
    if bedroom_count is not None:
        try:
            bed_num = int(bedroom_count)
            if property_type_group == "apartment" and bed_num > 8:
                record["is_suspicious_bedroom_count"] = True
            elif bed_num > 20:
                record["is_suspicious_bedroom_count"] = True
        except (TypeError, ValueError):
            pass

    # Description quality
    if description_raw is None or (isinstance(description_raw, str) and len(description_raw.strip()) < 30):
        record["is_description_too_short"] = True

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
