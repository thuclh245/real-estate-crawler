import sys
import unittest
from copy import deepcopy
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from validation.source_promotion_gate import evaluate_source_promotion_gate


class SourcePromotionGateTest(unittest.TestCase):
    def setUp(self):
        self.nhatot_config = yaml.safe_load(
            (ROOT / "configs" / "sources" / "nhatot.yaml").read_text(encoding="utf-8")
        )
        self.passing_scorecard = {
            "source_code": "nhatot",
            "crawl_date": "2026-05-26",
            "crawl_id": "nhatot_20260526_010000",
            "total_records": 800,
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

    def test_current_nhatot_config_allows_silver_ingestion_but_blocks_promotion(self):
        decision = evaluate_source_promotion_gate(
            source_config=self.nhatot_config,
            scorecard=self.passing_scorecard,
            warehouse_summary=self.warehouse_summary,
        )

        self.assertFalse(decision.passed)
        self.assertEqual(decision.status, "blocked")
        self.assertIn(
            "legal_access_review.personal_contact_handling_documented is not true",
            decision.block_reasons,
        )

    def test_gate_passes_when_source_has_all_required_promotion_evidence(self):
        config = deepcopy(self.nhatot_config)
        config["promotion"]["legal_access_review"] = {
            "terms_reviewed": True,
            "robots_checked": True,
            "prohibited_login_required": False,
            "personal_contact_handling_documented": True,
            "approved_fetch_mode_documented": True,
            "no_captcha_bypass_required": True,
        }

        decision = evaluate_source_promotion_gate(
            source_config=config,
            scorecard=self.passing_scorecard,
            warehouse_summary=self.warehouse_summary,
        )

        self.assertTrue(decision.passed)
        self.assertEqual(decision.status, "pass")
        self.assertEqual(decision.block_reasons, [])

    def test_gate_blocks_when_scorecard_or_warehouse_evidence_is_missing(self):
        decision = evaluate_source_promotion_gate(
            source_config={
                **self.nhatot_config,
                "is_active": True,
                "compatibility": {"production_enabled": True},
                "promotion": {
                    "legal_access_review": {
                        "terms_reviewed": True,
                        "robots_checked": True,
                        "prohibited_login_required": False,
                        "personal_contact_handling_documented": True,
                        "approved_fetch_mode_documented": True,
                        "no_captcha_bypass_required": True,
                    }
                },
            },
            scorecard={**self.passing_scorecard, "gate_status": "fail"},
            warehouse_summary={
                "source_codes": ["unknown"],
                "table_row_counts": {
                    "fact_listing_snapshot": 0,
                    "fact_data_quality_daily": 0,
                },
            },
        )

        self.assertEqual(decision.status, "blocked")
        self.assertIn("source scorecard gate_status is not pass", decision.block_reasons)
        self.assertIn(
            "warehouse summary does not include source_code",
            decision.block_reasons,
        )
        self.assertIn(
            "warehouse fact_listing_snapshot has no rows",
            decision.block_reasons,
        )


if __name__ == "__main__":
    unittest.main()
