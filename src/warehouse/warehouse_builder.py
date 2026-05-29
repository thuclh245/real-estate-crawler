from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd


GOLD_BASE_PATH = Path("data/gold")
WAREHOUSE_BASE_PATH = Path("data/warehouse")
SOURCE_KEYS_PATH = Path("configs/sources/source_keys.yaml")

WAREHOUSE_TABLES = [
    "dim_date",
    "dim_source",
    "dim_property_type",
    "dim_location_basic",
    "dim_listing",
    "fact_listing_snapshot",
    "fact_data_quality_daily",
]

UNKNOWN_LOCATION_KEY = "0000000000000000"
UNKNOWN_PROPERTY_TYPE_KEY = "0000000000000000"


def _load_source_key_map() -> dict[str, int]:
    default_map = {
        "unknown": 0,
        "batdongsan": 1,
        "nhatot": 2,
    }
    if not SOURCE_KEYS_PATH.exists():
        return default_map

    mapping: dict[str, int] = {}
    for raw_line in SOURCE_KEYS_PATH.read_text(encoding="utf-8").splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if not line or ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip().strip("\"'")
        value = value.strip().strip("\"'")
        if not key or not value:
            continue
        try:
            mapping[key.lower()] = int(value)
        except ValueError:
            continue

    return mapping or default_map


SOURCE_KEY_MAP = _load_source_key_map()


@dataclass(frozen=True)
class WarehouseBuildResult:
    warehouse_base_path: Path
    summary_path: Path
    table_paths: dict[str, Path]
    summary: dict[str, Any]


def log_step(message: str) -> None:
    print(f"[warehouse] {message}")


def _fail(message: str) -> None:
    raise SystemExit(f"FAIL: {message}")


def _normalize_text(value: object, default_value: str = "") -> str:
    if value is None or pd.isna(value):
        value = default_value
    return " ".join(str(value).strip().lower().split())


def _slugify(value: object) -> str:
    normalized = _normalize_text(value)
    normalized = re.sub(r"[^a-z0-9]+", "_", normalized)
    normalized = re.sub(r"_+", "_", normalized).strip("_")
    return normalized or "unknown"


def _hash_key(*parts: object) -> str:
    normalized = [
        str(part).strip().lower() if part is not None and not pd.isna(part) else "NONE"
        for part in parts
    ]
    payload = "|".join(normalized)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def _parse_date_series(series: pd.Series) -> pd.Series:
    parsed = pd.to_datetime(series, errors="coerce")
    return parsed.dt.date


def _date_key(series: pd.Series) -> pd.Series:
    parsed = pd.to_datetime(series, errors="coerce")
    return parsed.dt.strftime("%Y%m%d").astype("Int64")


def _read_parquet_table(
    base_path: Path, table_name: str, required: bool = True
) -> pd.DataFrame | None:
    table_path = base_path / table_name
    if not table_path.exists():
        if required:
            _fail(f"Missing required gold table path: {table_path}")
        return None

    parquet_files = sorted(table_path.glob("**/*.parquet"))
    if not parquet_files:
        if required:
            _fail(f"No parquet files found under: {table_path}")
        return None

    frames = []
    for file_path in parquet_files:
        df = pd.read_parquet(file_path)
        # Traverse parent directories up to table_path to extract Hive partition values
        for parent in file_path.parents:
            if parent == table_path:
                break
            if "=" in parent.name:
                part_col, part_val = parent.name.split("=", 1)
                df[part_col] = part_val
        frames.append(df)

    return pd.concat(frames, ignore_index=True, sort=False)


def _write_table(df: pd.DataFrame, output_path: Path) -> None:
    if output_path.exists():
        shutil.rmtree(output_path)
    output_path.mkdir(parents=True, exist_ok=True)
    parquet_path = output_path / "part-0000.parquet"
    df.to_parquet(parquet_path, index=False)
    df.head(1000).to_csv(output_path / "sample.csv", index=False, encoding="utf-8-sig")


def _source_key(source_code: object) -> int:
    normalized = _normalize_text(source_code)
    if normalized in SOURCE_KEY_MAP:
        return SOURCE_KEY_MAP[normalized]
    for key, val in SOURCE_KEY_MAP.items():
        if key != "unknown" and (key in normalized or normalized in key):
            return val
    return 0


def _choose_text_column(df: pd.DataFrame, candidates: list[str]) -> pd.Series:
    for candidate in candidates:
        if candidate in df.columns:
            return df[candidate]
    return pd.Series([None] * len(df), index=df.index)


def _first_nonempty_text(df: pd.DataFrame, candidates: list[str]) -> pd.Series:
    result = pd.Series([None] * len(df), index=df.index)
    for candidate in candidates:
        if candidate not in df.columns:
            continue
        candidate_series = df[candidate].apply(lambda value: _normalize_text(value, ""))
        result = result.where(result.notna() & (result != ""), candidate_series)
    return result


def build_dim_date(snapshot_df: pd.DataFrame, quality_df: pd.DataFrame) -> pd.DataFrame:
    date_values: list[pd.Series] = []
    for candidate in ["snapshot_date", "crawl_date"]:
        if candidate in snapshot_df.columns:
            date_values.append(_parse_date_series(snapshot_df[candidate]))
        if candidate in quality_df.columns:
            date_values.append(_parse_date_series(quality_df[candidate]))

    if not date_values:
        return pd.DataFrame(
            columns=[
                "date_key",
                "date_value",
                "day_of_month",
                "day_of_week",
                "week_of_year",
                "month",
                "month_name",
                "quarter",
                "year",
                "is_weekend",
            ]
        )

    combined = pd.concat(date_values, ignore_index=True).dropna().drop_duplicates().sort_values()
    date_frame = pd.DataFrame({"date_value": pd.to_datetime(combined)})
    date_frame["date_key"] = date_frame["date_value"].dt.strftime("%Y%m%d").astype(int)
    date_frame["day_of_month"] = date_frame["date_value"].dt.day
    date_frame["day_of_week"] = date_frame["date_value"].dt.dayofweek + 1
    date_frame["week_of_year"] = date_frame["date_value"].dt.isocalendar().week.astype(int)
    date_frame["month"] = date_frame["date_value"].dt.month
    date_frame["month_name"] = date_frame["date_value"].dt.month_name()
    date_frame["quarter"] = date_frame["date_value"].dt.quarter
    date_frame["year"] = date_frame["date_value"].dt.year
    date_frame["is_weekend"] = date_frame["day_of_week"].isin([6, 7])
    return date_frame[
        [
            "date_key",
            "date_value",
            "day_of_month",
            "day_of_week",
            "week_of_year",
            "month",
            "month_name",
            "quarter",
            "year",
            "is_weekend",
        ]
    ].reset_index(drop=True)


def build_dim_source(snapshot_df: pd.DataFrame, quality_df: pd.DataFrame) -> pd.DataFrame:
    source_values = pd.concat(
        [
            snapshot_df.get("source_code", snapshot_df.get("source")),
            quality_df.get("source_code", quality_df.get("source")),
        ],
        ignore_index=True,
    )
    source_values = source_values.dropna().map(_normalize_text).drop_duplicates()
    source_values = pd.Index([value for value in source_values.tolist() if value])
    source_values = pd.Index(["unknown"] + [value for value in source_values if value != "unknown"])

    rows = []
    for source_code in source_values:
        rows.append(
            {
                "source_key": _source_key(source_code),
                "source_code": source_code,
                "source_name": source_code.replace("_", " ").title(),
                "source_domain": "batdongsan.com.vn"
                if "batdongsan" in source_code
                else "nhatot.com"
                if "nhatot" in source_code
                else None,
                "source_type": "website",
                "is_active": "batdongsan" in source_code or "nhatot" in source_code,
                "first_onboarded_at": None,
            }
        )

    frame = pd.DataFrame(rows).drop_duplicates(subset=["source_key"]).sort_values("source_key")
    return frame.reset_index(drop=True)


def build_dim_property_type(snapshot_df: pd.DataFrame) -> pd.DataFrame:
    source_column = None
    for candidate in ["property_type_group", "property_type", "crawl_category"]:
        if candidate in snapshot_df.columns:
            source_column = candidate
            break

    if source_column is None:
        return pd.DataFrame(
            [
                {
                    "property_type_key": UNKNOWN_PROPERTY_TYPE_KEY,
                    "business_type": "unknown",
                    "property_type_group": "unknown",
                    "property_type_code": "unknown",
                    "property_type_label": "Unknown",
                    "is_residential": False,
                    "is_land": False,
                    "is_commercial": False,
                }
            ]
        )

    groups = snapshot_df[source_column].dropna().map(_normalize_text).drop_duplicates()
    groups = pd.Index([value for value in groups.tolist() if value])
    groups = pd.Index(["unknown"] + [value for value in groups if value != "unknown"])

    rows = []
    for group in groups:
        if group in {"apartment", "house", "villa_townhouse"}:
            business_type = "residential"
        elif group == "land":
            business_type = "land"
        elif group == "commercial":
            business_type = "commercial"
        else:
            business_type = "unknown"

        rows.append(
            {
                "property_type_key": _hash_key(business_type, group)
                if group != "unknown"
                else UNKNOWN_PROPERTY_TYPE_KEY,
                "business_type": business_type,
                "property_type_group": group,
                "property_type_code": group,
                "property_type_label": group.replace("_", " ").title(),
                "is_residential": business_type == "residential",
                "is_land": business_type == "land",
                "is_commercial": business_type == "commercial",
            }
        )

    frame = (
        pd.DataFrame(rows)
        .drop_duplicates(subset=["property_type_key"])
        .sort_values("property_type_key")
    )
    return frame.reset_index(drop=True)


def build_dim_location_basic(snapshot_df: pd.DataFrame) -> pd.DataFrame:
    city_series = _first_nonempty_text(
        snapshot_df, ["city_norm", "province_norm", "city", "city_name"]
    )
    district_series = _first_nonempty_text(
        snapshot_df, ["district_norm", "district", "district_name"]
    )
    ward_series = _first_nonempty_text(snapshot_df, ["ward_norm", "ward", "ward_name"])

    rows = []
    for city_name, district_name, ward_name in zip(city_series, district_series, ward_series):
        city_name = "Unknown" if not city_name else str(city_name)
        district_name = "Unknown" if not district_name else str(district_name)
        ward_name = "Unknown" if not ward_name else str(ward_name)

        city_code = _slugify(city_name)
        district_code = _slugify(district_name)
        ward_code = _slugify(ward_name)

        if city_code == "unknown" and district_code == "unknown" and ward_code == "unknown":
            location_key = UNKNOWN_LOCATION_KEY
            location_level = "unknown"
            location_confidence = 0.0
        else:
            location_key = _hash_key("VN", city_code, district_code, ward_code)
            if ward_code != "unknown":
                location_level = "ward"
                location_confidence = 1.0
            elif district_code != "unknown":
                location_level = "district"
                location_confidence = 0.7
            elif city_code != "unknown":
                location_level = "city"
                location_confidence = 0.4
            else:
                location_level = "unknown"
                location_confidence = 0.0

        rows.append(
            {
                "location_key": location_key,
                "country_code": "VN",
                "country_name": "Vietnam",
                "city_code": city_code,
                "city_name": city_name,
                "district_code": district_code,
                "district_name": district_name,
                "ward_code": ward_code,
                "ward_name": ward_name,
                "location_level": location_level,
                "location_confidence": location_confidence,
                "location_match_method": "normalized_labels",
                "is_reference_matched": False,
            }
        )

    rows.append(
        {
            "location_key": UNKNOWN_LOCATION_KEY,
            "country_code": "VN",
            "country_name": "Vietnam",
            "city_code": "unknown",
            "city_name": "Unknown",
            "district_code": "unknown",
            "district_name": "Unknown",
            "ward_code": "unknown",
            "ward_name": "Unknown",
            "location_level": "unknown",
            "location_confidence": 0.0,
            "location_match_method": "unknown",
            "is_reference_matched": False,
        }
    )

    frame = pd.DataFrame(rows).drop_duplicates(subset=["location_key"]).sort_values("location_key")
    return frame.reset_index(drop=True)


def _listing_identity_row(row: pd.Series) -> tuple[str, str, str | None, str | None, str | None]:
    source_code = _normalize_text(row.get("source_code") or row.get("source"))
    listing_id = _normalize_text(row.get("listing_id"), "")
    listing_url = _normalize_text(row.get("listing_url") or row.get("final_detail_url"), "")
    dedup_key = _normalize_text(row.get("dedup_key"), "")

    if listing_id:
        method = "listing_id"
        identity_value = listing_id
    elif listing_url:
        method = "listing_url"
        identity_value = listing_url
    else:
        method = "dedup_key"
        identity_value = dedup_key

    return source_code, method, listing_id or None, listing_url or None, identity_value or None


def build_dim_listing(snapshot_df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, row in snapshot_df.iterrows():
        source_code, method, listing_id, listing_url, identity_value = _listing_identity_row(row)
        if not source_code or not identity_value:
            continue
        rows.append(
            {
                "listing_key": _hash_key(source_code, identity_value),
                "source_key": _source_key(source_code),
                "source_listing_id": listing_id,
                "source_listing_url": listing_url,
                "dedup_key": row.get("dedup_key"),
                "first_seen_date_key": int(
                    _date_key(pd.Series([row.get("snapshot_date") or row.get("crawl_date")])).iloc[
                        0
                    ]
                )
                if pd.notna(row.get("snapshot_date") or row.get("crawl_date"))
                else None,
                "last_seen_date_key": int(
                    _date_key(pd.Series([row.get("snapshot_date") or row.get("crawl_date")])).iloc[
                        0
                    ]
                )
                if pd.notna(row.get("snapshot_date") or row.get("crawl_date"))
                else None,
                "listing_identity_method": method,
                # --- NLP enriched descriptive attributes ---
                "project_name": row.get("project_name") or None,
                "building_name": row.get("building_name") or None,
                "direction": row.get("direction") or None,
                "frontage_width_m": row.get("frontage_width") or row.get("frontage_width_m") or None,
                "seller_type": row.get("seller_type") or None,
            }
        )

    frame = pd.DataFrame(rows)
    if frame.empty:
        return pd.DataFrame(
            columns=[
                "listing_key",
                "source_key",
                "source_listing_id",
                "source_listing_url",
                "dedup_key",
                "first_seen_date_key",
                "last_seen_date_key",
                "listing_identity_method",
                "project_name",
                "building_name",
                "direction",
                "frontage_width_m",
                "seller_type",
            ]
        )

    frame["first_seen_date_key"] = pd.to_numeric(frame["first_seen_date_key"], errors="coerce")
    frame["last_seen_date_key"] = pd.to_numeric(frame["last_seen_date_key"], errors="coerce")
    frame = (
        frame.groupby("listing_key", as_index=False)
        .agg(
            source_key=("source_key", "first"),
            source_listing_id=("source_listing_id", "first"),
            source_listing_url=("source_listing_url", "first"),
            dedup_key=("dedup_key", "first"),
            first_seen_date_key=("first_seen_date_key", "min"),
            last_seen_date_key=("last_seen_date_key", "max"),
            listing_identity_method=("listing_identity_method", "first"),
            project_name=("project_name", "first"),
            building_name=("building_name", "first"),
            direction=("direction", "first"),
            frontage_width_m=("frontage_width_m", "first"),
            seller_type=("seller_type", "first"),
        )
        .sort_values("listing_key")
    )
    frame["first_seen_date_key"] = frame["first_seen_date_key"].astype("Int64")
    frame["last_seen_date_key"] = frame["last_seen_date_key"].astype("Int64")
    return frame.reset_index(drop=True)


def build_fact_listing_snapshot(snapshot_df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, row in snapshot_df.iterrows():
        source_code, _, listing_id, listing_url, identity_value = _listing_identity_row(row)
        if not source_code or not identity_value:
            continue

        city_name = _normalize_text(
            row.get("city_norm")
            or row.get("province_norm")
            or row.get("city")
            or row.get("city_name"),
            "",
        )
        district_name = _normalize_text(
            row.get("district_norm") or row.get("district") or row.get("district_name"), ""
        )
        ward_name = _normalize_text(
            row.get("ward_norm") or row.get("ward") or row.get("ward_name"), ""
        )
        if city_name or district_name or ward_name:
            if city_name and district_name and ward_name:
                location_key = _hash_key(
                    "VN", _slugify(city_name), _slugify(district_name), _slugify(ward_name)
                )
            elif city_name or district_name or ward_name:
                location_key = _hash_key(
                    "VN", _slugify(city_name), _slugify(district_name), _slugify(ward_name)
                )
            else:
                location_key = UNKNOWN_LOCATION_KEY
        else:
            location_key = UNKNOWN_LOCATION_KEY

        property_type_group = _normalize_text(
            row.get("property_type_group") or row.get("property_type") or row.get("crawl_category"),
            "unknown",
        )
        if property_type_group == "unknown":
            property_type_key = UNKNOWN_PROPERTY_TYPE_KEY
        else:
            if property_type_group in {"apartment", "house", "villa_townhouse"}:
                business_type = "residential"
            elif property_type_group == "land":
                business_type = "land"
            elif property_type_group == "commercial":
                business_type = "commercial"
            else:
                business_type = "unknown"
            property_type_key = _hash_key(business_type, property_type_group)

        rows.append(
            {
                "snapshot_date_key": int(
                    _date_key(pd.Series([row.get("snapshot_date") or row.get("crawl_date")])).iloc[
                        0
                    ]
                )
                if pd.notna(row.get("snapshot_date") or row.get("crawl_date"))
                else None,
                "source_key": _source_key(source_code),
                "listing_key": _hash_key(source_code, identity_value),
                "location_key": location_key,
                "property_type_key": property_type_key,
                "price_vnd": row.get("price_vnd"),
                "area_m2": row.get("area_m2"),
                "unit_price_vnd_m2": row.get("unit_price_vnd_m2"),
                "bedroom_count": row.get("bedroom_count"),
                "bathroom_count": row.get("bathroom_count"),
                "frontage_width_m": row.get("frontage_width_m"),
                "quality_score": row.get("quality_score"),
                "snapshot_status": row.get("snapshot_status") or "unknown",
                "is_new_listing": bool(row.get("is_new_listing", False)),
                "is_active_listing": bool(row.get("is_active_listing", False)),
                "is_removed_listing": bool(row.get("is_removed_listing", False)),
                "is_price_changed": bool(row.get("is_price_changed", False)),
                "is_info_changed": bool(row.get("is_info_changed", False)),
                "price_change_vnd": row.get("price_change_vnd"),
                "price_change_pct": row.get("price_change_pct"),
                "has_legal_info": bool(row.get("has_legal_info", False))
                if pd.notna(row.get("has_legal_info"))
                else False,
                "has_car_access": bool(row.get("has_car_access", False))
                if pd.notna(row.get("has_car_access"))
                else False,
                "is_price_negotiable": bool(row.get("is_price_negotiable", False))
                if pd.notna(row.get("is_price_negotiable"))
                else False,
                # --- NLP enriched status / flag fields ---
                "legal_status_raw": row.get("legal_status_raw") or None,
                "has_red_pink_book": bool(row.get("has_red_pink_book", False))
                if pd.notna(row.get("has_red_pink_book"))
                else False,
                "furniture_level": row.get("furniture_level") or None,
                "floor_count": row.get("floor_count") or None,
                "is_business_suitable": bool(row.get("is_business_suitable", False))
                if pd.notna(row.get("is_business_suitable"))
                else False,
                "has_urban_area_flag": bool(row.get("has_urban_area_flag", False))
                if pd.notna(row.get("has_urban_area_flag"))
                else False,
                "has_security_flag": bool(row.get("has_security_flag", False))
                if pd.notna(row.get("has_security_flag"))
                else False,
                "has_educated_community_flag": bool(row.get("has_educated_community_flag", False))
                if pd.notna(row.get("has_educated_community_flag"))
                else False,
                "has_high_intellect_flag": bool(row.get("has_high_intellect_flag", False))
                if pd.notna(row.get("has_high_intellect_flag"))
                else False,
                "has_residential_area_flag": bool(row.get("has_residential_area_flag", False))
                if pd.notna(row.get("has_residential_area_flag"))
                else False,
                "has_subdivision_flag": bool(row.get("has_subdivision_flag", False))
                if pd.notna(row.get("has_subdivision_flag"))
                else False,
                "car_access_type": row.get("car_access_type") or None,
            }
        )

    frame = pd.DataFrame(rows).drop_duplicates(
        subset=["snapshot_date_key", "source_key", "listing_key"]
    )
    return frame.sort_values(["snapshot_date_key", "source_key", "listing_key"]).reset_index(
        drop=True
    )


def build_fact_data_quality_daily(quality_df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, row in quality_df.iterrows():
        source_code = _normalize_text(row.get("source_code") or row.get("source"))
        if not source_code:
            continue
        rows.append(
            {
                "crawl_date_key": int(_date_key(pd.Series([row.get("crawl_date")])).iloc[0])
                if pd.notna(row.get("crawl_date"))
                else None,
                "source_key": _source_key(source_code),
                "total_records": row.get("total_records", 0),
                "parse_success_count": row.get("parse_success_count", 0),
                "parse_success_rate": row.get("parse_success_rate", 0.0),
                "duplicate_record_count": row.get("duplicate_record_count", 0),
                "duplicate_rate": row.get("duplicate_rate", 0.0),
                "missing_price_count": row.get("missing_price_count", 0),
                "missing_price_rate": row.get("missing_price_rate", 0.0),
                "missing_area_count": row.get("missing_area_count", 0),
                "missing_area_rate": row.get("missing_area_rate", 0.0),
                "missing_location_count": row.get("missing_location_count", 0),
                "missing_location_rate": row.get("missing_location_rate", 0.0),
                "quarantine_count": row.get("quarantine_count", 0),
                "publish_blocked_flag": bool(row.get("publish_blocked_flag", False))
                if pd.notna(row.get("publish_blocked_flag"))
                else False,
            }
        )

    frame = pd.DataFrame(rows).drop_duplicates(subset=["crawl_date_key", "source_key"])
    return frame.sort_values(["crawl_date_key", "source_key"]).reset_index(drop=True)


def _write_summary(
    *,
    warehouse_base_path: Path,
    table_paths: dict[str, Path],
    table_counts: dict[str, int],
    snapshot_df: pd.DataFrame,
    quality_df: pd.DataFrame,
) -> tuple[Path, dict[str, Any]]:
    snapshot_dates = (
        pd.to_datetime(
            snapshot_df[
                [column for column in ["snapshot_date"] if column in snapshot_df.columns]
            ].stack(),
            errors="coerce",
        )
        .dropna()
        .dt.strftime("%Y-%m-%d")
        .drop_duplicates()
        .sort_values()
        .tolist()
        if "snapshot_date" in snapshot_df.columns
        else []
    )
    crawl_dates = (
        pd.to_datetime(
            quality_df[
                [column for column in ["crawl_date"] if column in quality_df.columns]
            ].stack(),
            errors="coerce",
        )
        .dropna()
        .dt.strftime("%Y-%m-%d")
        .drop_duplicates()
        .sort_values()
        .tolist()
        if "crawl_date" in quality_df.columns
        else []
    )
    source_codes = sorted(
        {
            _normalize_text(value)
            for value in pd.concat(
                [
                    snapshot_df.get("source_code", snapshot_df.get("source")),
                    quality_df.get("source_code", quality_df.get("source")),
                ],
                ignore_index=True,
            )
            .dropna()
            .tolist()
            if _normalize_text(value)
        }
    )
    if "unknown" not in source_codes:
        source_codes = ["unknown"] + source_codes

    summary = {
        "warehouse_schema_version": "warehouse_v1",
        "table_row_counts": table_counts,
        "snapshot_dates": snapshot_dates,
        "crawl_dates": crawl_dates,
        "source_codes": source_codes,
        "warehouse_tables_created": list(table_paths.keys()),
        "created_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
    }

    summary_path = warehouse_base_path / "warehouse_summary.json"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return summary_path, summary


def build_warehouse_outputs(
    *,
    gold_base_path: str | Path = GOLD_BASE_PATH,
    warehouse_base_path: str | Path = WAREHOUSE_BASE_PATH,
) -> WarehouseBuildResult:
    gold_base_path = Path(gold_base_path)
    warehouse_base_path = Path(warehouse_base_path)

    listing_snapshot_df = _read_parquet_table(
        gold_base_path, "gold_listing_snapshots", required=False
    )
    if listing_snapshot_df is None:
        listing_snapshot_df = _read_parquet_table(
            gold_base_path, "gold_current_listings", required=True
        )

    quality_df = _read_parquet_table(gold_base_path, "gold_data_quality_daily", required=True)

    dim_date_df = build_dim_date(listing_snapshot_df, quality_df)
    dim_source_df = build_dim_source(listing_snapshot_df, quality_df)
    dim_property_type_df = build_dim_property_type(listing_snapshot_df)
    dim_location_basic_df = build_dim_location_basic(listing_snapshot_df)
    dim_listing_df = build_dim_listing(listing_snapshot_df)
    fact_listing_snapshot_df = build_fact_listing_snapshot(listing_snapshot_df)
    fact_data_quality_daily_df = build_fact_data_quality_daily(quality_df)

    tables = {
        "dim_date": dim_date_df,
        "dim_source": dim_source_df,
        "dim_property_type": dim_property_type_df,
        "dim_location_basic": dim_location_basic_df,
        "dim_listing": dim_listing_df,
        "fact_listing_snapshot": fact_listing_snapshot_df,
        "fact_data_quality_daily": fact_data_quality_daily_df,
    }

    table_paths: dict[str, Path] = {}
    table_counts: dict[str, int] = {}
    for table_name, df in tables.items():
        output_path = warehouse_base_path / table_name
        log_step(f"Writing {table_name} to {output_path}")
        _write_table(df, output_path)
        table_paths[table_name] = output_path
        table_counts[table_name] = int(len(df))

    summary_path, summary = _write_summary(
        warehouse_base_path=warehouse_base_path,
        table_paths=table_paths,
        table_counts=table_counts,
        snapshot_df=listing_snapshot_df,
        quality_df=quality_df,
    )

    return WarehouseBuildResult(
        warehouse_base_path=warehouse_base_path,
        summary_path=summary_path,
        table_paths=table_paths,
        summary=summary,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the warehouse outputs.")
    parser.add_argument("--gold-base-path", default=str(GOLD_BASE_PATH))
    parser.add_argument("--warehouse-base-path", default=str(WAREHOUSE_BASE_PATH))
    args = parser.parse_args()

    result = build_warehouse_outputs(
        gold_base_path=args.gold_base_path,
        warehouse_base_path=args.warehouse_base_path,
    )
    print(json.dumps(result.summary, ensure_ascii=False, indent=2))
    print(f"Warehouse summary written to: {result.summary_path}")


if __name__ == "__main__":
    main()
