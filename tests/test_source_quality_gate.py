import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from validation.source_quality_gate import evaluate_source_quality_gate


class SourceQualityGateTest(unittest.TestCase):
    def setUp(self):
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

    def test_gate_passes_good_nhatot_smoke_metrics(self):
        decision = evaluate_source_quality_gate(
            {
                "total_records": 1,
                "parse_success_rate": 1.0,
                "blocked_rate": 0.0,
                "missing_price_rate": 0.0,
                "missing_area_rate": 0.0,
                "missing_location_rate": 0.0,
                "duplicate_rate": 0.0,
                "quarantine_rate": 0.0,
            },
            self.quality_config,
        )

        self.assertTrue(decision.passed)
        self.assertEqual(decision.status, "pass")
        self.assertEqual(decision.failures, [])

    def test_gate_fails_when_records_below_minimum(self):
        decision = evaluate_source_quality_gate(
            {
                "total_records": 0,
                "parse_success_rate": 1.0,
                "blocked_rate": 0.0,
            },
            self.quality_config,
        )

        self.assertEqual(decision.status, "fail")
        self.assertIn("total_records 0 below minimum 1", decision.failures)

    def test_gate_fails_when_parse_success_rate_is_low(self):
        decision = evaluate_source_quality_gate(
            {
                "total_records": 1,
                "parse_success_rate": 0.5,
                "blocked_rate": 0.0,
            },
            self.quality_config,
        )

        self.assertEqual(decision.status, "fail")
        self.assertTrue(any("parse_success_rate" in failure for failure in decision.failures))

    def test_gate_fails_when_blocked_rate_is_too_high(self):
        decision = evaluate_source_quality_gate(
            {
                "total_records": 1,
                "parse_success_rate": 1.0,
                "blocked_rate": 0.75,
            },
            self.quality_config,
        )

        self.assertEqual(decision.status, "fail")
        self.assertTrue(any("blocked_rate" in failure for failure in decision.failures))

    def test_gate_fails_when_missing_or_duplicate_rates_exceed_thresholds(self):
        decision = evaluate_source_quality_gate(
            {
                "total_records": 2,
                "parse_success_rate": 1.0,
                "blocked_rate": 0.0,
                "missing_price_rate": 0.75,
                "missing_area_rate": 0.0,
                "missing_location_rate": 0.0,
                "duplicate_rate": 0.75,
                "quarantine_rate": 0.75,
            },
            self.quality_config,
        )

        self.assertEqual(decision.status, "fail")
        self.assertTrue(any("missing_price_rate" in failure for failure in decision.failures))
        self.assertTrue(any("duplicate_rate" in failure for failure in decision.failures))
        self.assertTrue(any("quarantine_rate" in failure for failure in decision.failures))


if __name__ == "__main__":
    unittest.main()
