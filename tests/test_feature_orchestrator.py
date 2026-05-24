import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from parsing import FEATURE_OUTPUT_KEYS, extract_features


class FeatureOrchestratorTest(unittest.TestCase):
    def test_extract_features_returns_stable_schema(self):
        result = extract_features(
            {
                "title_raw": "Chinh chu ban nha 4 tang",
                "description_raw": "So do, mat tien 5m, 3 phong ngu, o to vao nha",
                "property_type_group": "house",
            }
        )

        self.assertEqual(list(result.keys()), FEATURE_OUTPUT_KEYS)
        self.assertTrue(result["has_legal_info"])
        self.assertEqual(result["floor_count"], 4)
        self.assertEqual(result["frontage_width"], 5.0)
        self.assertEqual(result["bedroom_count"], 3)
        self.assertTrue(result["has_car_access"])

    def test_extract_features_apartment_skip_rules(self):
        result = extract_features(
            {
                "title_raw": "Can ho toa S1",
                "description_raw": "nha 5 tang mat tien 8m o to vao",
                "property_type_group": "apartment",
            }
        )

        self.assertIsNone(result["floor_count"])
        self.assertIsNone(result["frontage_width"])
        self.assertIsNone(result["has_car_access"])
        self.assertIsNone(result["car_access_type"])

    def test_extract_features_empty_input_all_null(self):
        result = extract_features({})
        self.assertEqual(list(result.keys()), FEATURE_OUTPUT_KEYS)
        self.assertTrue(all(value is None for value in result.values()))

    def test_extract_features_preserves_existing_seller_type(self):
        result = extract_features(
            {
                "title_raw": "Ban nha dep",
                "description_raw": "gan cong vien",
                "seller_type": "broker",
            }
        )

        self.assertEqual(result["seller_type"], "broker")


if __name__ == "__main__":
    unittest.main()
