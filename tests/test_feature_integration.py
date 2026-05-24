import json
import shutil
import sys
import unittest
import uuid
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import pandas as pd

from parsing import FEATURE_OUTPUT_KEYS
from transform.bronze_to_silver import run_bronze_to_silver


class FeatureIntegrationTest(unittest.TestCase):
    def test_bronze_to_silver_enriches_feature_columns(self):
        tmp_root = ROOT / "tests" / "tmp_runtime"
        tmp_root.mkdir(exist_ok=True)
        tmp = tmp_root / f"run_{uuid.uuid4().hex}"
        tmp.mkdir()
        try:
            base = tmp
            bronze = base / "bronze"
            silver = base / "silver"
            metadata_dir = bronze / "metadata"
            raw_text_dir = bronze / "raw_text"
            raw_html_dir = bronze / "raw_html"
            metadata_dir.mkdir(parents=True)
            raw_text_dir.mkdir()
            raw_html_dir.mkdir()

            raw_text_path = raw_text_dir / "listing.txt"
            raw_html_path = raw_html_dir / "listing.html"
            raw_text_path.write_text(
                "Chinh chu ban nha 4 tang\n"
                "Gia 5 ty, dien tich 50 m2, so do, mat tien 5m, "
                "3 phong ngu, 2 wc, o to vao nha, co thuong luong",
                encoding="utf-8",
            )
            raw_html_path.write_text("<html></html>", encoding="utf-8")

            metadata = {
                "source": "test",
                "crawl_date": "2026-05-13",
                "crawl_id": "crawl-1",
                "listing_id": "listing-1",
                "listing_url": "https://example.test/listing-1",
                "crawl_category": "nha-rieng",
                "property_type_group": "house",
                "crawl_city_label": "Ha Noi",
                "crawl_district_label": "Cau Giay",
                "raw_text_path": str(raw_text_path),
                "raw_html_path": str(raw_html_path),
                "metadata_path": str(metadata_dir / "listing.json"),
            }
            (metadata_dir / "listing.json").write_text(
                json.dumps(metadata, ensure_ascii=False),
                encoding="utf-8",
            )

            run_bronze_to_silver(str(bronze), str(silver))

            df = pd.read_csv(silver / "listings.csv")
            for key in FEATURE_OUTPUT_KEYS:
                self.assertIn(key, df.columns)

            row = df.iloc[0]
            self.assertEqual(int(row["floor_count"]), 4)
            self.assertTrue(bool(row["is_price_negotiable"]))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
