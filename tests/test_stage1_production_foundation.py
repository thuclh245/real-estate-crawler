import json
import shutil
import sys
import unittest
from pathlib import Path
from uuid import uuid4


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from common.quarantine import append_quarantine_record, build_quarantine_record
from observability import ProductionRunSummary
from validation.preflight import EXIT_HARD_FAILURE, EXIT_PASS, run_preflight
from validation.publish_gate import evaluate_publish_gate


class Stage1ProductionFoundationTest(unittest.TestCase):
    def setUp(self):
        self.base_dir = ROOT / "tests" / "tmp_runtime" / "stage1" / uuid4().hex

    def tearDown(self):
        shutil.rmtree(self.base_dir, ignore_errors=True)

    def test_production_summary_writes_latest_pointer_for_published_run(self):
        generator = ProductionRunSummary()
        summary = generator.generate_summary(
            run_id="20260522T003000_batdongsan_full",
            run_date="2026-05-22",
            pipeline_status="success",
            validation_status="pass",
            start_time="2026-05-22T00:30:00+07:00",
            end_time="2026-05-22T00:40:00+07:00",
            duration_seconds=600,
            source_names=["batdongsan"],
            gold_summary={
                "total_silver_records": 100,
                "total_current_listings": 80,
                "snapshot_dates": ["2026-05-22"],
            },
        )

        path = generator.write_summary(summary, self.base_dir / "pipeline_runs")
        pointer_path = self.base_dir / "pipeline_runs" / "latest_production.json"

        self.assertEqual(summary["publish_status"], "published")
        self.assertTrue(path.exists())
        self.assertTrue(pointer_path.exists())
        pointer = json.loads(pointer_path.read_text(encoding="utf-8"))
        self.assertEqual(pointer["run_id"], summary["run_id"])
        self.assertEqual(json.loads(path.read_text(encoding="utf-8")), summary)

    def test_production_summary_blocks_zero_record_full_run(self):
        summary = ProductionRunSummary().generate_summary(
            run_id="20260522T003000_batdongsan_full",
            run_date="2026-05-22",
            pipeline_status="success",
            validation_status="pass",
            start_time="2026-05-22T00:30:00+07:00",
            end_time="2026-05-22T00:31:00+07:00",
            duration_seconds=60,
            gold_summary={"total_silver_records": 0},
        )

        self.assertEqual(summary["publish_status"], "blocked")
        self.assertIn("zero silver records", summary["publish_block_reason"])

    def test_publish_gate_reports_validated_warnings(self):
        decision = evaluate_publish_gate(
            pipeline_mode="full",
            run_class="production",
            pipeline_status="success",
            validation_status="pass",
            silver_records_written=12,
            warnings=["duplicate_rate above warning threshold"],
        )

        self.assertEqual(decision.status, "validated_with_warnings")
        self.assertIn("duplicate_rate", decision.block_reason)

    def test_preflight_writes_result_and_fails_missing_config(self):
        config_path = self.base_dir / "missing.yaml"
        exit_code, payload, output_path = run_preflight(
            run_id="preflight_missing_config",
            config_paths=[str(config_path)],
            output_dir=self.base_dir / "preflight",
        )

        self.assertEqual(exit_code, EXIT_HARD_FAILURE)
        self.assertEqual(payload["overall"], "failed")
        self.assertTrue(output_path.exists())

    def test_preflight_passes_existing_config_without_spark(self):
        exit_code, payload, _ = run_preflight(
            run_id="preflight_existing_config",
            config_paths=["configs/crawl_targets.yaml"],
            output_dir=self.base_dir / "preflight",
        )

        self.assertEqual(exit_code, EXIT_PASS)
        self.assertEqual(payload["overall"], "pass")

    def test_quarantine_base_appends_jsonl_record(self):
        record = build_quarantine_record(
            run_id="run-1",
            source_code="batdongsan",
            rejection_stage="silver_parse_errors",
            rejection_reason="parse_exception",
            record_identity="listing-1",
            error_message="invalid field",
        )

        path = append_quarantine_record(
            record,
            run_date="2026-05-22",
            base_dir=self.base_dir / "quarantine",
        )

        self.assertTrue(path.exists())
        payload = json.loads(path.read_text(encoding="utf-8").splitlines()[0])
        self.assertEqual(payload["record_identity"], "listing-1")
        self.assertEqual(payload["rejection_stage"], "silver_parse_errors")


if __name__ == "__main__":
    unittest.main()
