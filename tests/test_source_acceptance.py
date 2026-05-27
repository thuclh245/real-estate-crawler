import json
import shutil
import sys
import unittest
from pathlib import Path
from uuid import uuid4

import yaml


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from observability import (
    SOURCE_ACCEPTANCE_SCHEMA_VERSION,
    build_source_acceptance_pack,
    write_source_acceptance_pack,
)
from validation.source_promotion_gate import evaluate_source_promotion_gate


class SourceAcceptanceTest(unittest.TestCase):
    def setUp(self):
        self.base_dir = ROOT / "tests" / "tmp_runtime" / "source_acceptance" / uuid4().hex
        self.source_config = yaml.safe_load(
            (ROOT / "configs" / "sources" / "nhatot.yaml").read_text(encoding="utf-8")
        )
        self.source_config["compatibility"]["production_scope"] = "silver_only"
        self.scorecard = {
            "source_code": "nhatot",
            "crawl_date": "2026-05-26",
            "crawl_id": "nhatot_20260526_010000",
            "total_records": 1,
            "parse_success_rate": 1.0,
            "blocked_rate": 0.0,
            "gate_status": "pass",
        }
        self.warehouse_summary = {
            "source_codes": ["unknown", "nhatot"],
            "table_row_counts": {
                "fact_listing_snapshot": 1,
                "fact_data_quality_daily": 1,
            },
        }

    def tearDown(self):
        shutil.rmtree(self.base_dir, ignore_errors=True)

    def test_acceptance_pack_marks_technical_ready_but_promotion_blocked(self):
        decision = evaluate_source_promotion_gate(
            source_config=self.source_config,
            scorecard=self.scorecard,
            warehouse_summary=self.warehouse_summary,
        )
        acceptance = build_source_acceptance_pack(
            source_code="nhatot",
            source_config=self.source_config,
            scorecard=self.scorecard,
            promotion_decision=decision,
            warehouse_summary=self.warehouse_summary,
            artifact_paths=["source_scorecard.json", "warehouse_summary.json"],
        )

        self.assertEqual(
            acceptance["acceptance_schema_version"],
            SOURCE_ACCEPTANCE_SCHEMA_VERSION,
        )
        self.assertEqual(acceptance["source_code"], "nhatot")
        self.assertEqual(acceptance["technical_readiness_status"], "pass")
        self.assertEqual(acceptance["promotion_status"], "blocked")
        self.assertEqual(acceptance["source_acceptance_status"], "blocked")
        self.assertTrue(acceptance["checklist"]["source_scorecard_passed"])
        self.assertTrue(acceptance["checklist"]["warehouse_source_present"])
        self.assertTrue(acceptance["checklist"]["production_scope_is_silver_only"])
        self.assertTrue(acceptance["promotion_block_reasons"])

    def test_acceptance_pack_can_be_written_as_json_artifact(self):
        decision = evaluate_source_promotion_gate(
            source_config=self.source_config,
            scorecard=self.scorecard,
            warehouse_summary=self.warehouse_summary,
        )
        acceptance = build_source_acceptance_pack(
            source_code="nhatot",
            source_config=self.source_config,
            scorecard=self.scorecard,
            promotion_decision=decision,
            warehouse_summary=self.warehouse_summary,
        )

        path = write_source_acceptance_pack(acceptance, self.base_dir)

        expected_path = (
            self.base_dir / "source_acceptance" / "source=nhatot" / "source_acceptance.json"
        )
        self.assertEqual(path, expected_path)
        self.assertTrue(path.exists())
        self.assertEqual(json.loads(path.read_text(encoding="utf-8")), acceptance)


if __name__ == "__main__":
    unittest.main()
