import json
import sys
import unittest
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from crawler.bronze_writer import (
    append_crawl_log,
    build_listing_paths,
    write_metadata_json,
    write_raw_html,
)


class BronzeWriterTest(unittest.TestCase):
    def setUp(self):
        self.base_dir = ROOT / "tests" / "tmp_runtime" / "bronze_writer" / uuid4().hex

    def tearDown(self):
        if self.base_dir.exists():
            for path in sorted(self.base_dir.rglob("*"), reverse=True):
                if path.is_file():
                    path.unlink()
                else:
                    path.rmdir()

    def test_write_raw_html_and_metadata_and_log(self):
        source = "testsource"
        crawl_date = "2026-05-23"
        crawl_id = "testsource_20260523_000000"
        listing_id = "listing-1"

        raw_html_path = write_raw_html(
            html="<html>ok</html>",
            listing_id=listing_id,
            source=source,
            crawl_date=crawl_date,
            crawl_id=crawl_id,
            base_dir=self.base_dir,
        )
        self.assertTrue(raw_html_path.exists())

        metadata = {"listing_id": listing_id, "source": source}
        metadata_path = write_metadata_json(
            metadata=metadata,
            listing_id=listing_id,
            source=source,
            crawl_date=crawl_date,
            crawl_id=crawl_id,
            base_dir=self.base_dir,
        )
        self.assertTrue(metadata_path.exists())
        loaded = json.loads(metadata_path.read_text(encoding="utf-8"))
        self.assertEqual(loaded["listing_id"], listing_id)

        log_path = append_crawl_log(
            record={"listing_id": listing_id},
            source=source,
            crawl_date=crawl_date,
            crawl_id=crawl_id,
            base_dir=self.base_dir,
        )
        self.assertTrue(log_path.exists())

        paths = build_listing_paths(
            listing_id=listing_id,
            source=source,
            crawl_date=crawl_date,
            crawl_id=crawl_id,
            base_dir=self.base_dir,
        )
        self.assertIn(f"source={source}", str(paths["bronze_root"]))


if __name__ == "__main__":
    unittest.main()
