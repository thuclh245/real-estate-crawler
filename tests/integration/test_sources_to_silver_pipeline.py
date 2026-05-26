import json
import shutil
import sys
import unittest
from pathlib import Path
from uuid import uuid4

import pandas as pd
import yaml


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from pipeline.sources_to_silver import run_sources_to_silver


BATDONGSAN_LIST_PAGE_HTML = """
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

BATDONGSAN_DETAIL_PAGE_HTML = """
<html>
  <body>
    <h1 class="re__pr-title">Tieu de bai dang</h1>
    <div class="re__address-line-1">123 Pho Hue</div>
    <div class="re__breadcrumb">Ha Noi / Quan 1</div>
    <div class="re__section-body">Mo ta chi tiet</div>
  </body>
</html>
"""

NHATOT_LIST_PAGE_HTML = (
    ROOT / "tests" / "fixtures" / "nhatot" / "list_page_sample.html"
).read_text(encoding="utf-8")
NHATOT_DETAIL_PAGE_HTML = (
    ROOT / "tests" / "fixtures" / "nhatot" / "detail_page_sample.html"
).read_text(encoding="utf-8")


def fake_fetch_with_retry(url: str, mode: str, max_retries: int, retry_delay_seconds: float):
    if "nhatot.com" in url and "/111.htm" in url:
        return 200, NHATOT_DETAIL_PAGE_HTML, url, 0, None
    if "nhatot.com" in url:
        return 200, NHATOT_LIST_PAGE_HTML, url, 0, None
    if "pr123456" in url:
        return 200, BATDONGSAN_DETAIL_PAGE_HTML, url, 0, None
    return 200, BATDONGSAN_LIST_PAGE_HTML, url, 0, None


class SourcesToSilverPipelineTest(unittest.TestCase):
    def setUp(self):
        self.base_dir = ROOT / "tests" / "tmp_runtime" / "sources_to_silver" / uuid4().hex

    def tearDown(self):
        shutil.rmtree(self.base_dir, ignore_errors=True)

    def _write_batdongsan_config(self) -> Path:
        config = {
            "source": "batdongsan",
            "source_domain": "batdongsan.com.vn",
            "base_url": "https://batdongsan.com.vn",
            "crawl_settings": {
                "max_pages_per_target": 1,
                "max_listings_per_target": 1,
                "request_delay_seconds": 0,
                "fetch_mode": "requests",
                "max_retries": 0,
                "retry_delay_seconds": 0,
            },
            "categories": [{"slug": "ban-nha-rieng", "label": "Ban nha"}],
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
        path = self.base_dir / "configs" / "batdongsan.yaml"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            yaml.safe_dump(config, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )
        return path

    def _write_nhatot_config(self) -> Path:
        config = yaml.safe_load(
            (ROOT / "configs" / "sources" / "nhatot.yaml").read_text(
                encoding="utf-8"
            )
        )
        config["crawl"]["request_delay_seconds"] = 0
        config["crawl"]["max_listings_per_target"] = 1
        config["targets"] = [
            target
            for target in config["targets"]
            if target["property_type_group"] == "apartment"
            and target["location_path"] == "quan-cau-giay-ha-noi"
        ][:1]
        path = self.base_dir / "configs" / "nhatot.yaml"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            yaml.safe_dump(config, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )
        return path

    def _write_blocked_nhatot_config(self) -> Path:
        config = yaml.safe_load(
            (ROOT / "configs" / "sources" / "nhatot_house_150.yaml").read_text(
                encoding="utf-8"
            )
        )
        config["crawl"]["request_delay_seconds"] = 0
        config["crawl"]["max_listings_per_target"] = 1
        config["quality"]["min_expected_records"] = 1
        config["targets"] = config["targets"][:1]
        path = self.base_dir / "configs" / "nhatot_blocked.yaml"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            yaml.safe_dump(config, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )
        return path

    def test_runner_writes_source_aware_bronze_silver_and_scorecards(self):
        summary = run_sources_to_silver(
            config_paths=[self._write_batdongsan_config(), self._write_nhatot_config()],
            base_dir=self.base_dir,
            fetch_with_retry_fn=fake_fetch_with_retry,
        )

        self.assertEqual(summary["source_names"], ["batdongsan", "nhatot"])
        self.assertEqual(len(summary["runs"]), 2)
        runs_by_source = {run["source"]: run for run in summary["runs"]}

        for source, run in runs_by_source.items():
            bronze_dir = Path(run["bronze_dir"])
            silver_dir = Path(run["silver_dir"])
            self.assertIn(f"source={source}", str(bronze_dir))
            self.assertIn(f"source={source}", str(silver_dir))
            self.assertTrue((silver_dir / "listings.parquet").exists())
            self.assertTrue(Path(run["source_scorecard_path"]).exists())

        nhatot_df = pd.read_parquet(
            Path(runs_by_source["nhatot"]["silver_dir"]) / "listings.parquet"
        )
        self.assertEqual(len(nhatot_df), 1)
        nhatot_row = nhatot_df.iloc[0]
        self.assertEqual(nhatot_row["source"], "nhatot")
        self.assertEqual(nhatot_row["source_code"], "nhatot")
        self.assertEqual(nhatot_row["listing_id"], "111")
        self.assertEqual(nhatot_row["dedup_key"], "nhatot::111")
        self.assertEqual(int(nhatot_row["price_vnd"]), 3200000000)
        self.assertEqual(float(nhatot_row["area_m2"]), 65.0)
        self.assertEqual(nhatot_row["city_norm"], "Ha Noi")
        self.assertEqual(nhatot_row["district_norm"], "Cau Giay")

        scorecard = json.loads(
            Path(runs_by_source["nhatot"]["source_scorecard_path"]).read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(scorecard["source_code"], "nhatot")
        self.assertEqual(scorecard["gate_status"], "pass")

    def test_optional_source_with_no_metadata_writes_failed_scorecard_without_crashing(self):
        def blocked_fetch(url: str, mode: str, max_retries: int, retry_delay_seconds: float):
            return 200, "<html><body>Access denied</body></html>", url, 0, None

        summary = run_sources_to_silver(
            config_paths=[self._write_blocked_nhatot_config()],
            base_dir=self.base_dir,
            fetch_with_retry_fn=blocked_fetch,
        )

        self.assertEqual(summary["source_names"], ["nhatot"])
        run = summary["runs"][0]
        self.assertEqual(run["status"], "skipped_no_metadata")
        self.assertEqual(run["silver_validation"]["row_count"], 0)
        self.assertFalse((Path(run["silver_dir"]) / "listings.parquet").exists())

        scorecard = json.loads(
            Path(run["source_scorecard_path"]).read_text(encoding="utf-8")
        )
        self.assertEqual(scorecard["source_code"], "nhatot")
        self.assertEqual(scorecard["total_records"], 0)
        self.assertEqual(scorecard["parse_success_rate"], 0.0)
        self.assertEqual(scorecard["gate_status"], "fail")
        self.assertTrue(scorecard["gate_failures"])

    def test_nhatot_cloudflare_block_halts_remaining_targets(self):
        config_path = self._write_blocked_nhatot_config()
        config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        second_target = dict(config["targets"][0])
        second_target["location_slug"] = "quan-cau-giay"
        second_target["location_path"] = "quan-cau-giay-ha-noi"
        second_target["location_label"] = "Cau Giay"
        second_target["seed_url"] = (
            "https://www.nhatot.com/mua-ban-nha-dat-quan-cau-giay-ha-noi?page=4"
        )
        config["targets"] = [config["targets"][0], second_target]
        config_path.write_text(
            yaml.safe_dump(config, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )
        calls = []
        challenge_html = (
            "<html><head><title>Just a moment...</title>"
            '<script src="https://challenges.cloudflare.com/turnstile/v0/api.js"></script>'
            "</head></html>"
        )

        def cloudflare_fetch(url: str, mode: str, max_retries: int, retry_delay_seconds: float):
            calls.append(url)
            return 307, challenge_html, url, 0, None

        summary = run_sources_to_silver(
            config_paths=[config_path],
            base_dir=self.base_dir,
            fetch_with_retry_fn=cloudflare_fetch,
        )

        run = summary["runs"][0]
        self.assertEqual(len(calls), 1)
        self.assertEqual(run["source_scorecard"]["blocked_count"], 1)
        self.assertEqual(
            run["source_scorecard"]["block_reasons"],
            {"cloudflare_turnstile": 1},
        )
        self.assertEqual(
            run["source_scorecard"]["halt_reason"],
            "blocked:cloudflare_turnstile",
        )


if __name__ == "__main__":
    unittest.main()
