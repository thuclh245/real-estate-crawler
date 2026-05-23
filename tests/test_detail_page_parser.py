import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from crawler.detail_page_parser import parse_detail_page_location_fields


class DetailPageParserTest(unittest.TestCase):
    def test_parse_detail_page_location_fields(self):
        fixture = ROOT / "tests" / "fixtures" / "batdongsan" / "detail_page_sample.html"
        html = fixture.read_text(encoding="utf-8")

        result = parse_detail_page_location_fields(html)
        self.assertEqual(result["detail_title"], "Tieu de bai dang")
        self.assertEqual(result["detail_address_raw"], "123 Pho Hue")
        self.assertEqual(result["breadcrumb_raw"], "Ha Noi / Hai Ba Trung")
        self.assertEqual(result["breadcrumb_location_raw"], "Ha Noi / Hai Ba Trung")
        self.assertEqual(result["detail_description"], "Mo ta chi tiet")

    def test_parse_detail_page_handles_missing_fields(self):
        result = parse_detail_page_location_fields("<html></html>")
        self.assertIsNone(result["detail_title"])
        self.assertIsNone(result["detail_address_raw"])
        self.assertIsNone(result["breadcrumb_raw"])
        self.assertIsNone(result["detail_description"])


if __name__ == "__main__":
    unittest.main()
