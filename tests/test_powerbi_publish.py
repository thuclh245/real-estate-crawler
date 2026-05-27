import csv
import json
import os
import shutil
import sys
import unittest
from pathlib import Path
from uuid import uuid4

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from publish.powerbi import publish_powerbi_marts


class PowerBiPublishTest(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = ROOT / "tests" / "tmp_runtime" / f"pbi_{uuid4().hex}"
        self.gold_dir = self.tmp_dir / "gold"
        self.warehouse_dir = self.tmp_dir / "warehouse"
        self.powerbi_dir = self.tmp_dir / "powerbi"
        self.tmp_dir.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_publish_powerbi_marts_success(self):
        # Create mock gold data
        snapshot_rows = [
            {
                "snapshot_date": "2026-05-14",
                "source": "batdongsan",
                "listing_id": "123",
                "listing_url": "https://batdongsan.com.vn/pr123",
                "city_norm": "Ha Noi",
                "district_norm": "Cau Giay",
                "ward_norm": None,
                "property_type_group": "house",
                "price_vnd": 5000000000,
                "area_m2": 50.0,
                "unit_price_vnd_m2": 100000000.0,
                "bedroom_count": 3,
                "bathroom_count": 2,
                "frontage_width_m": 5.0,
                "quality_score": 18,
                "snapshot_status": "active",
                "is_new_listing": True,
                "is_active_listing": True,
                "is_removed_listing": False,
                "is_price_changed": False,
                "is_info_changed": False,
                "price_change_vnd": None,
                "price_change_pct": None,
                "has_legal_info": True,
                "has_car_access": True,
                "is_price_negotiable": False,
                "dedup_key": "batdongsan::123",
            },
            {
                "snapshot_date": "2026-05-14",
                "source": "nhatot",
                "listing_id": None,
                "listing_url": "https://www.nhatot.com/listing/abc",
                "city_norm": "Ho Chi Minh",
                "district_norm": "Thu Duc",
                "ward_norm": "An Phu",
                "property_type_group": "apartment",
                "price_vnd": None,  # Negotiable price -> should be empty string in CSV
                "area_m2": 65.0,
                "unit_price_vnd_m2": None,
                "bedroom_count": 2,
                "bathroom_count": 1,
                "frontage_width_m": None,
                "quality_score": 17,
                "snapshot_status": "active",
                "is_new_listing": False,
                "is_active_listing": True,
                "is_removed_listing": False,
                "is_price_changed": True,
                "is_info_changed": False,
                "price_change_vnd": 200000000,
                "price_change_pct": 0.066,
                "has_legal_info": False,
                "has_car_access": False,
                "is_price_negotiable": True,
                "dedup_key": "nhatot::abc",
            },
        ]

        quality_rows = [
            {
                "crawl_date": "2026-05-14",
                "source": "batdongsan",
                "total_records": 1,
                "parse_success_count": 1,
                "parse_success_rate": 1.0,
                "duplicate_record_count": 0,
                "duplicate_rate": 0.0,
                "missing_price_count": 0,
                "missing_price_rate": 0.0,
                "missing_area_count": 0,
                "missing_area_rate": 0.0,
                "missing_location_count": 0,
                "missing_location_rate": 0.0,
                "quarantine_count": 0,
                "publish_blocked_flag": False,
            },
            {
                "crawl_date": "2026-05-14",
                "source": "nhatot",
                "total_records": 2,
                "parse_success_count": 2,
                "parse_success_rate": 1.0,
                "duplicate_record_count": 0,
                "duplicate_rate": 0.0,
                "missing_price_count": 1,
                "missing_price_rate": 0.5,
                "missing_area_count": 1,
                "missing_area_rate": 0.5,
                "missing_location_count": 1,
                "missing_location_rate": 0.5,
                "quarantine_count": 1,
                "publish_blocked_flag": False,
            },
        ]

        # Write Parquet files
        snapshot_table_dir = self.gold_dir / "gold_listing_snapshots"
        quality_table_dir = self.gold_dir / "gold_data_quality_daily"
        snapshot_table_dir.mkdir(parents=True, exist_ok=True)
        quality_table_dir.mkdir(parents=True, exist_ok=True)

        pd.DataFrame(snapshot_rows).to_parquet(
            snapshot_table_dir / "part-0000.parquet", index=False
        )
        pd.DataFrame(quality_rows).to_parquet(quality_table_dir / "part-0000.parquet", index=False)

        # Set environment variable to control run_id
        os.environ["RUN_ID"] = "test_run_powerbi_123"

        # Execute publishing
        success = publish_powerbi_marts(
            gold_base_path=self.gold_dir,
            warehouse_base_path=self.warehouse_dir,
            powerbi_base_path=self.powerbi_dir,
        )

        self.assertTrue(success)

        # Verify CSV exports
        csv_files = [
            "dim_date.csv",
            "dim_source.csv",
            "dim_property_type.csv",
            "dim_location_basic.csv",
            "dim_listing.csv",
            "fact_listing_snapshot.csv",
            "fact_data_quality_daily.csv",
        ]

        for file_name in csv_files:
            file_path = self.powerbi_dir / file_name
            self.assertTrue(file_path.exists(), f"{file_name} was not created")
            df = pd.read_csv(file_path)
            self.assertGreater(len(df), 0, f"{file_name} is empty")

        # Verify manifest contents
        manifest_path = self.powerbi_dir / "refresh_manifest.json"
        self.assertTrue(manifest_path.exists())
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(manifest["warehouse_schema_version"], "warehouse_v1")
        self.assertEqual(manifest["refresh_status"], "success")
        self.assertEqual(manifest["run_id"], "test_run_powerbi_123")
        self.assertEqual(manifest["latest_snapshot_date"], "2026-05-14")
        self.assertIn("fact_listing_snapshot", manifest["table_row_counts"])
        self.assertEqual(manifest["table_row_counts"]["fact_listing_snapshot"], 2)

        # Verify UTF-8 BOM encoding (first three bytes should be \xef\xbb\xbf)
        with open(self.powerbi_dir / "fact_listing_snapshot.csv", "rb") as f:
            bom = f.read(3)
            self.assertEqual(bom, b"\xef\xbb\xbf")

        # Verify nullable prices are saved as empty strings (not 0 or NaN)
        fact_csv_path = self.powerbi_dir / "fact_listing_snapshot.csv"
        raw_text = fact_csv_path.read_text(encoding="utf-8-sig")

        reader = csv.reader(raw_text.splitlines())
        rows_parsed = list(reader)

        header = rows_parsed[0]
        price_idx = header.index("price_vnd")
        unit_price_idx = header.index("unit_price_vnd_m2")

        # The nhatot row (listing key index) is row 2
        # Let's identify by source_key: batdongsan = 1, nhatot = 2
        source_key_idx = header.index("source_key")

        nhatot_row = None
        for r in rows_parsed[1:]:
            if r[source_key_idx] == "2":
                nhatot_row = r
                break

        self.assertIsNotNone(nhatot_row)
        self.assertEqual(nhatot_row[price_idx], "")
        self.assertEqual(nhatot_row[unit_price_idx], "")

    def test_publish_powerbi_marts_validation_failure(self):
        # Create invalid/empty files to force validation failures
        snapshot_table_dir = self.gold_dir / "gold_listing_snapshots"
        quality_table_dir = self.gold_dir / "gold_data_quality_daily"
        snapshot_table_dir.mkdir(parents=True, exist_ok=True)
        quality_table_dir.mkdir(parents=True, exist_ok=True)

        pd.DataFrame([]).to_parquet(snapshot_table_dir / "part-0000.parquet", index=False)
        pd.DataFrame([]).to_parquet(quality_table_dir / "part-0000.parquet", index=False)

        # Execution should abort and return False
        success = publish_powerbi_marts(
            gold_base_path=self.gold_dir,
            warehouse_base_path=self.warehouse_dir,
            powerbi_base_path=self.powerbi_dir,
        )

        self.assertFalse(success)


if __name__ == "__main__":
    unittest.main()
