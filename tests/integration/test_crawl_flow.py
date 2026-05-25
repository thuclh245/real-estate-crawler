import json
import sys
import unittest
from pathlib import Path
import shutil
from uuid import uuid4

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from common.utils import today_str
from crawler.crawl_config import load_config
from crawler.orchestrator import CrawlOrchestrator, CrawlDependencies
from transform.bronze_to_silver import run_bronze_to_silver


LIST_PAGE_HTML = """
<html>
  <body>
    <div class="js__card-listing">
      <a href="/ban-nha/pr123456">Listing</a>
      <div class="js__card-title">Nha pho</div>
      <div class="re__card-config-price">10 ty</div>
      <div class="re__card-config-area">100 m2</div>
      <div class="re__card-location">Quan 1</div>
      <div class="js__card-description">Mo ta ngan</div>
    </div>
  </body>
</html>
"""

DETAIL_PAGE_HTML = """
<html>
  <body>
    <h1 class="re__pr-title">Tieu de bai dang</h1>
    <div class="re__address-line-1">123 Pho Hue</div>
    <div class="re__breadcrumb">Ha Noi / Quan 1</div>
    <div class="re__section-body">Mo ta chi tiet</div>
  </body>
</html>
"""


def fake_fetch_with_retry(url: str, mode: str, max_retries: int, retry_delay_seconds: float):
    if "pr123456" in url:
        return 200, DETAIL_PAGE_HTML, url, 0, None
    return 200, LIST_PAGE_HTML, url, 0, None


class CrawlFlowTest(unittest.TestCase):
    def setUp(self):
        self.base_dir = ROOT / "tests" / "tmp_runtime" / "crawl_flow" / uuid4().hex

    def tearDown(self):
        shutil.rmtree(self.base_dir, ignore_errors=True)

    def test_crawl_flow_writes_bronze_files(self):
        config = {
            "source": "batdongsan",
            "base_url": "https://batdongsan.com.vn",
            "crawl_settings": {
                "max_pages_per_target": 1,
                "max_listings_per_target": 1,
                "request_delay_seconds": 0,
                "fetch_mode": "requests",
                "max_retries": 0,
                "retry_delay_seconds": 0,
            },
            "categories": [
                {"slug": "ban-nha-rieng", "label": "Ban nha"}
            ],
            "locations": [
                {
                    "district": "quan-1",
                    "location_path": "quan-1",
                    "district_label": "Quan 1",
                    "city": "ha-noi",
                    "city_label": "Ha Noi",
                    "city_slug": "ha-noi",
                }
            ],
        }

        dependencies = CrawlDependencies(fetch_with_retry_fn=fake_fetch_with_retry)
        orchestrator = CrawlOrchestrator(
            config,
            base_dir=self.base_dir,
            dependencies=dependencies,
        )
        summary = orchestrator.run()

        self.assertEqual(summary["success_count"], 1)

        metadata_files = list(self.base_dir.rglob("metadata/*.json"))
        self.assertEqual(len(metadata_files), 1)
        raw_html_files = list(self.base_dir.rglob("raw_html/*.html"))
        self.assertEqual(len(raw_html_files), 1)

        metadata = json.loads(metadata_files[0].read_text(encoding="utf-8"))
        self.assertEqual(metadata.get("source"), "batdongsan")
        self.assertEqual(metadata.get("listing_url"), "https://batdongsan.com.vn/ban-nha/pr123456")
        self.assertEqual(metadata.get("final_detail_url"), "https://batdongsan.com.vn/ban-nha/pr123456")
        self.assertEqual(metadata.get("crawl_status"), "ok")
        self.assertEqual(metadata.get("http_status"), 200)
        self.assertEqual(metadata.get("fetch_mode"), "requests")
        self.assertTrue(Path(metadata["raw_html_path"]).exists())
        self.assertTrue(Path(metadata["raw_text_path"]).exists())
        self.assertTrue(Path(metadata["raw_json_path"]).exists())
        self.assertTrue(Path(metadata["metadata_path"]).exists())

    def test_real_yaml_writes_bronze_and_silver_under_standard_source_partition(self):
        config = load_config(ROOT / "configs" / "crawl_targets.yaml")
        config["crawl_settings"]["request_delay_seconds"] = 0
        config["crawl_settings"]["max_pages_per_target"] = 1
        config["crawl_settings"]["max_listings_per_target"] = 1

        dependencies = CrawlDependencies(fetch_with_retry_fn=fake_fetch_with_retry)
        summary = CrawlOrchestrator(
            config,
            base_dir=self.base_dir,
            dependencies=dependencies,
        ).run()

        crawl_date = today_str()
        crawl_id = summary["crawl_id"]
        bronze_crawl_dir = (
            self.base_dir
            / "bronze"
            / "source=batdongsan"
            / f"crawl_date={crawl_date}"
            / f"crawl_id={crawl_id}"
        )
        silver_crawl_dir = (
            self.base_dir
            / "silver"
            / "source=batdongsan"
            / f"crawl_date={crawl_date}"
            / f"crawl_id={crawl_id}"
        )

        self.assertEqual(config["source"], "batdongsan")
        self.assertEqual(config["source_domain"], "batdongsan.com.vn")
        self.assertTrue(bronze_crawl_dir.exists())
        self.assertTrue((bronze_crawl_dir / "metadata").exists())
        self.assertGreater(len(list((bronze_crawl_dir / "metadata").glob("*.json"))), 0)

        run_bronze_to_silver(
            bronze_dir=str(bronze_crawl_dir),
            silver_dir=str(silver_crawl_dir),
        )

        self.assertTrue((silver_crawl_dir / "listings.parquet").exists())
        self.assertTrue((silver_crawl_dir / "data_quality_summary.json").exists())
        silver_df = pd.read_parquet(silver_crawl_dir / "listings.parquet")
        self.assertGreaterEqual(len(silver_df), 1)

        required_columns = {
            "source",
            "listing_id",
            "listing_url",
            "price_vnd",
            "area_m2",
            "city_norm",
            "district_norm",
        }
        self.assertTrue(required_columns.issubset(set(silver_df.columns)))
        first_row = silver_df.iloc[0]
        self.assertEqual(first_row["source"], "batdongsan")
        self.assertEqual(first_row["listing_id"], "123456")
        self.assertEqual(first_row["listing_url"], "https://batdongsan.com.vn/ban-nha/pr123456")
        self.assertFalse(
            (
                self.base_dir
                / "bronze"
                / "source=batdongsan.com.vn"
                / f"crawl_date={crawl_date}"
            ).exists()
        )


if __name__ == "__main__":
    unittest.main()
