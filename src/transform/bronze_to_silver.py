import argparse
import json
from pathlib import Path
from datetime import datetime, timezone

import pandas as pd

from crawler.parsing.batdongsan_parser import parse_listing
from crawler.parsing.quality_checks import apply_quality_flags


SILVER_SCHEMA_VERSION = "v1.1"

# Define explicit dtypes for consistent Parquet schema
SILVER_DTYPES = {
    "silver_schema_version": "string",
    "source": "string",
    "crawl_date": "string",
    "crawl_id": "string",
    "listing_id": "string",
    "listing_url": "string",
    "dedup_key": "string",
    "dedup_method": "string",
    "title_raw": "string",
    "description_raw": "string",
    "price_raw": "string",
    "area_raw": "string",
    "location_raw": "string",
    "price_value": "float64",
    "price_unit": "string",
    "price_vnd": "float64",
    "area_m2": "float64",
    "unit_price_vnd_m2": "float64",
    "property_type_raw": "string",
    "property_type_group": "string",
    "listing_business_type": "string",
    "city_raw": "string",
    "district_raw": "string",
    "ward_raw": "string",
    "street_raw": "string",
    "project_raw": "string",
    "city_norm": "string",
    "district_norm": "string",
    "ward_norm": "string",
    "location_confidence": "string",
    "location_parse_method": "string",
    "bedroom_count": "Int64",
    "bathroom_count": "Int64",
    "floor_count": "Int64",
    "direction": "string",
    "legal_status": "string",
    "furniture_status": "string",
    "seller_type": "string",
    "seller_years_on_platform": "string",
    "seller_active_listing_count": "string",
    "has_broker_certificate": "string",
    "phone_masked": "string",
    "is_broker": "boolean",
    "phone_raw": "string",
    "listing_type": "string",
    "image_count": "Int64",
    "has_image": "boolean",
    "posted_date_raw": "string",
    "expired_date_raw": "string",
    "posted_date": "string",
    "expired_date": "string",
    "parse_status": "string",
    "parse_error_message": "string",
    "raw_html_path": "string",
    "raw_text_path": "string",
    "metadata_path": "string",
    "parser_version": "string",
    "processed_at": "string",
    # Quality flags (boolean)
    "is_price_negotiable": "boolean",
    "is_missing_price": "boolean",
    "is_missing_area": "boolean",
    "is_missing_location": "boolean",
    "is_invalid_price": "boolean",
    "is_invalid_area": "boolean",
    "is_invalid_unit_price": "boolean",
    "is_outlier_price": "boolean",
    "is_outlier_area": "boolean",
    "is_outlier_unit_price": "boolean",
    "is_suspicious_bedroom_count": "boolean",
    "is_description_too_short": "boolean",
    "is_inconsistent_price_area": "boolean",
}


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def read_text_file(path_value: str) -> str:
    if not path_value:
        return ""
    path = Path(path_value)
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="ignore")


def cast_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Enforce consistent dtypes to prevent NaN-vs-null issues in Parquet."""
    for col, dtype in SILVER_DTYPES.items():
        if col not in df.columns:
            continue
        try:
            if dtype == "Int64":
                df[col] = pd.array(df[col], dtype="Int64")
            elif dtype == "boolean":
                df[col] = pd.array(df[col], dtype="boolean")
            elif dtype == "float64":
                series = pd.to_numeric(df[col], errors="coerce")
                df[col] = series.astype("float64")
            elif dtype == "string":
                mask = df[col].notna()
                df.loc[mask, col] = df.loc[mask, col].astype(str)
        except Exception:
            pass
    return df


def run_bronze_to_silver(
    bronze_dir: str,
    silver_dir: str,
    parser_version: str = "phase2_v1"
):
    bronze_path = Path(bronze_dir)
    silver_path = Path(silver_dir)

    silver_path.mkdir(parents=True, exist_ok=True)

    metadata_dir = bronze_path / "metadata"

    if not metadata_dir.exists():
        raise FileNotFoundError(f"Metadata folder not found: {metadata_dir}")

    metadata_files = sorted(metadata_dir.glob("*.json"))

    records = []
    errors = []

    for metadata_file in metadata_files:
        try:
            metadata = json.loads(metadata_file.read_text(encoding="utf-8"))

            raw_html = read_text_file(metadata.get("raw_html_path"))
            raw_text = read_text_file(metadata.get("raw_text_path"))

            record = parse_listing(
                raw_html=raw_html,
                raw_text=raw_text,
                metadata=metadata,
                parser_version=parser_version
            )

            record = apply_quality_flags(record)
            records.append(record)

        except Exception as e:
            errors.append({
                "metadata_file": str(metadata_file),
                "error_message": str(e),
                "processed_at": now_utc_iso()
            })

    df = pd.DataFrame(records)

    if not df.empty:
        df = cast_dataframe(df)
        df.to_parquet(silver_path / "listings.parquet", index=False)
        df.to_csv(silver_path / "listings.csv", index=False, encoding="utf-8-sig")

    error_df = pd.DataFrame(errors)
    if not error_df.empty:
        error_df.to_csv(silver_path / "parse_error_log.csv", index=False, encoding="utf-8-sig")

    summary = {
        "silver_schema_version": SILVER_SCHEMA_VERSION,
        "bronze_dir": str(bronze_path),
        "silver_dir": str(silver_path),
        "total_metadata_files": len(metadata_files),
        "total_records_parsed": len(records),
        "total_parse_errors": len(errors),
        "parse_success_rate": len(records) / len(metadata_files) if metadata_files else 0,
        "parser_version": parser_version,
        "processed_at": now_utc_iso()
    }

    if not df.empty:
        quality_flag_cols = [
            "is_missing_price",
            "is_price_negotiable",
            "is_missing_area",
            "is_missing_location",
            "is_invalid_price",
            "is_invalid_area",
            "is_invalid_unit_price",
            "is_outlier_price",
            "is_outlier_area",
            "is_outlier_unit_price",
            "is_suspicious_bedroom_count",
            "is_description_too_short",
            "is_inconsistent_price_area",
        ]

        for col in quality_flag_cols:
            if col in df.columns:
                summary[f"{col}_rate"] = float(df[col].mean())

        # Additional stats
        if "bedroom_count" in df.columns:
            summary["bedroom_count_null_rate"] = float(df["bedroom_count"].isna().mean())
        if "bathroom_count" in df.columns:
            summary["bathroom_count_null_rate"] = float(df["bathroom_count"].isna().mean())
        if "floor_count" in df.columns:
            summary["floor_count_null_rate"] = float(df["floor_count"].isna().mean())
        if "posted_date" in df.columns:
            summary["posted_date_null_rate"] = float(df["posted_date"].isna().mean())
        if "project_raw" in df.columns:
            summary["project_raw_null_rate"] = float(df["project_raw"].isna().mean())
        if "dedup_method" in df.columns:
            for method in df["dedup_method"].unique():
                if method is not None and not (isinstance(method, float) and pd.isna(method)):
                    summary[f"dedup_method_{method}_count"] = int((df["dedup_method"] == method).sum())

    with open(silver_path / "data_quality_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--bronze-dir",
        required=True,
        help="Path to Bronze crawl_date folder"
    )

    parser.add_argument(
        "--silver-dir",
        required=True,
        help="Path to output Silver folder"
    )

    parser.add_argument(
        "--parser-version",
        default="phase2_v1",
        help="Parser version"
    )

    args = parser.parse_args()

    run_bronze_to_silver(
        bronze_dir=args.bronze_dir,
        silver_dir=args.silver_dir,
        parser_version=args.parser_version
    )
