import re
import sys
import unittest
from pathlib import Path
from uuid import uuid4

from hypothesis import given, settings, strategies as st


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from observability import ensure_screenshot_dir, generate_screenshot_filename


class ScreenshotUtilsTest(unittest.TestCase):
    def test_ensure_screenshot_dir_creates_directory(self):
        path = ROOT / "tests" / "tmp_runtime" / "screenshots" / uuid4().hex
        result = ensure_screenshot_dir(path)

        self.assertEqual(result, path)
        self.assertTrue(path.exists())
        self.assertTrue(path.is_dir())

    @settings(max_examples=100)
    @given(
        tab_name=st.text(min_size=0, max_size=80),
        date_str=st.dates().map(str),
    )
    def test_property_screenshot_filename_format(self, tab_name, date_str):
        filename = generate_screenshot_filename(tab_name, date_str)

        self.assertRegex(filename, r"^[a-z0-9_]+_\d{4}-\d{2}-\d{2}\.png$")
        normalized_tab = filename[: -len(f"_{date_str}.png")]
        self.assertTrue(normalized_tab)
        self.assertIsNotNone(re.fullmatch(r"[a-z0-9_]+", normalized_tab))


if __name__ == "__main__":
    unittest.main()
