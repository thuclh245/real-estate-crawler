import json
import shutil
import sys
import unittest
from pathlib import Path
from uuid import uuid4

from hypothesis import given, settings, strategies as st


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from observability import DataQualityReport, QUALITY_METRIC_KEYS


RATE_KEYS = (
    "parse_success_rate",
    "duplicate_rate",
    "missing_price_rate",
    "missing_area_rate",
    "missing_location_rate",
)
COUNT_KEYS = ("total_records", "total_current_listings")


def metric_strategy():
    return st.fixed_dictionaries(
        {
            **{
                key: st.floats(
                    min_value=0,
                    max_value=1,
                    allow_nan=False,
                    allow_infinity=False,
                )
                for key in RATE_KEYS
            },
            **{
                key: st.integers(min_value=0, max_value=1_000_000)
                for key in COUNT_KEYS
            },
        }
    )


def expected_baseline_quality(parse_success, current, baseline, tolerances):
    excellent_parse_floor = max(
        0.95,
        baseline["parse_success_rate"] - tolerances["excellent_parse_success_drop"],
    )
    good_parse_floor = max(
        0.90,
        baseline["parse_success_rate"] - tolerances["good_parse_success_drop"],
    )

    excellent_rates_ok = all(
        current[key] <= baseline[key] + tolerances["excellent_rate_increase"]
        for key in (
            "duplicate_rate",
            "missing_price_rate",
            "missing_area_rate",
            "missing_location_rate",
        )
    )
    good_rates_ok = all(
        current[key] <= baseline[key] + tolerances["good_rate_increase"]
        for key in (
            "duplicate_rate",
            "missing_price_rate",
            "missing_area_rate",
            "missing_location_rate",
        )
    )

    if parse_success >= excellent_parse_floor and excellent_rates_ok:
        return "excellent"
    if parse_success >= good_parse_floor and good_rates_ok:
        return "good"
    return "needs_attention"


def format_report_value(value):
    value = float(value)
    if value.is_integer():
        return str(int(value))
    return f"{value:.6g}"


class DataQualityReportTest(unittest.TestCase):
    def setUp(self):
        self.report = DataQualityReport()

    def test_classify_quality_uses_static_guardrails_without_baseline(self):
        self.assertEqual(self.report.classify_quality(0.98, 0.05), "excellent")
        self.assertEqual(self.report.classify_quality(0.92, 0.30), "good")
        self.assertEqual(self.report.classify_quality(0.89, 0.01), "needs_attention")

    def test_classify_quality_accepts_small_drop_from_rolling_baseline(self):
        quality = self.report.classify_quality(
            parse_success_rate=0.97,
            duplicate_rate=0.08,
            baseline_metrics={
                "parse_success_rate": 0.985,
                "duplicate_rate": 0.04,
                "missing_price_rate": 0.02,
            },
            current_metrics={
                "missing_price_rate": 0.03,
            },
        )

        self.assertEqual(quality, "excellent")

    def test_classify_quality_flags_large_regression_from_baseline(self):
        quality = self.report.classify_quality(
            parse_success_rate=0.94,
            duplicate_rate=0.17,
            baseline_metrics={
                "parse_success_rate": 0.99,
                "duplicate_rate": 0.04,
                "missing_price_rate": 0.02,
            },
            current_metrics={
                "missing_price_rate": 0.18,
            },
        )

        self.assertEqual(quality, "needs_attention")

    def test_write_reports_creates_markdown_and_json(self):
        output_dir = ROOT / "tests" / "tmp_runtime" / "quality_report" / uuid4().hex
        metrics = {
            "parse_success_rate": 1.0,
            "duplicate_rate": 0.1,
            "missing_price_rate": 0.0,
            "missing_area_rate": 0.0,
            "missing_location_rate": 0.0,
            "total_records": 100,
            "total_current_listings": 80,
        }
        try:
            paths = self.report.write_reports(
                "2026-05-14",
                output_dir,
                include_json=True,
                metrics=metrics,
                quality_level="good",
            )

            self.assertEqual(len(paths), 2)
            self.assertTrue((output_dir / "data_quality_report_2026-05-14.md").exists())
            json_path = output_dir / "data_quality_report_2026-05-14.json"
            self.assertTrue(json_path.exists())
            self.assertEqual(
                json.loads(json_path.read_text(encoding="utf-8"))["metrics"],
                metrics,
            )
        finally:
            shutil.rmtree(output_dir, ignore_errors=True)

    @settings(max_examples=100)
    @given(
        parse_success=st.floats(min_value=0, max_value=1, allow_nan=False, allow_infinity=False),
        duplicate=st.floats(min_value=0, max_value=1, allow_nan=False, allow_infinity=False),
    )
    def test_property_static_classification_rules(self, parse_success, duplicate):
        actual = self.report.classify_quality(parse_success, duplicate)
        if parse_success >= 0.95 and duplicate < 0.1:
            expected = "excellent"
        elif parse_success >= 0.9:
            expected = "good"
        else:
            expected = "needs_attention"

        self.assertEqual(actual, expected)

    @settings(max_examples=100)
    @given(
        current=metric_strategy(),
        baseline=metric_strategy(),
        tolerances=st.fixed_dictionaries(
            {
                "excellent_parse_success_drop": st.floats(
                    min_value=0,
                    max_value=0.2,
                    allow_nan=False,
                    allow_infinity=False,
                ),
                "good_parse_success_drop": st.floats(
                    min_value=0,
                    max_value=0.2,
                    allow_nan=False,
                    allow_infinity=False,
                ),
                "excellent_rate_increase": st.floats(
                    min_value=0,
                    max_value=0.2,
                    allow_nan=False,
                    allow_infinity=False,
                ),
                "good_rate_increase": st.floats(
                    min_value=0,
                    max_value=0.2,
                    allow_nan=False,
                    allow_infinity=False,
                ),
            }
        ),
    )
    def test_property_baseline_classification_rules(self, current, baseline, tolerances):
        if tolerances["good_parse_success_drop"] < tolerances["excellent_parse_success_drop"]:
            tolerances["good_parse_success_drop"] = tolerances["excellent_parse_success_drop"]
        if tolerances["good_rate_increase"] < tolerances["excellent_rate_increase"]:
            tolerances["good_rate_increase"] = tolerances["excellent_rate_increase"]

        actual = self.report.classify_quality(
            current["parse_success_rate"],
            current["duplicate_rate"],
            baseline_metrics=baseline,
            tolerances=tolerances,
            current_metrics=current,
        )
        expected = expected_baseline_quality(
            current["parse_success_rate"],
            current,
            baseline,
            tolerances,
        )

        self.assertEqual(actual, expected)

    @settings(max_examples=100)
    @given(
        current=metric_strategy(),
        history=st.lists(metric_strategy(), min_size=1, max_size=10),
        window_days=st.integers(min_value=1, max_value=7),
    )
    def test_property_comparison_correctness(self, current, history, window_days):
        comparison = self.report.compute_comparison(
            current,
            history,
            window_days=window_days,
        )

        baseline_source = history[-window_days:]
        self.assertIsNotNone(comparison)
        self.assertEqual(comparison["history_count"], len(baseline_source))
        for key in QUALITY_METRIC_KEYS:
            expected_avg = sum(float(row[key]) for row in baseline_source) / len(baseline_source)
            expected_delta = float(current[key]) - expected_avg
            self.assertAlmostEqual(comparison["baseline_metrics"][key], expected_avg)
            self.assertAlmostEqual(comparison["deltas"][f"{key}_delta"], expected_delta)
            if key in COUNT_KEYS and expected_avg != 0:
                self.assertAlmostEqual(
                    comparison["percent_deltas"][f"{key}_pct_delta"],
                    expected_delta / expected_avg,
                )

    @settings(max_examples=100)
    @given(metrics=metric_strategy())
    def test_property_report_metric_completeness(self, metrics):
        markdown = self.report.generate_markdown_report(
            metrics,
            comparison=None,
            quality_level="good",
            run_date="2026-05-14",
        )
        json_report = self.report.generate_json_report(
            metrics,
            comparison=None,
            quality_level="good",
            run_date="2026-05-14",
        )

        for key in QUALITY_METRIC_KEYS:
            self.assertIn(key, markdown)
            self.assertIn(key, json_report["metrics"])

    @settings(max_examples=100)
    @given(metrics=metric_strategy(), history=st.lists(metric_strategy(), min_size=1, max_size=7))
    def test_property_report_format_equivalence(self, metrics, history):
        comparison = self.report.compute_comparison(metrics, history)
        json_report = self.report.generate_json_report(
            metrics,
            comparison=comparison,
            quality_level="good",
            run_date="2026-05-14",
        )
        markdown = self.report.generate_markdown_report(
            metrics,
            comparison=comparison,
            quality_level="good",
            run_date="2026-05-14",
        )

        for key, value in json_report["metrics"].items():
            self.assertIn(key, markdown)
            self.assertIn(format_report_value(value), markdown)


if __name__ == "__main__":
    unittest.main()
