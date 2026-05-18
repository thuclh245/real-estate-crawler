import json
import shutil
import sys
import unittest
from pathlib import Path
from uuid import uuid4


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dashboard.app import load_run_summaries


class PipelineHealthTabTest(unittest.TestCase):
    def setUp(self):
        self.base_dir = ROOT / "tests" / "tmp_runtime" / "pipeline_health" / uuid4().hex

    def tearDown(self):
        shutil.rmtree(self.base_dir, ignore_errors=True)
        load_run_summaries.clear()

    def write_summary(self, run_date, payload):
        target = self.base_dir / f"run_date={run_date}" / "daily_run_summary.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(payload), encoding="utf-8")
        return target

    def test_load_run_summaries_reads_valid_json_files(self):
        self.write_summary(
            "2026-05-14",
            {
                "run_id": "daily_20260514_190001",
                "run_date": "2026-05-14",
                "parse_success_rate": 1.0,
            },
        )

        df = load_run_summaries(self.base_dir)

        self.assertEqual(len(df), 1)
        self.assertEqual(df.iloc[0]["run_id"], "daily_20260514_190001")
        self.assertIn("_summary_path", df.columns)

    def test_load_run_summaries_returns_empty_dataframe_when_missing(self):
        df = load_run_summaries(self.base_dir)

        self.assertTrue(df.empty)

    def test_load_run_summaries_skips_corrupted_json(self):
        self.write_summary(
            "2026-05-14",
            {
                "run_id": "daily_20260514_190001",
                "run_date": "2026-05-14",
            },
        )
        bad_path = self.base_dir / "run_date=2026-05-15" / "daily_run_summary.json"
        bad_path.parent.mkdir(parents=True, exist_ok=True)
        bad_path.write_text("{invalid json", encoding="utf-8")

        df = load_run_summaries(self.base_dir)

        self.assertEqual(len(df), 1)
        self.assertEqual(df.iloc[0]["run_date"], "2026-05-14")


if __name__ == "__main__":
    unittest.main()
