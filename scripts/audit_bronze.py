"""Compatibility shim for the Bronze audit tool.

Use scripts/tools/audit_bronze.py for the canonical entrypoint.
"""

from __future__ import annotations

import runpy
from pathlib import Path


def main() -> None:
    target = Path(__file__).resolve().parent / "tools" / "audit_bronze.py"
    runpy.run_path(target, run_name="__main__")


if __name__ == "__main__":
    main()
