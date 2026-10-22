#!/usr/bin/env python
# -*- coding: utf-8 -*-
# =============================================================================
# Author: Florent TOURNOIS | License: MIT
# =============================================================================

"""Blacklist sources must accumulate and be checked before Outlook delivery."""

import logging
from copy import deepcopy
from unittest.mock import Mock

import pandas as pd
import pytest
import yaml

from pyoutlookmailing import core, outlook, preferences


# -----------------------------------------------------------------------------
def test_global_profile_include_main_and_local_blacklists_accumulate(
    tmp_path, monkeypatch
):
    store = preferences.get_preferences_store()
    common = tmp_path / "common"
    common.mkdir()
    mails = tmp_path / "mails"
    mails.mkdir()
    shared = tmp_path / "shared"
    shared.mkdir()
    sources = {
        "global": (tmp_path, "GlobalBlocked"),
        "profile": (tmp_path, "ProfileBlocked"),
        "included": (shared, "IncludedBlocked"),
        "main": (mails, "MainBlocked"),
        "local": (mails, "LocalBlocked"),
    }
    for name, (folder, column) in sources.items():
        pd.DataFrame({column: [f" {name.upper()}@example.org "]}).to_excel(
            folder / f"{name}.xlsx", index=False
        )
    store.save(
        {
            "not_to": {
                "list": ["manual-global@example.org"],
                "excel_file": "global.xlsx",
                "excel_column_name": "GlobalBlocked",
            },
            "profiles": {
                "test": {
                    "not_to": {
                        "list": ["manual-profile@example.org"],
                        "excel_file": "profile.xlsx",
                        "excel_column_name": "ProfileBlocked",
                    }
                }
            },
        }
    )
    (shared / "base.conf").write_text(
        yaml.safe_dump(
            {
                "not_to": {
                    "excel_file": "included.xlsx",
                    "excel_column_name": "IncludedBlocked",
                }
            }
        ),
        encoding="utf-8",
    )
    source = mails / "campaign.mailmd"
    source.write_text(
        '<!-- var(conf/profile) = "test" -->\n'
        '<!-- var(conf/paths/includes) = "../shared/base.conf" -->\n'
        '<!-- var(conf/not_to/excel_file) = "main.xlsx" -->\n'
        '<!-- var(conf/not_to/excel_column_name) = "MainBlocked" -->\n'
        '<!-- var(conf/to/list) = "allowed@example.org" -->\n'
        '<!-- var(subject) = "Combined exclusions" -->\n\nBody',
        encoding="utf-8",
    )
    source.with_suffix(".local.conf").write_text(
        yaml.safe_dump(
            {
                "not_to": {
                    "excel_file": "local.xlsx",
                    "excel_column_name": "LocalBlocked",
                }
            }
        ),
        encoding="utf-8",
    )
    read_excel = pd.read_excel
    forbidden = Mock(
        side_effect=AssertionError("load_conf must not read Excel")
    )
    monkeypatch.setattr(pd, "read_excel", forbidden)
    loaded = core.load_conf(source)
    forbidden.assert_not_called()
    monkeypatch.setattr(pd, "read_excel", read_excel)
    original = deepcopy(loaded)
    prepared = core.compute_conf(loaded)
    expected = {f"{name}@example.org" for name in sources}
    expected.update({"manual-global@example.org", "manual-profile@example.org"})
    assert set(prepared["not_to"]["list"]) == expected
    assert set(prepared["not_to"]) == {"list"}
    assert loaded == original
    prepared["to"]["list"].extend(expected)
    prepared["cc"] = {"list": ["manual-global@example.org"]}
    prepared["bcc"] = {"list": ["manual-profile@example.org"]}
    factory = Mock()
    outlook.deliver(prepared, mail_factory=factory)
    assert factory.return_value.To == "allowed@example.org"
    assert factory.return_value.Cc == factory.return_value.Bcc == ""
    factory.return_value.Save.assert_called_once()
    factory.return_value.Send.assert_not_called()


# -----------------------------------------------------------------------------
@pytest.mark.parametrize("override", [None, {}, {"list": []}])
def test_campaign_cannot_clear_common_blacklist_with_empty_value(
    tmp_path, override
):
    store = preferences.get_preferences_store()
    store.save({"not_to": {"list": ["blocked@example.org"]}})
    source = tmp_path / "campaign.conf"
    source.write_text(
        yaml.safe_dump(
            {
                "not_to": override,
                "email": {"subject": "Test", "content": {"txt": "Body"}},
                "to": {"list": ["allowed@example.org", "blocked@example.org"]},
            }
        ),
        encoding="utf-8",
    )
    prepared = core.compute_conf(core.load_conf(source))
    assert prepared["not_to"]["list"] == ["blocked@example.org"]
    assert prepared["really_send"] is False
    factory = Mock()
    outlook.deliver(prepared, mail_factory=factory)
    assert factory.return_value.To == "allowed@example.org"


# -----------------------------------------------------------------------------
def test_workbook_read_once_per_preparation_and_reloaded_next_run(
    tmp_path, monkeypatch, caplog
):
    workbook = tmp_path / "contacts.xlsx"
    pd.DataFrame(
        {
            "Email": ["allowed@example.org", "blocked@example.org"],
            "BLACKLIST": [" BLOCKED@example.org\u00a0", None],
        }
    ).to_excel(workbook, index=False)
    store = preferences.get_preferences_store()
    store.save(
        {
            "not_to": {
                "excel_file": "contacts.xlsx",
                "excel_column_name": "BLACKLIST",
            }
        }
    )
    source = tmp_path / "campaign.conf"
    source.write_text(
        yaml.safe_dump(
            {
                "not_to": {
                    "excel_file": "contacts.xlsx",
                    "excel_column_name": "BLACKLIST",
                },
                "to": {
                    "excel_file": "contacts.xlsx",
                    "excel_column_name": "Email",
                },
                "email": {"subject": "Test", "content": {"txt": "Body"}},
            }
        ),
        encoding="utf-8",
    )
    read_excel = Mock(wraps=pd.read_excel)
    monkeypatch.setattr(pd, "read_excel", read_excel)
    with caplog.at_level(logging.INFO):
        first = core.compute_conf(core.load_conf(source))
    assert read_excel.call_count == 1
    assert first["not_to"]["list"] == ["blocked@example.org"]
    assert str(workbook) in caplog.text
    assert "colonnes=BLACKLIST" in caplog.text
    assert caplog.text.count("Import Excel not_to") == 1
    pd.DataFrame(
        {
            "Email": ["allowed@example.org"],
            "BLACKLIST": ["newly-blocked@example.org"],
        }
    ).to_excel(workbook, index=False)
    second = core.compute_conf(core.load_conf(source))
    assert read_excel.call_count == 2
    assert second["not_to"]["list"] == ["newly-blocked@example.org"]


# -----------------------------------------------------------------------------
def test_blacklist_filename_can_be_inherited_with_local_column_selection(
    tmp_path,
):
    pd.DataFrame({"BLACKLIST": ["blocked@example.org"]}).to_excel(
        tmp_path / "contacts.xlsx", index=False
    )
    preferences.get_preferences_store().save(
        {"not_to": {"excel_file": "contacts.xlsx"}}
    )
    source = tmp_path / "campaign.conf"
    source.write_text(
        "not_to:\n  excel_column_name: BLACKLIST\n"
        "email:\n  subject: Test\n  content:\n    txt: Body\n",
        encoding="utf-8",
    )
    assert core.compute_conf(core.load_conf(source))["not_to"]["list"] == [
        "blocked@example.org"
    ]


# -----------------------------------------------------------------------------
@pytest.mark.parametrize(
    "data",
    [
        {"excel_file": "contacts.xlsx", "list": ["manual@example.org"]},
        {"excel_column_name": "BLACKLIST"},
    ],
)
def test_incomplete_excel_blacklist_never_falls_back_to_manual_only(
    tmp_path, data
):
    conf = core.default_conf()
    conf["not_to"] = data
    with pytest.raises(
        ValueError, match="not_to.excel_file.*excel_column_name"
    ):
        core.compute_conf(conf)


# -----------------------------------------------------------------------------
@pytest.mark.parametrize("individual", [False, True])
@pytest.mark.parametrize("send", [False, True])
def test_excel_exclusions_filter_every_category_and_delivery_mode(
    tmp_path, individual, send
):
    pd.DataFrame({"BLACKLIST": [" BLOCKED@example.org\u00a0"]}).to_excel(
        tmp_path / "contacts.xlsx", index=False
    )
    conf = core.default_conf()
    conf["paths"]["base_search"] = [str(tmp_path)]
    conf["to"] = {
        "list": ["allowed@example.org", "blocked@example.org"],
        "individual_email": individual,
    }
    conf["cc"] = {"list": ["blocked@example.org"]}
    conf["Bcc"] = {"list": ["blocked@example.org"]}
    conf["bcc"] = None
    conf["not_to"] = {
        "excel_file": "contacts.xlsx",
        "excel_column_name": "BLACKLIST",
    }
    conf["really_send"] = send
    prepared = core.compute_conf(conf)
    original = deepcopy(prepared)
    factory = Mock()
    outlook.deliver(prepared, mail_factory=factory)
    factory.assert_called_once()
    assert factory.return_value.To == "allowed@example.org"
    assert factory.return_value.Cc == factory.return_value.Bcc == ""
    assert factory.return_value.Send.call_count == int(send)
    assert factory.return_value.Save.call_count == int(not send)
    assert prepared == original
