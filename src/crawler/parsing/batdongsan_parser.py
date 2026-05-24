from __future__ import annotations

import warnings

warnings.warn(
    "crawler.parsing.batdongsan_parser is deprecated; use parsing.sources.batdongsan.silver_parser",
    DeprecationWarning,
    stacklevel=2,
)

from parsing.sources.batdongsan.silver_parser import *  # noqa: F401,F403
