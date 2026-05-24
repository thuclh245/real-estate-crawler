from __future__ import annotations

import warnings

warnings.warn(
    "crawler.parsing.quality_checks is deprecated; use parsing.quality.quality_checks",
    DeprecationWarning,
    stacklevel=2,
)

from parsing.quality.quality_checks import *  # noqa: F401,F403
