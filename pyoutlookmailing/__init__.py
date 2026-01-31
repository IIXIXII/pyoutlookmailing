#!/usr/bin/env python
# -*- coding: utf-8 -*-
# =============================================================================
#                    Author: Florent TOURNOIS | License: MIT                   
# =============================================================================

# -----------------------------------------------------------------------------
# pyoutlookmailing package init
# Keep this module lightweight: avoid importing heavy dependencies at import time.
# -----------------------------------------------------------------------------
from __future__ import annotations

# ---------------------------------------------------------------------------
# Package metadata (lightweight, no side effects)
# ---------------------------------------------------------------------------
from .version import __version_info__, __release_date__
from ._about import (
    __title__,
    __description__,
    __author__,
    __author_email__,
    __license__,
    __copyright__,
    __maintainer__,
    __status__,
    __url__,
)

__module_name__ = __title__
__package_name__ = __title__

# Standard convention: expose version as a string "X.Y.Z"
__version__ = ".".join(str(c) for c in __version_info__)

# ---------------------------------------------------------------------------
# Public API (lazy-loaded)
# ---------------------------------------------------------------------------
__all__ = [
    "load_conf",
    "default_conf",
    "compute_conf",
    "send_email",
    "html_img",
    "__version__",
    "__release_date__",
]


def __getattr__(name: str):
    """
    Lazy export of public symbols.

    This avoids importing core/renderer at package import time, which improves:
    - packaging/build behavior (PEP 517/660)
    - import performance
    - resilience when optional dependencies are missing
    """
    if name in {"load_conf", "default_conf", "compute_conf", "send_email"}:
        from . import core as _core
        return getattr(_core, name)

    if name == "html_img":
        from .renderer import html_img as _html_img
        return _html_img

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
