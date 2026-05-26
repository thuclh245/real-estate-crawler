import shutil
import sys
import unittest
from pathlib import Path
from uuid import uuid4

import pandas as pd
import yaml


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from common.utils import today_str
from crawler.sources.nhatot.smoke_crawl import load_source_config, run_nhatot_smoke_crawl
from transform.bronze_to_silver import run_bronze_to_silver
from validation.check_warehouse import check_warehouse_summary, check_warehouse_tables
from warehouse import build_warehouse_outputs


LIST_PAGE_HTML = (ROOT / "tests" / "fixtures" / "nhatot" / "list_page_sample.html").read_text(
    encoding="utf-8"
)
DETAIL_PAGE_HTML = (
    ROOT / "tests" / "fixtures" / "nhatot" / "detail_page_sample.html"
).read_text(encoding="utf-8")


def fake_fetch_with_retry(url: str, mode: str, max_retries: int, retry_delay_seconds: float):
    if "/111.htm" in url:
        return 200, DETAIL_PAGE_HTML, url, 0, None
    return 200, LIST_PAGE_HTML, url, 0, None


class NhatotGoldWarehouseFlowTest(unittest.TestCase):
    def setUp(self):
        self.base_dir = ROOT / "tests" / "tmp_runtime" / "nhatot_gold_warehouse" / uuid4().hex

    def tearDown(self):
        shutil.rmtree(self.base_dir, ignore_errors=True)

    def _write_smoke_config(self) -> Path:
        source_config = load_source_config(ROOT / "configs" / "sources" / "nhatot.yaml")
        source_config["crawl"]["request_delay_seconds"] = 0
        source_config["crawl"]["max_listings_per_target"] = 1
        source_config["targets"] = [
            target
            for target in source_config["targets"]
            if target["property_type_group"] == "apartment"
            and target["location_path"] == "quan-cau-giay-ha-noi"
        ][:1]

        config_path = self.base_dir / "configs" / "nhatot_smoke.yaml"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(
            yaml.safe_dump(source_config, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )
        return config_path

    def _build_nhatot_silver(self) -> tuple[pd.Series, str]:
        summary = run_nhatot_smoke_crawl(
            config_path=self._write_smoke_config(),
            base_dir=self.base_dir,
            fetch_with_retry_fn=fake_fetch_with_retry,
        )
        crawl_date = today_str()
        crawl_id = summary["crawl_id"]
        bronze_crawl_dir = (
            self.base_dir
            / "bronze"
            / "source=nhatot"
            / f"crawl_date={crawl_date}"
            / f"crawl_id={crawl_id}"
        )
        silver_crawl_dir = (
            self.base_dir
            / "silver"
            / "source=nhatot"
            / f"crawl_date={crawl_date}"
            / f"crawl_id={crawl_id}"
        )

        run_bronze_to_silver(
            bronze_dir=str(bronze_crawl_dir),
            silver_dir=str(silver_crawl_dir),
            parser_version="nhatot_adapter_v0.1",
        )
        silver_df = pd.read_parquet(silver_crawl_dir / "listings.parquet")
        self.assertEqual(len(silver_df), 1)
        return silver_df.iloc[0], crawl_date

    def _write_gold_fixture(self, silver_row: pd.Series, crawl_date: str) -> Path:
        gold_dir = self.base_dir / "gold"
        snapshot_dir = gold_dir / "gold_listing_snapshots"
        quality_dir = gold_dir / "gold_data_quality_daily"
        snapshot_dir.mkdir(parents=True, exist_ok=True)
        quality_dir.mkdir(parents=True, exist_ok=True)

        snapshot_row = {
            "snapshot_date": crawl_date,
            "crawl_date": crawl_date,
            "source": "nhatot",
            "source_code": "nhatot",
            "listing_id": str(silver_row["listing_id"]),
            "listing_url": silver_row["listing_url"],
            "dedup_key": silver_row["dedup_key"],
            "city_norm": silver_row["city_norm"],
            "district_norm": silver_row["district_norm"],
            "ward_norm": silver_row.get("ward_norm"),
            "property_type_group": silver_row["property_type_group"],
            "price_vnd": int(silver_row["price_vnd"]),
            "area_m2": float(silver_row["area_m2"]),
            "unit_price_vnd_m2": float(silver_row["unit_price_vnd_m2"]),
            "bedroom_count": int(silver_row["bedroom_count"]),
            "bathroom_count": int(silver_row["bathroom_count"]),
            "frontage_width_m": None,
            "quality_score": 20,
            "snapshot_status": "active",
            "is_new_listing": True,
            "is_active_listing": True,
            "is_removed_listing": False,
            "is_price_changed": False,
            "is_info_changed": False,
            "price_change_vnd": None,
            "price_change_pct": None,
            "has_legal_info": False,
            "has_car_access": False,
            "is_price_negotiable": bool(silver_row["is_price_negotiable"]),
        }
        quality_row = {
            "crawl_date": crawl_date,
            "source": "nhatot",
            "source_code": "nhatot",
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
        }

        pd.DataFrame([snapshot_row]).to_parquet(snapshot_dir / "part-0000.parquet", index=False)
        pd.DataFrame([quality_row]).to_parquet(quality_dir / "part-0000.parquet", index=False)
        return gold_dir

    def test_nhatot_silver_gold_fixture_builds_valid_warehouse(self):
        silver_row, crawl_date = self._build_nhatot_silver()
        gold_dir = self._write_gold_fixture(silver_row, crawl_date)
        warehouse_dir = self.base_dir / "warehouse"

        result = build_warehouse_outputs(
            gold_base_path=gold_dir,
            warehouse_base_path=warehouse_dir,
        )

        check_warehouse_summary(warehouse_dir)
        check_warehouse_tables(warehouse_dir, gold_dir)

        dim_source_df = pd.read_parquet(warehouse_dir / "dim_source" / "part-0000.parquet")
        nhatot_source = dim_source_df.loc[dim_source_df["source_code"] == "nhatot"].iloc[0]
        self.assertEqual(int(nhatot_source["source_key"]), 2)
        self.assertEqual(nhatot_source["source_domain"], "nhatot.com")

        dim_listing_df = pd.read_parquet(warehouse_dir / "dim_listing" / "part-0000.parquet")
        nhatot_listing = dim_listing_df.loc[dim_listing_df["source_key"] == 2].iloc[0]
        self.assertEqual(str(nhatot_listing["source_listing_id"]), "111")
        self.assertEqual(nhatot_listing["dedup_key"], "nhatot::111")
        self.assertEqual(nhatot_listing["listing_identity_method"], "listing_id")

        dim_property_type_df = pd.read_parquet(
            warehouse_dir / "dim_property_type" / "part-0000.parquet"
        )
        self.assertIn("apartment", set(dim_property_type_df["property_type_group"]))

        fact_df = pd.read_parquet(warehouse_dir / "fact_listing_snapshot" / "part-0000.parquet")
        self.assertEqual(len(fact_df), 1)
        fact_row = fact_df.iloc[0]
        expected_date_key = int(crawl_date.replace("-", ""))
        self.assertEqual(int(fact_row["source_key"]), 2)
        self.assertEqual(int(fact_row["snapshot_date_key"]), expected_date_key)
        self.assertEqual(int(fact_row["price_vnd"]), 3200000000)
        self.assertEqual(float(fact_row["area_m2"]), 65.0)
        self.assertTrue(pd.notna(fact_row["listing_key"]))
        self.assertTrue(pd.notna(fact_row["location_key"]))
        self.assertTrue(pd.notna(fact_row["property_type_key"]))

        quality_fact_df = pd.read_parquet(
            warehouse_dir / "fact_data_quality_daily" / "part-0000.parquet"
        )
        self.assertEqual(len(quality_fact_df), 1)
        self.assertEqual(int(quality_fact_df.iloc[0]["source_key"]), 2)
        self.assertEqual(int(quality_fact_df.iloc[0]["crawl_date_key"]), expected_date_key)

        self.assertEqual(result.summary["table_row_counts"]["fact_listing_snapshot"], 1)
        self.assertIn("nhatot", result.summary["source_codes"])


if __name__ == "__main__":
    unittest.main()
