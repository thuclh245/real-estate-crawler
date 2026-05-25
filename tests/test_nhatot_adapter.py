import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from crawler.sources.nhatot import NhatotAdapter
from crawler.sources.nhatot.adapter import extract_ads_from_state, extract_next_state


class NhatotAdapterTest(unittest.TestCase):
    def setUp(self):
        self.adapter = NhatotAdapter()

    def test_source_code_is_stable(self):
        self.assertEqual(self.adapter.source_code, "nhatot")

    def test_build_seed_urls_uses_seed_url_override_with_query_pagination(self):
        config = {
            "base_url": "https://www.nhatot.com",
            "crawl_settings": {"max_pages_per_target": 2},
            "targets": [
                {
                    "category": "mua-ban-can-ho-chung-cu",
                    "location_path": "quan-cau-giay-ha-noi",
                    "seed_url": "https://www.nhatot.com/mua-ban-can-ho-chung-cu-quan-cau-giay-ha-noi",
                }
            ],
        }

        urls = self.adapter.build_seed_urls(config)

        self.assertEqual(
            urls,
            [
                "https://www.nhatot.com/mua-ban-can-ho-chung-cu-quan-cau-giay-ha-noi",
                "https://www.nhatot.com/mua-ban-can-ho-chung-cu-quan-cau-giay-ha-noi?page=2",
            ],
        )

    def test_build_seed_urls_builds_from_category_and_location_path(self):
        config = {
            "base_url": "https://www.nhatot.com",
            "crawl_settings": {"max_pages_per_target": 2},
            "targets": [
                {
                    "category": "mua-ban-nha-dat",
                    "location_path": "quan-dong-da-ha-noi",
                }
            ],
        }

        urls = self.adapter.build_seed_urls(config)

        self.assertEqual(
            urls,
            [
                "https://www.nhatot.com/mua-ban-nha-dat-quan-dong-da-ha-noi",
                "https://www.nhatot.com/mua-ban-nha-dat-quan-dong-da-ha-noi?page=2",
            ],
        )

    def test_extract_next_state_and_ads_support_initial_state_path(self):
        fixture = ROOT / "tests" / "fixtures" / "nhatot" / "list_page_sample.html"
        html = fixture.read_text(encoding="utf-8")

        state = extract_next_state(html)
        ads = extract_ads_from_state(state)

        self.assertIsNotNone(state)
        self.assertEqual(len(ads), 2)

    def test_parse_list_page_maps_ads_to_adapter_contract(self):
        fixture = ROOT / "tests" / "fixtures" / "nhatot" / "list_page_sample.html"
        html = fixture.read_text(encoding="utf-8")

        entries = self.adapter.parse_list_page(html)

        self.assertEqual(len(entries), 2)
        first = entries[0]
        self.assertEqual(first["source"], "nhatot")
        self.assertEqual(first["source_code"], "nhatot")
        self.assertEqual(first["listing_id"], "111")
        self.assertEqual(
            first["listing_url"],
            "https://www.nhatot.com/mua-ban-can-ho-chung-cu-quan-cau-giay-ha-noi/111.htm",
        )
        self.assertEqual(first["listing_card_title"], "Can ho 2 phong ngu Cau Giay")
        self.assertEqual(first["listing_card_price_raw"], "3,2 ty")
        self.assertEqual(first["listing_card_area_raw"], "65 m2")
        self.assertEqual(first["listing_card_location_raw"], "Dich Vong, Cau Giay, Ha Noi")
        self.assertEqual(first["listing_card_description"], "Can ho gan cong vien, so hong day du")
        self.assertEqual(first["property_type_group"], "apartment")
        self.assertEqual(first["city_raw"], "Ha Noi")
        self.assertEqual(first["district_raw"], "Cau Giay")
        self.assertEqual(first["ward_raw"], "Dich Vong")
        self.assertEqual(first["bedroom_count"], 2)
        self.assertEqual(first["bathroom_count"], 2)

        second = entries[1]
        self.assertEqual(second["source"], "nhatot")
        self.assertEqual(second["listing_id"], "222")
        self.assertIsNone(second["listing_card_price_raw"])
        self.assertIsNone(second["listing_card_area_raw"])
        self.assertEqual(second["listing_card_location_raw"], "Dong Da, Ha Noi")

    def test_parse_list_page_handles_empty_and_invalid_pages(self):
        empty_fixture = ROOT / "tests" / "fixtures" / "nhatot" / "list_page_empty.html"

        self.assertEqual(self.adapter.parse_list_page(empty_fixture.read_text(encoding="utf-8")), [])
        self.assertEqual(self.adapter.parse_list_page("<html></html>"), [])

    def test_parse_detail_page_maps_next_state_to_crawler_detail_contract(self):
        fixture = ROOT / "tests" / "fixtures" / "nhatot" / "detail_page_sample.html"
        html = fixture.read_text(encoding="utf-8")

        result = self.adapter.parse_detail_page(html)

        self.assertEqual(result["detail_title"], "Can ho 2 phong ngu Cau Giay")
        self.assertEqual(result["detail_address_raw"], "So 1 Duong Cau Giay")
        self.assertEqual(result["breadcrumb_raw"], "Ha Noi / Cau Giay / Dich Vong")
        self.assertEqual(result["breadcrumb_location_raw"], "Ha Noi / Cau Giay / Dich Vong")
        self.assertEqual(result["detail_description"], "Can ho gan cong vien, so hong day du")

    def test_parse_detail_page_handles_missing_fields(self):
        result = self.adapter.parse_detail_page("<html></html>")

        self.assertIsNone(result["detail_title"])
        self.assertIsNone(result["detail_address_raw"])
        self.assertIsNone(result["breadcrumb_raw"])
        self.assertIsNone(result["breadcrumb_location_raw"])
        self.assertIsNone(result["detail_description"])


if __name__ == "__main__":
    unittest.main()
