import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from crawler.block_detector import (
    classify_failure_status,
    increment_http_counters,
    is_blocked_page,
)


class BlockDetectorTest(unittest.TestCase):
    def test_blocked_on_http_status(self):
        self.assertTrue(is_blocked_page(403, ""))
        self.assertTrue(is_blocked_page(429, ""))

    def test_blocked_on_cloudflare_signals(self):
        html = "<title>Just a moment</title>"
        self.assertTrue(is_blocked_page(200, html))

    def test_not_blocked_if_listing_urls_found(self):
        html = "<title>Just a moment</title>"
        self.assertFalse(is_blocked_page(200, html, listing_urls_found=3))

    def test_not_blocked_without_signals(self):
        html = "<html><body>ok</body></html>"
        self.assertFalse(is_blocked_page(200, html))

    def test_increment_http_counters(self):
        summary = {"http_403_count": 0, "http_429_count": 0}
        increment_http_counters(summary, 403)
        increment_http_counters(summary, 429)
        self.assertEqual(summary["http_403_count"], 1)
        self.assertEqual(summary["http_429_count"], 1)

    def test_classify_failure_status(self):
        self.assertEqual(classify_failure_status(403), "blocked")
        self.assertEqual(classify_failure_status(429), "blocked")
        self.assertEqual(classify_failure_status(500), "failed_http")
        self.assertEqual(
            classify_failure_status(None, "request timed out"),
            "failed_timeout",
        )
        self.assertEqual(classify_failure_status(None, "unknown"), "failed_fetch")


if __name__ == "__main__":
    unittest.main()
