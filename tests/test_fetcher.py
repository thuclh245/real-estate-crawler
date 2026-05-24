import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from crawler.fetcher import is_retryable_http_status, retry_sleep_seconds


class FetcherTest(unittest.TestCase):
    def test_antibot_http_statuses_are_retryable(self):
        for status in [0, 403, 408, 425, 429, 500, 502, 503, 504]:
            self.assertTrue(is_retryable_http_status(status), status)

    def test_non_retryable_http_statuses(self):
        for status in [200, 301, 302, 400, 404]:
            self.assertFalse(is_retryable_http_status(status), status)

    def test_retry_sleep_backoff_is_non_negative(self):
        self.assertEqual(retry_sleep_seconds(0, 0), 0)
        self.assertGreaterEqual(retry_sleep_seconds(10, 1), 20)


if __name__ == "__main__":
    unittest.main()
