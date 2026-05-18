import json
import shutil
import sys
import unittest
from pathlib import Path
from uuid import uuid4

from hypothesis import given, settings, strategies as st


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from observability import DailyRunSummary, REQUIRED_SUMMARY_FIELDS


class DailyRunSummaryTest(unittest.TestCase):
    def setUp(self):
        self.generator = DailyRunSummary()

    def test_generate_summary_contains_required_fields_with_expected_types(self):
        summary = self.generator.generate_summary(
            run_id="daily_20260514_190001",
            run_date="2026-05-14",
            pipeline_status="success",
            validation_status="pass",
            gcs_sync_status="success",
            start_time="2026-05-14T19:00:00+07:00",
            end_time="2026-05-14T19:30:00+07:00",
            duration_seconds=1800,
            gold_summary={
                "total_silver_records": "1200",
                "total_current_listings": 840,
                "duplicate_record_count": 24,
                "duplicate_rate": "0.02",
                "parse_success_rate": 1,
                "missing_price_rate": 0.1,
                "missing_area_rate": 0.0,
                "missing_location_rate": 0.0,
                "snapshot_dates": ("2026-05-13", "2026-05-14"),
            },
            crawl_configs=["configs/team/a.yaml"],
            crawl_ids_created=["batdongsan_20260514_190001"],
        )

        for field in REQUIRED_SUMMARY_FIELDS:
            self.assertIn(field, summary)

        self.assertEqual(summary["summary_schema_version"], "daily_run_summary_v1")
        self.assertIsInstance(summary["run_id"], str)
        self.assertIsInstance(summary["run_date"], str)
        self.assertIsInstance(summary["pipeline_status"], str)
        self.assertIsInstance(summary["validation_status"], str)
        self.assertIsInstance(summary["gcs_sync_status"], str)
        self.assertIsInstance(summary["total_silver_records"], int)
        self.assertIsInstance(summary["total_current_listings"], int)
        self.assertIsInstance(summary["duplicate_record_count"], int)
        self.assertIsInstance(summary["duplicate_rate"], float)
        self.assertIsInstance(summary["parse_success_rate"], float)
        self.assertIsInstance(summary["missing_price_rate"], float)
        self.assertIsInstance(summary["missing_area_rate"], float)
        self.assertIsInstance(summary["missing_location_rate"], float)
        self.assertIsInstance(summary["snapshot_dates"], list)
        self.assertIsInstance(summary["duration_seconds"], int)

    def test_generate_summary_marks_failed_state_when_error_is_present(self):
        summary = self.generator.generate_summary(
            run_id="daily_20260514_190001",
            run_date="2026-05-14",
            pipeline_status="success",
            validation_status="skipped",
            gcs_sync_status="skipped",
            start_time="2026-05-14T19:00:00+07:00",
            end_time="2026-05-14T19:01:00+07:00",
            duration_seconds=60,
            error_message="silver_to_gold failed",
        )

        self.assertEqual(summary["pipeline_status"], "failed")
        self.assertEqual(summary["error_message"], "silver_to_gold failed")

    def test_write_summary_writes_expected_partitioned_json_path(self):
        output_dir = ROOT / "tests" / "tmp_runtime" / "observability" / uuid4().hex
        try:
            summary = self.generator.generate_summary(
                run_id="daily_20260514_190001",
                run_date="2026-05-14",
                pipeline_status="success",
                validation_status="pass",
                gcs_sync_status="success",
                start_time="2026-05-14T19:00:00+07:00",
                end_time="2026-05-14T19:01:00+07:00",
                duration_seconds=60,
            )

            path = self.generator.write_summary(summary, output_dir=output_dir)

            self.assertEqual(path.name, "daily_run_summary.json")
            self.assertEqual(path.parent.name, "run_date=2026-05-14")
            self.assertTrue(path.exists())
            self.assertEqual(json.loads(path.read_text(encoding="utf-8")), summary)
        finally:
            shutil.rmtree(output_dir, ignore_errors=True)

    @settings(max_examples=100)
    @given(
        run_id=st.text(min_size=1, max_size=40),
        run_date=st.dates().map(str),
        pipeline_status=st.sampled_from(["success", "failed", "running"]),
        validation_status=st.sampled_from(["pass", "failed", "skipped"]),
        gcs_sync_status=st.sampled_from(["success", "failed", "skipped"]),
        start_time=st.text(min_size=1, max_size=40),
        end_time=st.text(min_size=1, max_size=40),
        duration_seconds=st.integers(min_value=0, max_value=86400),
        total_silver_records=st.integers(min_value=0, max_value=1_000_000),
        total_current_listings=st.integers(min_value=0, max_value=1_000_000),
        duplicate_record_count=st.integers(min_value=0, max_value=1_000_000),
        duplicate_rate=st.floats(min_value=0, max_value=1, allow_nan=False, allow_infinity=False),
        parse_success_rate=st.floats(min_value=0, max_value=1, allow_nan=False, allow_infinity=False),
        missing_price_rate=st.floats(min_value=0, max_value=1, allow_nan=False, allow_infinity=False),
        missing_area_rate=st.floats(min_value=0, max_value=1, allow_nan=False, allow_infinity=False),
        missing_location_rate=st.floats(min_value=0, max_value=1, allow_nan=False, allow_infinity=False),
    )
    def test_property_daily_run_summary_completeness(
        self,
        run_id,
        run_date,
        pipeline_status,
        validation_status,
        gcs_sync_status,
        start_time,
        end_time,
        duration_seconds,
        total_silver_records,
        total_current_listings,
        duplicate_record_count,
        duplicate_rate,
        parse_success_rate,
        missing_price_rate,
        missing_area_rate,
        missing_location_rate,
    ):
        summary = self.generator.generate_summary(
            run_id=run_id,
            run_date=run_date,
            pipeline_status=pipeline_status,
            validation_status=validation_status,
            gcs_sync_status=gcs_sync_status,
            start_time=start_time,
            end_time=end_time,
            duration_seconds=duration_seconds,
            gold_summary={
                "total_silver_records": total_silver_records,
                "total_current_listings": total_current_listings,
                "duplicate_record_count": duplicate_record_count,
                "duplicate_rate": duplicate_rate,
                "parse_success_rate": parse_success_rate,
                "missing_price_rate": missing_price_rate,
                "missing_area_rate": missing_area_rate,
                "missing_location_rate": missing_location_rate,
                "snapshot_dates": [run_date],
            },
        )

        for field in REQUIRED_SUMMARY_FIELDS:
            self.assertIn(field, summary)
        self.assertIsInstance(summary["run_id"], str)
        self.assertIsInstance(summary["run_date"], str)
        self.assertIsInstance(summary["pipeline_status"], str)
        self.assertIsInstance(summary["validation_status"], str)
        self.assertIsInstance(summary["gcs_sync_status"], str)
        self.assertIsInstance(summary["total_silver_records"], int)
        self.assertIsInstance(summary["total_current_listings"], int)
        self.assertIsInstance(summary["duplicate_rate"], float)
        self.assertIsInstance(summary["parse_success_rate"], float)
        self.assertIsInstance(summary["missing_price_rate"], float)
        self.assertIsInstance(summary["snapshot_dates"], list)
        self.assertIsInstance(summary["start_time"], str)
        self.assertIsInstance(summary["end_time"], str)
        self.assertIsInstance(summary["duration_seconds"], int)


if __name__ == "__main__":
    unittest.main()
