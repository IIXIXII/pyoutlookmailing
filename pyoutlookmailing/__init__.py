#!/usr/bin/env python
# -*- coding: utf-8 -*-
# =============================================================================
# Author: Florent TOURNOIS | License: MIT
# =============================================================================

# -----------------------------------------------------------------------------
# pyoutlookmailing package init
# Keep this module lightweight: avoid importing heavy dependencies at import
# time.
# -----------------------------------------------------------------------------
"""Package metadata and lazily loaded email preparation helpers."""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING

from ._about import (
    __author__,
    __author_email__,
    __copyright__,
    __description__,
    __license__,
    __maintainer__,
    __status__,
    __title__,
    __url__,
)

# -----------------------------------------------------------------------------
# Package metadata (lightweight, no side effects)
# -----------------------------------------------------------------------------
from .version import __release_date__, __version_info__

__module_name__ = __title__
__package_name__ = __title__

# Standard convention: expose version as a string "X.Y.Z"
__version__ = ".".join(str(c) for c in __version_info__)

# -----------------------------------------------------------------------------
# Public API (lazy-loaded)
# -----------------------------------------------------------------------------
if TYPE_CHECKING:
    from .core import compute_conf, default_conf, load_conf, send_email
    from .renderer import html_img

__all__ = [
    "load_conf",
    "default_conf",
    "compute_conf",
    "send_email",
    "html_img",
    "__version__",
    "__release_date__",
]


# -----------------------------------------------------------------------------
def __getattr__(name: str):
    """Lazy export of public symbols.

    This avoids importing core/renderer at package import time, which improves:
    - packaging/build behavior (PEP 517/660)
    - import performance
    - resilience when optional dependencies are missing
    """
    if name in {"load_conf", "default_conf", "compute_conf", "send_email"}:
        return getattr(import_module(".core", __name__), name)

    if name == "html_img":
        return import_module(".renderer", __name__).html_img

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
