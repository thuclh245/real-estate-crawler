import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from crawler.list_page_parser import (
    extract_listing_entries_from_listing_page,
    extract_listing_urls_from_listing_page,
)


class ListPageParserTest(unittest.TestCase):
    def test_extract_entries_and_urls(self):
        fixture = ROOT / "tests" / "fixtures" / "batdongsan" / "list_page_sample.html"
        html = fixture.read_text(encoding="utf-8")

        entries = extract_listing_entries_from_listing_page(html)
        self.assertEqual(len(entries), 1)

        entry = entries[0]
        self.assertEqual(
            entry["listing_url"], "https://batdongsan.com.vn/ban-nha/pr123456"
        )
        self.assertEqual(entry["listing_card_title"], "Nha pho dep")
        self.assertEqual(entry["listing_card_price_raw"], "10 ty")
        self.assertEqual(entry["listing_card_area_raw"], "100 m2")
        self.assertEqual(entry["listing_card_location_raw"], "Quan 1 (Quan 1 cu)")
        self.assertEqual(entry["listing_card_old_district_raw"], "Quan 1 cu")
        self.assertEqual(entry["listing_card_description"], "Mo ta ngan")

        urls = extract_listing_urls_from_listing_page(html)
        self.assertEqual(urls, [entry["listing_url"]])


if __name__ == "__main__":
    unittest.main()
