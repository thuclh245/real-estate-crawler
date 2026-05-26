import json
import shutil
import sys
import unittest
from pathlib import Path
from uuid import uuid4

import yaml
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from common.utils import today_str
from crawler.sources.nhatot.smoke_crawl import (
    build_smoke_crawl_config,
    load_source_config,
    run_nhatot_smoke_crawl,
)
from observability import (
    build_source_scorecard,
    load_silver_quality_summary,
    write_source_scorecard,
)
from transform.bronze_to_silver import run_bronze_to_silver


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


class NhatotSmokeCrawlTest(unittest.TestCase):
    def setUp(self):
        self.base_dir = ROOT / "tests" / "tmp_runtime" / "nhatot_smoke" / uuid4().hex

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

    def test_build_smoke_crawl_config_maps_source_config_to_orchestrator_config(self):
        source_config = load_source_config(ROOT / "configs" / "sources" / "nhatot.yaml")
        crawl_config = build_smoke_crawl_config(source_config)

        self.assertEqual(crawl_config["source"], "nhatot")
        self.assertEqual(crawl_config["source_domain"], "nhatot.com")
        self.assertEqual(crawl_config["base_url"], "https://www.nhatot.com")
        self.assertEqual(crawl_config["crawl_settings"]["fetch_mode"], "crawl4ai")
        self.assertEqual(crawl_config["crawl_settings"]["max_pages_per_target"], 1)
        self.assertGreaterEqual(
            crawl_config["crawl_settings"]["request_delay_seconds"],
            1.5,
        )
        self.assertGreaterEqual(len(crawl_config["targets"]), 1)

    def test_nhatot_smoke_crawl_writes_bronze_artifacts(self):
        config_path = self._write_smoke_config()

        summary = run_nhatot_smoke_crawl(
            config_path=config_path,
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

        self.assertEqual(summary["source"], "nhatot")
        self.assertEqual(summary["success_count"], 1)
        self.assertEqual(summary["metadata_file_count"], 1)
        self.assertTrue(bronze_crawl_dir.exists())

        metadata_files = list((bronze_crawl_dir / "metadata").glob("*.json"))
        raw_html_files = list((bronze_crawl_dir / "raw_html").glob("*.html"))
        raw_text_files = list((bronze_crawl_dir / "raw_text").glob("*.txt"))
        raw_json_files = list((bronze_crawl_dir / "raw_json").glob("*.json"))
        crawl_log_files = list((bronze_crawl_dir / "crawl_log").glob("*.json*"))

        self.assertEqual(len(metadata_files), 1)
        self.assertEqual(len(raw_html_files), 1)
        self.assertEqual(len(raw_text_files), 1)
        self.assertEqual(len(raw_json_files), 1)
        self.assertGreaterEqual(len(crawl_log_files), 1)

        metadata = json.loads(metadata_files[0].read_text(encoding="utf-8"))
        self.assertEqual(metadata["source"], "nhatot")
        self.assertEqual(metadata["listing_id"], "111")
        self.assertEqual(
            metadata["listing_url"],
            "https://www.nhatot.com/mua-ban-can-ho-chung-cu-quan-cau-giay-ha-noi/111.htm",
        )
        self.assertEqual(metadata["fetch_mode"], "crawl4ai")
        self.assertEqual(metadata["crawl_status"], "ok")
        self.assertEqual(metadata["property_type_group"], "apartment")
        self.assertEqual(metadata["crawl_location_path"], "quan-cau-giay-ha-noi")
        self.assertEqual(metadata["crawl_location_label"], "Cau Giay")
        self.assertEqual(metadata["detail_address_raw"], "So 1 Duong Cau Giay")
        self.assertTrue(Path(metadata["raw_html_path"]).exists())
        self.assertTrue(Path(metadata["raw_text_path"]).exists())
        self.assertTrue(Path(metadata["raw_json_path"]).exists())
        self.assertTrue(Path(metadata["metadata_path"]).exists())

    def test_nhatot_bronze_reprocesses_to_silver_conformed_row(self):
        config_path = self._write_smoke_config()
        summary = run_nhatot_smoke_crawl(
            config_path=config_path,
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

        self.assertTrue((silver_crawl_dir / "listings.parquet").exists())
        self.assertTrue((silver_crawl_dir / "data_quality_summary.json").exists())

        df = pd.read_parquet(silver_crawl_dir / "listings.parquet")
        self.assertEqual(len(df), 1)
        row = df.iloc[0]

        required_columns = {
            "source",
            "source_code",
            "crawl_date",
            "crawl_id",
            "listing_id",
            "listing_url",
            "dedup_key",
            "dedup_method",
            "title_raw",
            "description_raw",
            "price_raw",
            "price_vnd",
            "area_m2",
            "unit_price_vnd_m2",
            "property_type_group",
            "city_norm",
            "district_norm",
            "parse_status",
            "is_missing_price",
            "is_missing_area",
            "is_missing_location",
        }
        self.assertTrue(required_columns.issubset(set(df.columns)))
        self.assertEqual(row["source"], "nhatot")
        self.assertEqual(row["source_code"], "nhatot")
        self.assertEqual(row["listing_id"], "111")
        self.assertEqual(row["dedup_key"], "nhatot::111")
        self.assertEqual(row["dedup_method"], "listing_id")
        self.assertEqual(row["title_raw"], "Can ho 2 phong ngu Cau Giay")
        self.assertEqual(row["price_raw"], "3,2 ty")
        self.assertEqual(int(row["price_vnd"]), 3200000000)
        self.assertEqual(float(row["area_m2"]), 65.0)
        self.assertEqual(row["property_type_group"], "apartment")
        self.assertEqual(row["city_norm"], "Ha Noi")
        self.assertEqual(row["district_norm"], "Cau Giay")
        self.assertEqual(row["parse_status"], "success")
        self.assertFalse(bool(row["is_missing_price"]))
        self.assertFalse(bool(row["is_missing_area"]))
        self.assertFalse(bool(row["is_missing_location"]))

    def test_nhatot_smoke_crawl_builds_passing_source_scorecard(self):
        config_path = self._write_smoke_config()
        source_config = load_source_config(config_path)
        summary = run_nhatot_smoke_crawl(
            config_path=config_path,
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

        silver_quality_path = silver_crawl_dir / "data_quality_summary.json"
        scorecard = build_source_scorecard(
            crawl_summary={**summary, "crawl_date": crawl_date},
            silver_quality_summary=load_silver_quality_summary(silver_quality_path),
            quality_config=source_config["quality"],
            artifact_paths=[
                str(silver_crawl_dir / "listings.parquet"),
                str(silver_quality_path),
            ],
        )
        scorecard_path = write_source_scorecard(scorecard, self.base_dir / "logs")

        self.assertTrue(scorecard_path.exists())
        self.assertEqual(scorecard["source_code"], "nhatot")
        self.assertEqual(scorecard["crawl_date"], crawl_date)
        self.assertEqual(scorecard["crawl_id"], crawl_id)
        self.assertEqual(scorecard["total_records"], 1)
        self.assertEqual(scorecard["parse_success_rate"], 1.0)
        self.assertEqual(scorecard["gate_status"], "pass")
        self.assertEqual(scorecard["gate_failures"], [])


if __name__ == "__main__":
    unittest.main()
