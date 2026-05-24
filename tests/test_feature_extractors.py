import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from parsing.sources.batdongsan.feature_extractor import (
    extract_car_access,
    extract_direction,
    extract_floor_count,
    extract_frontage_width,
    extract_legal_status,
    extract_negotiable_price,
    extract_seller_type,
)


class FeatureExtractorsTest(unittest.TestCase):
    def test_extract_legal_status(self):
        result = extract_legal_status("nha da co so do sang ten ngay")
        self.assertTrue(result["has_legal_info"])
        self.assertTrue(result["has_red_pink_book"])
        self.assertEqual(result["legal_status_raw"], "da co so")

    def test_extract_floor_count_tret_lau(self):
        self.assertEqual(extract_floor_count("nha 1 tret 3 lau dep"), 4)

    def test_extract_seller_type_owner_negation(self):
        self.assertEqual(extract_seller_type("chinh chu ban nha mien moi gioi"), "owner")

    def test_extract_frontage_does_not_match_area(self):
        self.assertIsNone(extract_frontage_width("dien tich 50 m2"))
        self.assertEqual(extract_frontage_width("mat tien 4,5 m"), 4.5)

    def test_extract_direction_requires_prefix(self):
        self.assertIsNone(extract_direction("nam tu liem"))
        self.assertEqual(extract_direction("nha huong dong nam"), "dong_nam")

    def test_extract_negotiable_price_with_negation(self):
        self.assertFalse(extract_negotiable_price("gia net khong co thuong luong"))
        self.assertTrue(extract_negotiable_price("gia tot co thuong luong"))

    def test_extract_car_access_type(self):
        self.assertEqual(
            extract_car_access("ngo o to tranh, nha dep")["car_access_type"],
            "car_can_pass",
        )


if __name__ == "__main__":
    unittest.main()
