"""Compatibility shim for the Bronze location audit backfill tool.

Use scripts/tools/backfill_crawl_location_audit.py for the canonical entrypoint.
"""

from __future__ import annotations

import runpy
from pathlib import Path


def main() -> None:
    target = (
        Path(__file__).resolve().parent / "tools" / "backfill_crawl_location_audit.py"
    )
    runpy.run_path(target, run_name="__main__")


if __name__ == "__main__":
    main()
