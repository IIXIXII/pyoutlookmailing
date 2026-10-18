#!/usr/bin/env python
# -*- coding: utf-8 -*-
# =============================================================================
# Author: Florent TOURNOIS | License: MIT
# =============================================================================

"""Deterministic file lookup using the public pymdtools API."""

from pathlib import Path

from pymdtools.common import check_file


# -----------------------------------------------------------------------------
def find_file(filename, folders=(), subfolders=("",)) -> Path:
    """Find an existing file using ordered roots and immediate subfolders.

    Args:
        filename: String or path-like name; a leading home-directory marker
            expands.
        folders: Search roots, tried in the supplied order for a relative
            filename.
        subfolders: Relative subdirectories within each root; an empty string
            searches the root itself. Defaults to just the root.

    Returns:
        The resolved Path of the first match. Absolute filenames bypass the
        roots.

    Raises:
        FileNotFoundError: The absolute file or every relative candidate is
            missing.

    No recursive traversal or implicit working-directory search is performed.
    Pass Path.cwd() in folders when that fallback is wanted.
    """
    candidate = Path(filename).expanduser()
    if candidate.is_absolute():
        return check_file(candidate)
    for folder in folders:
        for subfolder in subfolders:
            resolved = Path(folder) / subfolder / candidate
            if resolved.is_file():
                return resolved.resolve()
    raise FileNotFoundError(f"Fichier introuvable : {filename}")
