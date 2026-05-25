import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from crawler.sources.batdongsan import BatdongsanAdapter


class BatdongsanAdapterTest(unittest.TestCase):
    def setUp(self):
        self.adapter = BatdongsanAdapter()

    def test_source_code_is_stable(self):
        self.assertEqual(self.adapter.source_code, "batdongsan")

    def test_build_seed_urls_uses_target_seed_url_override_with_pagination(self):
        config = {
            "base_url": "https://batdongsan.com.vn",
            "crawl_settings": {"max_pages_per_target": 2},
            "targets": [
                {
                    "category": "ban-nha-rieng",
                    "location_path": "phuong-cau-giay-tp-ha-noi",
                    "seed_url": "https://batdongsan.com.vn/ban-nha-rieng-phuong-cau-giay-tp-ha-noi",
                }
            ],
        }

        urls = self.adapter.build_seed_urls(config)

        self.assertEqual(
            urls,
            [
                "https://batdongsan.com.vn/ban-nha-rieng-phuong-cau-giay-tp-ha-noi",
                "https://batdongsan.com.vn/ban-nha-rieng-phuong-cau-giay-tp-ha-noi/p2",
            ],
        )

    def test_build_seed_urls_expands_category_location_config(self):
        config = {
            "base_url": "https://batdongsan.com.vn",
            "crawl_settings": {"max_pages_per_target": 2},
            "categories": [{"slug": "ban-nha-rieng", "label": "Ban nha"}],
            "locations": [{"location_path": "quan-1", "district_label": "Quan 1"}],
        }

        urls = self.adapter.build_seed_urls(config)

        self.assertEqual(
            urls,
            [
                "https://batdongsan.com.vn/ban-nha-rieng-quan-1",
                "https://batdongsan.com.vn/ban-nha-rieng-quan-1/p2",
            ],
        )

    def test_parse_list_page_delegates_to_current_batdongsan_parser(self):
        fixture = ROOT / "tests" / "fixtures" / "batdongsan" / "list_page_sample.html"
        html = fixture.read_text(encoding="utf-8")

        entries = self.adapter.parse_list_page(html)

        self.assertEqual(len(entries), 1)
        entry = entries[0]
        self.assertEqual(entry["listing_url"], "https://batdongsan.com.vn/ban-nha/pr123456")
        self.assertEqual(entry["listing_card_title"], "Nha pho dep")
        self.assertEqual(entry["listing_card_price_raw"], "10 ty")
        self.assertEqual(entry["listing_card_area_raw"], "100 m2")
        self.assertEqual(entry["listing_card_location_raw"], "Quan 1 (Quan 1 cu)")
        self.assertEqual(entry["listing_card_description"], "Mo ta ngan")

    def test_parse_detail_page_delegates_to_current_batdongsan_parser(self):
        fixture = ROOT / "tests" / "fixtures" / "batdongsan" / "detail_page_sample.html"
        html = fixture.read_text(encoding="utf-8")

        result = self.adapter.parse_detail_page(html)

        self.assertEqual(result["detail_title"], "Tieu de bai dang")
        self.assertEqual(result["detail_address_raw"], "123 Pho Hue")
        self.assertEqual(result["breadcrumb_raw"], "Ha Noi / Hai Ba Trung")
        self.assertEqual(result["breadcrumb_location_raw"], "Ha Noi / Hai Ba Trung")
        self.assertEqual(result["detail_description"], "Mo ta chi tiet")

    def test_parse_detail_page_handles_missing_fields(self):
        result = self.adapter.parse_detail_page("<html></html>")

        self.assertIsNone(result["detail_title"])
        self.assertIsNone(result["detail_address_raw"])
        self.assertIsNone(result["breadcrumb_raw"])
        self.assertIsNone(result["breadcrumb_location_raw"])
        self.assertIsNone(result["detail_description"])


if __name__ == "__main__":
    unittest.main()
