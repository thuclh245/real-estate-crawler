import json
import shutil
import sys
import unittest
from pathlib import Path
from uuid import uuid4


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from observability import (
    SOURCE_SCORECARD_SCHEMA_VERSION,
    build_source_scorecard,
    write_source_scorecard,
)


class SourceScorecardTest(unittest.TestCase):
    def setUp(self):
        self.base_dir = ROOT / "tests" / "tmp_runtime" / "source_scorecard" / uuid4().hex
        self.quality_config = {
            "min_expected_records": 1,
            "min_parse_success_rate": 0.9,
            "blocking_blocked_rate": 0.5,
            "max_missing_price_rate": 0.5,
            "max_missing_area_rate": 0.5,
            "max_missing_location_rate": 0.5,
            "max_duplicate_rate": 0.5,
            "max_quarantine_rate": 0.5,
        }

    def tearDown(self):
        shutil.rmtree(self.base_dir, ignore_errors=True)

    def test_build_source_scorecard_normalizes_crawl_and_silver_metrics(self):
        scorecard = build_source_scorecard(
            crawl_summary={
                "source": "nhatot",
                "crawl_date": "2026-05-26",
                "crawl_id": "crawl-1",
                "success_count": 1,
                "failed_count": 0,
                "blocked_count": 0,
            },
            silver_quality_summary={
                "total_metadata_files": 1,
                "total_records_parsed": 1,
                "total_quarantined_records": 0,
                "parse_success_rate": 1.0,
                "is_missing_price_rate": 0.0,
                "is_missing_area_rate": 0.0,
                "is_missing_location_rate": 0.0,
            },
            quality_config=self.quality_config,
            artifact_paths=["silver/listings.parquet"],
        )

        self.assertEqual(
            scorecard["scorecard_schema_version"],
            SOURCE_SCORECARD_SCHEMA_VERSION,
        )
        self.assertEqual(scorecard["source_code"], "nhatot")
        self.assertEqual(scorecard["crawl_date"], "2026-05-26")
        self.assertEqual(scorecard["crawl_id"], "crawl-1")
        self.assertEqual(scorecard["run_id"], "crawl-1")
        self.assertEqual(scorecard["total_records"], 1)
        self.assertEqual(scorecard["parse_success_rate"], 1.0)
        self.assertEqual(scorecard["quarantine_count"], 0)
        self.assertEqual(scorecard["quarantine_rate"], 0.0)
        self.assertEqual(scorecard["success_count"], 1)
        self.assertEqual(scorecard["failed_count"], 0)
        self.assertEqual(scorecard["blocked_count"], 0)
        self.assertEqual(scorecard["blocked_rate"], 0.0)
        self.assertEqual(scorecard["gate_status"], "pass")
        self.assertEqual(scorecard["gate_failures"], [])
        self.assertEqual(scorecard["artifact_paths"], ["silver/listings.parquet"])

    def test_build_source_scorecard_defaults_missing_metrics_safely(self):
        scorecard = build_source_scorecard(
            crawl_summary={
                "source": "nhatot",
                "crawl_date": "2026-05-26",
                "crawl_id": "crawl-2",
                "success_count": 0,
                "failed_count": 1,
            },
            silver_quality_summary={},
            quality_config=self.quality_config,
        )

        self.assertEqual(scorecard["total_records"], 0)
        self.assertEqual(scorecard["parse_success_rate"], 0.0)
        self.assertEqual(scorecard["missing_price_rate"], 0.0)
        self.assertEqual(scorecard["duplicate_rate"], 0.0)
        self.assertEqual(scorecard["gate_status"], "fail")
        self.assertTrue(scorecard["gate_failures"])

    def test_write_source_scorecard_writes_expected_json_artifact(self):
        scorecard = build_source_scorecard(
            crawl_summary={
                "source": "nhatot",
                "crawl_date": "2026-05-26",
                "crawl_id": "crawl-3",
                "success_count": 1,
            },
            silver_quality_summary={
                "total_metadata_files": 1,
                "total_records_parsed": 1,
                "parse_success_rate": 1.0,
            },
            quality_config=self.quality_config,
        )

        path = write_source_scorecard(scorecard, self.base_dir)

        expected_path = (
            self.base_dir
            / "source_scorecards"
            / "source=nhatot"
            / "crawl_date=2026-05-26"
            / "crawl_id=crawl-3"
            / "source_scorecard.json"
        )
        self.assertEqual(path, expected_path)
        self.assertTrue(path.exists())
        self.assertEqual(json.loads(path.read_text(encoding="utf-8")), scorecard)


if __name__ == "__main__":
    unittest.main()
