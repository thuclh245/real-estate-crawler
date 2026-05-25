import json
import shutil
import sys
import unittest
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dashboard.data_loaders import (
    load_latest_production_summary,
    load_production_run_summaries,
    load_quarantine_counts,
    load_run_summaries,
)
from dashboard.pages.pipeline_health import _build_source_scorecards


class PipelineHealthTabTest(unittest.TestCase):
    def setUp(self):
        self.base_dir = ROOT / "tests" / "tmp_runtime" / "pipeline_health" / uuid4().hex

    def tearDown(self):
        shutil.rmtree(self.base_dir, ignore_errors=True)
        load_run_summaries.clear()
        load_production_run_summaries.clear()
        load_latest_production_summary.clear()
        load_quarantine_counts.clear()

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

    def test_load_latest_production_summary_prefers_pointer(self):
        run_dir = self.base_dir / "pipeline_runs"
        summary_path = run_dir / "run_id=prod_20260520_180000" / "run_summary.json"
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        summary_path.write_text(
            json.dumps(
                {
                    "run_id": "prod_20260520_180000",
                    "run_date": "2026-05-20",
                    "run_class": "production",
                    "pipeline_status": "success",
                    "publish_status": "published",
                    "parse_success_rate": 0.99,
                }
            ),
            encoding="utf-8",
        )
        pointer_path = run_dir / "latest_production.json"
        pointer_path.write_text(
            json.dumps({"summary_path": str(summary_path.relative_to(run_dir))}),
            encoding="utf-8",
        )

        payload = load_latest_production_summary(run_dir)

        self.assertEqual(payload["run_id"], "prod_20260520_180000")
        self.assertEqual(payload["parse_success_rate"], 0.99)

    def test_load_latest_production_summary_fallback_skips_smoke_and_blocked_runs(self):
        run_dir = self.base_dir / "pipeline_runs"
        self.write_production_summary(
            run_dir,
            "smoke_20260520_180000",
            {
                "run_id": "smoke_20260520_180000",
                "run_date": "2026-05-20",
                "run_class": "smoke",
                "pipeline_status": "success",
                "publish_status": "skipped",
            },
        )
        self.write_production_summary(
            run_dir,
            "blocked_20260521_180000",
            {
                "run_id": "blocked_20260521_180000",
                "run_date": "2026-05-21",
                "run_class": "production",
                "pipeline_status": "success",
                "publish_status": "blocked",
            },
        )
        self.write_production_summary(
            run_dir,
            "prod_20260519_180000",
            {
                "run_id": "prod_20260519_180000",
                "run_date": "2026-05-19",
                "run_class": "production",
                "pipeline_status": "success",
                "publish_status": "published",
            },
        )

        payload = load_latest_production_summary(run_dir)

        self.assertEqual(payload["run_id"], "prod_20260519_180000")

    def test_load_production_run_summaries_skips_invalid_json(self):
        run_dir = self.base_dir / "pipeline_runs"
        self.write_production_summary(
            run_dir,
            "prod_20260520_180000",
            {
                "run_id": "prod_20260520_180000",
                "run_date": "2026-05-20",
            },
        )
        bad_path = run_dir / "run_id=bad" / "run_summary.json"
        bad_path.parent.mkdir(parents=True, exist_ok=True)
        bad_path.write_text("{invalid json", encoding="utf-8")

        df = load_production_run_summaries(run_dir)

        self.assertEqual(len(df), 1)
        self.assertEqual(df.iloc[0]["run_id"], "prod_20260520_180000")

    def test_quarantine_counts_are_available_for_pipeline_health(self):
        quarantine_dir = self.base_dir / "quarantine"
        path = (
            quarantine_dir
            / "bronze_to_silver"
            / "source=batdongsan"
            / "date=2026-05-20"
            / "quarantine_prod_20260520_180000.jsonl"
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('{"record_identity":"1"}\n{"record_identity":"2"}\n', encoding="utf-8")

        df = load_quarantine_counts(quarantine_dir)

        self.assertEqual(len(df), 1)
        self.assertEqual(df.iloc[0]["rejection_stage"], "bronze_to_silver")
        self.assertEqual(df.iloc[0]["source_code"], "batdongsan")
        self.assertEqual(df.iloc[0]["quarantine_count"], 2)

    def test_source_scorecards_include_quarantine_count(self):
        production_df = load_production_run_summaries(
            self.seed_production_summary(
                {
                    "run_id": "prod_20260520_180000",
                    "run_date": "2026-05-20",
                    "source_names": ["batdongsan"],
                    "publish_status": "published",
                    "silver_records_written": 120,
                    "silver_quarantine_count": 2,
                }
            )
        )
        quarantine_df = load_quarantine_counts(self.base_dir / "missing_quarantine")

        rows = _build_source_scorecards(production_df, quarantine_df)

        self.assertEqual(rows[0]["source_code"], "batdongsan")
        self.assertEqual(rows[0]["silver_quarantine_count"], 2)

    def write_production_summary(self, run_dir, run_id, payload):
        summary_path = run_dir / f"run_id={run_id}" / "run_summary.json"
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        summary_path.write_text(json.dumps(payload), encoding="utf-8")
        return summary_path

    def seed_production_summary(self, payload):
        run_dir = self.base_dir / "pipeline_runs"
        self.write_production_summary(run_dir, payload["run_id"], payload)
        return run_dir


if __name__ == "__main__":
    unittest.main()
