from __future__ import annotations

import warnings

warnings.warn(
    "crawler.parsing.normalizers is deprecated; use parsing.normalizers",
    DeprecationWarning,
    stacklevel=2,
)

from parsing.normalizers import *  # noqa: F401,F403
