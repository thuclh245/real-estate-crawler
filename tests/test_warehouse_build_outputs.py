import shutil
import sys
import unittest
from pathlib import Path
from uuid import uuid4

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from warehouse import build_warehouse_outputs
from warehouse.orchestrator import build_warehouse_outputs as orchestrated_build
from validation.check_warehouse import check_warehouse_summary, check_warehouse_tables


class WarehouseBuildOutputsTest(unittest.TestCase):
    def test_build_and_validate_warehouse_outputs(self):
        tmp_root = ROOT / "tests" / "tmp_runtime"
        tmp_root.mkdir(exist_ok=True)
        tmp = tmp_root / f"warehouse_{uuid4().hex}"
        gold = tmp / "gold"
        warehouse = tmp / "warehouse"
        try:
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
                    "price_vnd": 3200000000,
                    "area_m2": 65.0,
                    "unit_price_vnd_m2": 49230769.23,
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
                {
                    "snapshot_date": "2026-05-15",
                    "source": "nhatot",
                    "listing_id": "999",
                    "listing_url": None,
                    "city_norm": None,
                    "district_norm": None,
                    "ward_norm": None,
                    "property_type_group": "land",
                    "price_vnd": None,
                    "area_m2": None,
                    "unit_price_vnd_m2": None,
                    "bedroom_count": None,
                    "bathroom_count": None,
                    "frontage_width_m": None,
                    "quality_score": 5,
                    "snapshot_status": "quarantine",
                    "is_new_listing": False,
                    "is_active_listing": False,
                    "is_removed_listing": True,
                    "is_price_changed": False,
                    "is_info_changed": False,
                    "price_change_vnd": None,
                    "price_change_pct": None,
                    "has_legal_info": None,
                    "has_car_access": None,
                    "is_price_negotiable": None,
                    "dedup_key": "nhatot::999",
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

            snapshot_table_dir = gold / "gold_listing_snapshots"
            quality_table_dir = gold / "gold_data_quality_daily"
            snapshot_table_dir.mkdir(parents=True, exist_ok=True)
            quality_table_dir.mkdir(parents=True, exist_ok=True)
            pd.DataFrame(snapshot_rows).to_parquet(
                snapshot_table_dir / "part-0000.parquet", index=False
            )
            pd.DataFrame(quality_rows).to_parquet(
                quality_table_dir / "part-0000.parquet", index=False
            )

            result = build_warehouse_outputs(
                gold_base_path=gold,
                warehouse_base_path=warehouse,
            )

            self.assertTrue((warehouse / "dim_source").exists())
            self.assertTrue((warehouse / "fact_listing_snapshot").exists())
            self.assertTrue((warehouse / "warehouse_summary.json").exists())

            dim_source_df = pd.read_parquet(
                warehouse / "dim_source" / "part-0000.parquet"
            )
            self.assertIn("source_key", dim_source_df.columns)
            self.assertGreaterEqual(len(dim_source_df), 3)

            fact_df = pd.read_parquet(
                warehouse / "fact_listing_snapshot" / "part-0000.parquet"
            )
            self.assertEqual(len(fact_df), 3)
            self.assertEqual(
                fact_df.drop_duplicates(
                    subset=["snapshot_date_key", "source_key", "listing_key"]
                ).shape[0],
                3,
            )

            check_warehouse_summary(warehouse)
            check_warehouse_tables(warehouse, gold)

            self.assertIn("fact_listing_snapshot", result.summary["table_row_counts"])
            self.assertEqual(
                result.summary["table_row_counts"]["fact_listing_snapshot"], 3
            )
            self.assertIs(orchestrated_build, build_warehouse_outputs)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
