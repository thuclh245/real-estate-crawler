import json
import shutil
import sys
import unittest
from pathlib import Path
from uuid import uuid4

import yaml


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from validation.preflight import EXIT_PASS, run_preflight


class SourceConfigsTest(unittest.TestCase):
    def setUp(self):
        self.base_dir = ROOT / "tests" / "tmp_runtime" / "source_configs" / uuid4().hex

    def tearDown(self):
        shutil.rmtree(self.base_dir, ignore_errors=True)

    def test_nhatot_source_config_contract(self):
        config_path = ROOT / "configs" / "sources" / "nhatot.yaml"
        self.assertTrue(config_path.exists())

        config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        required_top_level = {
            "source_code",
            "source_domain",
            "source_type",
            "is_active",
            "fetch_mode",
            "crawl",
            "compatibility",
            "targets",
            "output",
            "quality",
        }
        self.assertTrue(required_top_level.issubset(set(config)))
        self.assertEqual(config["source_code"], "nhatot")
        self.assertEqual(config["source_domain"], "nhatot.com")
        self.assertEqual(config["source_type"], "web_listing")
        self.assertIs(config["is_active"], True)
        self.assertEqual(config["fetch_mode"], "requests")

        crawl = config["crawl"]
        self.assertEqual(crawl["max_pages_per_target"], 20)
        self.assertEqual(crawl["max_listings_per_target"], 200)
        self.assertGreaterEqual(float(crawl["request_delay_seconds"]), 1.5)
        self.assertEqual(crawl["concurrency"], 1)
        self.assertEqual(crawl["max_retries"], 1)
        self.assertEqual(crawl["retry_delay_seconds"], 10)

        api = config["api"]
        self.assertIs(api["enabled"], True)
        self.assertEqual(api["daily_listing_cap"], 1500)
        self.assertEqual(api["region_id"], 12)

        compatibility = config["compatibility"]
        self.assertEqual(compatibility["current_config_paths"], [])
        self.assertIs(compatibility["production_enabled"], True)
        self.assertEqual(compatibility["production_scope"], "api_daily_1000")
        self.assertEqual(compatibility["onboarding_status"], "production_api_enabled")

        promotion = config["promotion"]
        self.assertEqual(promotion["promotion_status"], "active")
        self.assertIsNone(promotion["block_reason"])
        self.assertIs(promotion["production_candidate"], True)
        legal_access_review = promotion["legal_access_review"]
        self.assertIs(legal_access_review["terms_reviewed"], True)
        self.assertIs(legal_access_review["robots_checked"], True)
        self.assertIs(legal_access_review["prohibited_login_required"], False)
        self.assertIs(
            legal_access_review["personal_contact_handling_documented"],
            False,
        )
        self.assertIs(legal_access_review["approved_fetch_mode_documented"], True)
        self.assertIs(legal_access_review["no_captcha_bypass_required"], True)

        self.assertEqual(config["output"]["bronze_base_path"], "data/bronze")
        self.assertEqual(config["quality"]["min_expected_records"], 800)
        self.assertEqual(config["quality"]["blocking_blocked_rate"], 0.5)
        self.assertEqual(config["quality"]["min_parse_success_rate"], 0.9)
        self.assertEqual(config["quality"]["max_missing_price_rate"], 0.5)
        self.assertEqual(config["quality"]["max_missing_area_rate"], 0.5)
        self.assertEqual(config["quality"]["max_missing_location_rate"], 0.5)
        self.assertEqual(config["quality"]["max_duplicate_rate"], 0.5)
        self.assertEqual(config["quality"]["max_quarantine_rate"], 0.5)

        expected_location_paths = {
            "quan-ba-dinh-ha-noi",
            "quan-bac-tu-liem-ha-noi",
            "quan-cau-giay-ha-noi",
            "quan-dong-da-ha-noi",
            "quan-ha-dong-ha-noi",
            "quan-hai-ba-trung-ha-noi",
            "quan-hoan-kiem-ha-noi",
            "quan-hoang-mai-ha-noi",
            "quan-long-bien-ha-noi",
            "quan-nam-tu-liem-ha-noi",
            "quan-tay-ho-ha-noi",
            "quan-thanh-xuan-ha-noi",
        }
        self.assertEqual(len(config["targets"]), len(expected_location_paths) * 2)
        self.assertEqual(
            {target["property_type_group"] for target in config["targets"]},
            {"apartment", "house"},
        )
        self.assertEqual(
            {target["location_path"] for target in config["targets"]},
            expected_location_paths,
        )
        for target in config["targets"]:
            self.assertIn("category", target)
            self.assertIn("location_path", target)
            self.assertIn("property_type_group", target)
            self.assertIn(target["location_path"], target["seed_url"])
            if target["property_type_group"] == "apartment":
                self.assertEqual(target["category"], "mua-ban-can-ho-chung-cu")
                self.assertIn("page=2", target["seed_url"])
            if target["property_type_group"] == "house":
                self.assertEqual(target["category"], "mua-ban-nha-dat")
                self.assertIn("page=4", target["seed_url"])

    def test_source_keys_register_nhatot(self):
        source_keys_path = ROOT / "configs" / "sources" / "source_keys.yaml"
        source_keys = yaml.safe_load(source_keys_path.read_text(encoding="utf-8"))

        self.assertEqual(source_keys["unknown"], 0)
        self.assertEqual(source_keys["batdongsan"], 1)
        self.assertEqual(source_keys["nhatot"], 2)

    def test_metadata_catalog_points_to_nhatot_source_config(self):
        catalog_path = ROOT / "configs" / "metadata" / "table_catalog.json"
        catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
        source_by_code = {
            source["source_code"]: source for source in catalog["source_systems"]
        }

        self.assertIn("nhatot", source_by_code)
        nhatot = source_by_code["nhatot"]
        self.assertEqual(nhatot["source_domain"], "nhatot.com")
        self.assertEqual(nhatot["current_config_paths"], [])
        self.assertEqual(
            nhatot["active_target_v2_config"],
            "configs/sources/nhatot.yaml",
        )

    def test_preflight_accepts_nhatot_source_config(self):
        exit_code, payload, output_path = run_preflight(
            run_id="preflight_nhatot_source_config",
            config_paths=["configs/sources/nhatot.yaml"],
            output_dir=self.base_dir / "preflight",
        )

        self.assertEqual(exit_code, EXIT_PASS)
        self.assertEqual(payload["overall"], "pass")
        self.assertTrue(output_path.exists())

    def test_production_configs_use_nhatot_api_and_deprecate_old_nhatot_house_config(self):
        batdongsan_path = ROOT / "configs" / "team" / "batdongsan_house_150.yaml"
        nhatot_path = ROOT / "configs" / "sources" / "nhatot.yaml"
        deprecated_nhatot_path = ROOT / "configs" / "sources" / "nhatot_house_150.yaml"
        self.assertTrue(batdongsan_path.exists())
        self.assertTrue(nhatot_path.exists())
        self.assertTrue(deprecated_nhatot_path.exists())

        batdongsan = yaml.safe_load(batdongsan_path.read_text(encoding="utf-8"))
        self.assertEqual(batdongsan["source"], "batdongsan")
        self.assertEqual(batdongsan["source_domain"], "batdongsan.com.vn")
        self.assertEqual(
            batdongsan["crawl_settings"]["member_id"],
            "batdongsan_house_1000",
        )
        self.assertEqual(
            batdongsan["crawl_settings"]["max_pages_per_target"],
            7,
        )
        self.assertEqual(
            batdongsan["crawl_settings"]["max_listings_per_target"],
            84,
        )
        self.assertEqual(len(batdongsan["locations"]), 12)
        self.assertEqual(
            {category["property_type_group"] for category in batdongsan["categories"]},
            {"house"},
        )
        self.assertEqual(
            len(batdongsan["locations"])
            * len(batdongsan["categories"])
            * batdongsan["crawl_settings"]["max_listings_per_target"],
            1008,
        )
        self.assertEqual(batdongsan["quality"]["min_expected_records"], 800)

        nhatot = yaml.safe_load(nhatot_path.read_text(encoding="utf-8"))
        self.assertEqual(nhatot["source_code"], "nhatot")
        self.assertEqual(nhatot["source_domain"], "nhatot.com")
        self.assertEqual(nhatot["fetch_mode"], "requests")
        self.assertIs(nhatot["api"]["enabled"], True)
        self.assertEqual(nhatot["api"]["daily_listing_cap"], 1500)
        self.assertEqual(nhatot["crawl"]["max_pages_per_target"], 20)
        self.assertEqual(nhatot["crawl"]["max_listings_per_target"], 200)
        self.assertEqual(len(nhatot["targets"]), 24)
        self.assertEqual(
            {target["property_type_group"] for target in nhatot["targets"]},
            {"apartment", "house"},
        )
        self.assertEqual(
            len(nhatot["targets"]) * nhatot["crawl"]["max_listings_per_target"],
            4800,
        )
        self.assertEqual(nhatot["quality"]["min_expected_records"], 800)

        deprecated_nhatot = yaml.safe_load(
            deprecated_nhatot_path.read_text(encoding="utf-8")
        )
        self.assertIs(deprecated_nhatot["compatibility"]["production_enabled"], False)
        self.assertEqual(deprecated_nhatot["promotion"]["promotion_status"], "blocked")
        self.assertIs(deprecated_nhatot["promotion"]["production_candidate"], False)

        exit_code, payload, _ = run_preflight(
            run_id="preflight_house_150_configs",
            config_paths=[str(batdongsan_path), str(nhatot_path)],
            output_dir=self.base_dir / "preflight",
        )
        self.assertEqual(exit_code, EXIT_PASS)
        self.assertEqual(payload["overall"], "pass")


if __name__ == "__main__":
    unittest.main()
