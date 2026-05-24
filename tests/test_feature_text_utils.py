import math
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from parsing.sources.batdongsan.feature_text_utils import build_search_text, normalize_text


class FeatureTextUtilsTest(unittest.TestCase):
    def test_normalize_vietnamese_text(self):
        self.assertEqual(normalize_text("  Nhà Đẹp Hà Nội 50 m²\n"), "nha dep ha noi 50 m2")

    def test_normalize_empty_values(self):
        self.assertEqual(normalize_text(None), "")
        self.assertEqual(normalize_text("   "), "")

    def test_build_search_text_skips_blank_and_nan(self):
        normalized, raw = build_search_text(
            {
                "title_raw": "Nhà đẹp",
                "description_raw": "  ",
                "location_raw": float("nan"),
                "property_type_raw": "nha-rieng",
                "project_raw": None,
            }
        )

        self.assertEqual(raw, "Nhà đẹp nha-rieng")
        self.assertEqual(normalized, "nha dep nha-rieng")


if __name__ == "__main__":
    unittest.main()
