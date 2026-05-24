import argparse
import json
from pathlib import Path

import pandas as pd

from common.quarantine import append_quarantine_record, build_quarantine_record
from common.utils import now_utc_iso
from parsing import extract_features, parse_listing
from parsing.quality import apply_quality_flags


def read_text_file(path_value: str) -> str:
    """
    Đọc file text/html an toàn.
    """
    if not path_value:
        return ""

    path = Path(path_value)

    if not path.exists():
        return ""

    return path.read_text(encoding="utf-8", errors="ignore")


def run_bronze_to_silver(
    bronze_dir: str, silver_dir: str, parser_version: str = "phase2_v1"
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
    quarantined = []
    run_id = f"bronze_to_silver_{now_utc_iso().replace(':', '').replace('-', '').replace('+', '_')}"

    for metadata_file in metadata_files:
        try:
            metadata = json.loads(metadata_file.read_text(encoding="utf-8"))

            raw_html = read_text_file(metadata.get("raw_html_path"))
            raw_text = read_text_file(metadata.get("raw_text_path"))

            record = parse_listing(
                raw_html=raw_html,
                raw_text=raw_text,
                metadata=metadata,
                parser_version=parser_version,
            )

            record.update(extract_features(record))
            record = apply_quality_flags(record)

            if record.get("parse_status") == "failed":
                quarantine_record = build_quarantine_record(
                    run_id=run_id,
                    source_code=str(metadata.get("source") or "unknown"),
                    rejection_stage="bronze_to_silver",
                    rejection_reason="parse_failed",
                    input_path=str(metadata_file),
                    record_identity=str(
                        metadata.get("listing_id")
                        or metadata.get("listing_url")
                        or metadata_file.stem
                    ),
                    error_message=str(record.get("parse_error_message") or "parse failed"),
                    parser_version=parser_version,
                    raw_reference_path=str(
                        metadata.get("raw_text_path")
                        or metadata.get("raw_html_path")
                        or metadata_file
                    ),
                    extra={"metadata_path": str(metadata.get("metadata_path") or metadata_file)},
                )
                quarantine_path = append_quarantine_record(
                    quarantine_record,
                    run_date=str(metadata.get("crawl_date") or now_utc_iso()[:10]),
                )
                quarantined.append(str(quarantine_path))

            records.append(record)

        except Exception as e:
            errors.append(
                {
                    "metadata_file": str(metadata_file),
                    "error_message": str(e),
                    "processed_at": now_utc_iso(),
                }
            )

    df = pd.DataFrame(records)

    if not df.empty:
        df.to_parquet(silver_path / "listings.parquet", index=False)
        df.to_csv(silver_path / "listings.csv", index=False, encoding="utf-8-sig")

    error_df = pd.DataFrame(errors)
    error_df.to_csv(
        silver_path / "parse_error_log.csv", index=False, encoding="utf-8-sig"
    )

    summary = {
        "bronze_dir": str(bronze_path),
        "silver_dir": str(silver_path),
        "total_metadata_files": len(metadata_files),
        "total_records_parsed": len(records),
        "total_parse_errors": len(errors),
        "total_quarantined_records": len(quarantined),
        "parse_success_rate": (
            len(records) / len(metadata_files) if metadata_files else 0
        ),
        "parser_version": parser_version,
        "processed_at": now_utc_iso(),
    }

    if not df.empty:
        for col in [
            "is_missing_price",
            "is_price_negotiable",
            "is_missing_area",
            "is_missing_location",
            "is_invalid_price",
            "is_invalid_area",
            "is_outlier_price",
            "is_outlier_area",
        ]:
            if col in df.columns:
                summary[f"{col}_rate"] = float(df[col].mean())

    with open(silver_path / "data_quality_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--bronze-dir", required=True, help="Path to Bronze crawl_date folder"
    )

    parser.add_argument(
        "--silver-dir", required=True, help="Path to output Silver folder"
    )

    parser.add_argument("--parser-version", default="phase2_v1", help="Parser version")

    args = parser.parse_args()

    run_bronze_to_silver(
        bronze_dir=args.bronze_dir,
        silver_dir=args.silver_dir,
        parser_version=args.parser_version,
    )
