import sys
import unittest
from pathlib import Path
from uuid import uuid4


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from crawler.orchestrator import CrawlOrchestrator, CrawlDependencies


LIST_PAGE_HTML = """
<html>
  <body>
    <div class="js__card-listing">
      <a href="/ban-nha/pr123456">Listing</a>
      <div class="js__card-title">Nha pho</div>
      <div class="re__card-config-price">10 ty</div>
      <div class="re__card-config-area">100 m2</div>
      <div class="re__card-location">Quan 1</div>
      <div class="js__card-description">Mo ta ngan</div>
    </div>
  </body>
</html>
"""

DETAIL_PAGE_HTML = """
<html>
  <body>
    <h1 class="re__pr-title">Tieu de bai dang</h1>
    <div class="re__address-line-1">123 Pho Hue</div>
    <div class="re__breadcrumb">Ha Noi / Quan 1</div>
    <div class="re__section-body">Mo ta chi tiet</div>
  </body>
</html>
"""


def fake_fetch_with_retry(url: str, mode: str, max_retries: int, retry_delay_seconds: float):
    if "pr123456" in url:
        return 200, DETAIL_PAGE_HTML, url, 0, None
    return 200, LIST_PAGE_HTML, url, 0, None


class CrawlFlowTest(unittest.TestCase):
    def setUp(self):
        self.base_dir = ROOT / "tests" / "tmp_runtime" / "crawl_flow" / uuid4().hex

    def tearDown(self):
        if self.base_dir.exists():
            for path in sorted(self.base_dir.rglob("*"), reverse=True):
                if path.is_file():
                    path.unlink()
                else:
                    path.rmdir()

    def test_crawl_flow_writes_bronze_files(self):
        config = {
            "source": "batdongsan",
            "base_url": "https://batdongsan.com.vn",
            "crawl_settings": {
                "max_pages_per_target": 1,
                "max_listings_per_target": 1,
                "request_delay_seconds": 0,
                "fetch_mode": "requests",
                "max_retries": 0,
                "retry_delay_seconds": 0,
            },
            "categories": [
                {"slug": "ban-nha-rieng", "label": "Ban nha"}
            ],
            "locations": [
                {
                    "district": "quan-1",
                    "location_path": "quan-1",
                    "district_label": "Quan 1",
                    "city": "ha-noi",
                    "city_label": "Ha Noi",
                    "city_slug": "ha-noi",
                }
            ],
        }

        dependencies = CrawlDependencies(fetch_with_retry_fn=fake_fetch_with_retry)
        orchestrator = CrawlOrchestrator(
            config,
            base_dir=self.base_dir,
            dependencies=dependencies,
        )
        summary = orchestrator.run()

        self.assertEqual(summary["success_count"], 1)

        metadata_files = list(self.base_dir.rglob("metadata/*.json"))
        self.assertEqual(len(metadata_files), 1)
        raw_html_files = list(self.base_dir.rglob("raw_html/*.html"))
        self.assertEqual(len(raw_html_files), 1)


if __name__ == "__main__":
    unittest.main()
