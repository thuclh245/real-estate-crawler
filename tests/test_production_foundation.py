import json
import shutil
import sys
import unittest
from pathlib import Path
from uuid import uuid4

import yaml


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from common.quarantine import append_quarantine_record, build_quarantine_record
from observability import ProductionRunSummary
from validation.preflight import EXIT_HARD_FAILURE, EXIT_PASS, run_preflight
from validation.publish_gate import evaluate_publish_gate, load_publish_thresholds


class ProductionFoundationTest(unittest.TestCase):
    def setUp(self):
        self.base_dir = ROOT / "tests" / "tmp_runtime" / "production_foundation" / uuid4().hex

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
            silver_records_written=120,
            warnings=["duplicate_rate above warning threshold"],
        )

        self.assertEqual(decision.status, "validated_with_warnings")
        self.assertIn("duplicate_rate", decision.block_reason)

    def test_publish_gate_blocks_below_full_production_threshold(self):
        decision = evaluate_publish_gate(
            pipeline_mode="full",
            run_class="production",
            pipeline_status="success",
            validation_status="pass",
            silver_records_written=99,
        )

        self.assertEqual(decision.status, "blocked")
        self.assertIn("below minimum 100", decision.block_reason)

    def test_publish_thresholds_load_from_stage1_config(self):
        thresholds = load_publish_thresholds(
            pipeline_mode="full",
            run_class="production",
        )

        self.assertEqual(thresholds.min_silver_records, 100)

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

    def test_source_code_is_consistent_across_configs_and_pipeline_scripts(self):
        config_paths = [
            ROOT / "configs" / "crawl_targets.yaml",
            ROOT / "configs" / "crawl_targets_scale.yaml",
            ROOT / "configs" / "team" / "priority_a_ha_noi.yaml",
            ROOT / "configs" / "team" / "priority_a_ha_noi_expand_01.yaml",
        ]

        for config_path in config_paths:
            config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
            self.assertEqual(config["source"], "batdongsan", config_path)
            self.assertEqual(config["source_domain"], "batdongsan.com.vn", config_path)

        for script_path in [
            ROOT / "scripts" / "run_daily_pipeline.ps1",
            ROOT / "scripts" / "run_daily_pipeline.sh",
        ]:
            script_text = script_path.read_text(encoding="utf-8")
            self.assertIn("configs/team/batdongsan_house_150.yaml", script_text)
            self.assertIn("configs/sources/nhatot.yaml", script_text)
            self.assertNotIn("configs/sources/nhatot_house_150.yaml", script_text)
            self.assertIn("pipeline.sources_to_silver", script_text, script_path)
            self.assertIn("source_names=", script_text, script_path)
            self.assertNotIn("source=batdongsan/crawl_date", script_text, script_path)
            self.assertNotIn("source=batdongsan" + ".com.vn", script_text, script_path)

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
