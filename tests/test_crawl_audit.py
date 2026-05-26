import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from crawler.crawl_audit import validate_seed_url


class CrawlAuditTest(unittest.TestCase):
    def test_validate_seed_url_accepts_matching_web_location_path(self):
        self.assertTrue(
            validate_seed_url(
                "https://www.nhatot.com/mua-ban-nha-dat-quan-ba-dinh-ha-noi",
                "https://www.nhatot.com/mua-ban-nha-dat-quan-ba-dinh-ha-noi",
                "quan-ba-dinh-ha-noi",
            )
        )

    def test_validate_seed_url_rejects_wrong_web_location_path(self):
        self.assertFalse(
            validate_seed_url(
                "https://www.nhatot.com/mua-ban-nha-dat-quan-ba-dinh-ha-noi",
                "https://www.nhatot.com/mua-ban-nha-dat-quan-dong-da-ha-noi",
                "quan-ba-dinh-ha-noi",
            )
        )

    def test_validate_seed_url_accepts_nhatot_gateway_api_seed(self):
        url = (
            "https://gateway.chotot.com/v1/public/ad-listing"
            "?cg=1010&region=12&area=74&page=1&limit=20&st=s"
        )

        self.assertTrue(validate_seed_url(url, url, "quan-ba-dinh-ha-noi"))


if __name__ == "__main__":
    unittest.main()
