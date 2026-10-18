#!/usr/bin/env python
# -*- coding: utf-8 -*-
# =============================================================================
# Author: Florent TOURNOIS | License: MIT
# =============================================================================

"""Tests must never reach a real Outlook session."""

import sys
from types import ModuleType

import pytest


# -----------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def isolate_user_preferences(tmp_path, monkeypatch):
    """Keep tests and subprocesses independent of personal preferences."""
    monkeypatch.setenv(
        "PYOUTLOOKMAILING_PREFERENCES", str(tmp_path / "preferences.yaml")
    )


# -----------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def block_outlook(monkeypatch):
    # --------------------------------------------------------------------------
    def forbidden(*args, **kwargs):
        raise AssertionError("Real Outlook COM access is forbidden in tests")

    client = ModuleType("win32com.client")
    monkeypatch.setattr(client, "Dispatch", forbidden, raising=False)
    win32com = ModuleType("win32com")
    monkeypatch.setattr(win32com, "client", client, raising=False)
    monkeypatch.setitem(sys.modules, "win32com", win32com)
    monkeypatch.setitem(sys.modules, "win32com.client", client)
