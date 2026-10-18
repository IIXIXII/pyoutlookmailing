#!/usr/bin/env python
# -*- coding: utf-8 -*-
# =============================================================================
# Author: Florent TOURNOIS | License: MIT
# =============================================================================

from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest
import yaml

from pyoutlookmailing import core


# -----------------------------------------------------------------------------
def test_defaults_render_without_outlook_or_files(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    conf = core.default_conf()
    original = deepcopy(conf)
    prepared = core.compute_conf(conf)
    assert "<strong>tout le monde</strong>" in prepared["email"]["html_body"]
    assert prepared["really_send"] is False
    assert conf == original
    assert list(tmp_path.iterdir()) == []


# -----------------------------------------------------------------------------
def test_infer_markdown_and_extract_variables(tmp_path):
    filename = tmp_path / "campagne.conf"
    filename.write_text("email: {}", encoding="utf-8")
    filename.with_suffix(".md").write_text(
        '<!-- var(subject)="Été & automne" -->\n\nBonjour **à tous**.',
        encoding="utf-8",
    )
    conf = core.compute_conf(core.load_conf(filename))
    assert conf["email"]["subject"] == "Été & automne"
    assert "<strong>à tous</strong>" in conf["email"]["html_body"]
    assert "<title>Été &amp; automne</title>" in conf["email"]["html_body"]


# -----------------------------------------------------------------------------
def test_includes_and_local_override_resolve_own_paths(tmp_path):
    shared = tmp_path / "shared"
    shared.mkdir()
    (shared / "base.conf").write_text(
        "paths:\n  jinja: templates\nto:\n  list: [base@example.org]\n"
        "email:\n  subject: Base",
        encoding="utf-8",
    )
    main = tmp_path / "mail.conf"
    main.write_text(
        "paths:\n  includes: [shared/base.conf]\nemail:\n  subject: Main",
        encoding="utf-8",
    )
    main.with_suffix(".local.conf").write_text(
        "email:\n  subject: Local\nto:\n  list: [local@example.org]",
        encoding="utf-8",
    )
    conf = core.load_conf(main)
    assert conf["email"]["subject"] == "Local"
    assert Path(conf["paths"]["jinja"]) == shared / "templates"
    assert conf["to"]["list"] == ["base@example.org", "local@example.org"]
    assert conf["paths"]["conf_filename"] == str(main)


# -----------------------------------------------------------------------------
def test_include_cycle_is_rejected(tmp_path):
    filename = tmp_path / "cycle.conf"
    filename.write_text("paths:\n  includes: [cycle.conf]", encoding="utf-8")
    with pytest.raises(ValueError, match="Cycle"):
        core.load_conf(filename)


# -----------------------------------------------------------------------------
@pytest.mark.parametrize(
    "text", ["", "[]", "true", "paths: []", "paths:\n  includes: base.conf"]
)
def test_invalid_yaml_structure(tmp_path, text):
    filename = tmp_path / "bad.conf"
    filename.write_text(text, encoding="utf-8")
    with pytest.raises(ValueError):
        core.load_conf(filename)


# -----------------------------------------------------------------------------
def test_yaml_does_not_construct_python_objects(tmp_path):
    filename = tmp_path / "bad.conf"
    filename.write_text("!!python/tuple [1, 2]", encoding="utf-8")
    with pytest.raises(yaml.constructor.ConstructorError):
        core.load_conf(filename)


# -----------------------------------------------------------------------------
def test_missing_configuration_is_actionable(tmp_path):
    with pytest.raises(FileNotFoundError):
        core.load_conf(tmp_path / "missing.conf")


# -----------------------------------------------------------------------------
def test_excel_keeps_manual_addresses_and_deduplicates(tmp_path):
    workbook = tmp_path / "contacts.xlsx"
    pd.DataFrame(
        {"Email": [" DUP@example.org ", None, "excel@example.org"]}
    ).to_excel(workbook, index=False)
    conf = {
        "paths": {"base_search": [str(tmp_path)]},
        "to": {
            "list": ["MANUAL@example.org", "dup@example.org"],
            "excel_file": "contacts.xlsx",
            "excel_column_name": "Email",
        },
    }
    result = core.read_excel_list(conf)
    assert result["to"]["list"] == [
        "manual@example.org",
        "dup@example.org",
        "excel@example.org",
    ]
    with pytest.raises(ValueError, match="Colonne"):
        core.email_excel_list(workbook, "Missing")


# -----------------------------------------------------------------------------
def test_commented_excel_columns_use_manual_recipients_and_keep_blacklist(
    tmp_path,
):
    # Same configuration shape as the EBW invitation: only not_to uses Excel.
    pd.DataFrame({"BLACKLIST": ["excluded@example.org"]}).to_excel(
        tmp_path / "contacts.xlsx", index=False
    )
    filename = tmp_path / "2026-09-23 - EBW invitation.conf"
    filename.write_text(
        "to:\n"
        "  excel_file: disabled-source.xlsx\n"
        "  # excel_column_name: [EmailTest]\n"
        "  list: [' MANUAL@example.org ', manual@example.org]\n"
        "not_to:\n"
        "  excel_file: contacts.xlsx\n"
        "  excel_column_name: [BLACKLIST]\n"
        "email:\n"
        "  subject: EBW invitation\n"
        "  content:\n"
        "    txt: '**Invitation**'\n",
        encoding="utf-8",
    )
    conf = core.compute_conf(core.load_conf(filename))
    assert conf["to"]["list"] == ["manual@example.org"]
    assert conf["not_to"]["list"] == ["excluded@example.org"]
    assert "<strong>Invitation</strong>" in conf["email"]["html_body"]


# -----------------------------------------------------------------------------
@pytest.mark.parametrize("manual", [None, []])
def test_missing_excel_columns_without_manual_recipients_still_fails(manual):
    conf = {"to": {"excel_file": "contacts.xlsx", "list": manual}}
    with pytest.raises(ValueError, match=r"to\.excel_column_name.*to\.list"):
        core.read_excel_list(conf)


# -----------------------------------------------------------------------------
@pytest.mark.parametrize("value", ["false", "true", 1, None])
def test_really_send_must_be_boolean(value):
    conf = core.default_conf()
    conf["really_send"] = value
    with pytest.raises(ValueError, match="really_send"):
        core.compute_conf(conf)


# -----------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("mode", "expected"), [("no", False), ("yes", True), ("conf", True)]
)
def test_command_line_send_override(mode, expected):
    conf = core.default_conf()
    conf["really_send"] = True
    assert (
        core.compute_conf(conf, SimpleNamespace(send_mail=mode))["really_send"]
        is expected
    )


# -----------------------------------------------------------------------------
def test_duplicate_markdown_variables_rejected():
    conf = core.default_conf()
    conf["email"]["content"] = {
        "txt": '<!-- var(subject)="A" -->\n<!-- var(subject)="B" -->'
    }
    with pytest.raises(ValueError, match="duplicate"):
        core.compute_conf(conf)


# -----------------------------------------------------------------------------
def test_metadata_cannot_replace_attachment_list():
    conf = core.default_conf()
    conf["email"]["content"] = {"txt": '<!-- var(attachments)="file.txt" -->'}
    with pytest.raises(ValueError, match="attachments"):
        core.compute_conf(conf)


# -----------------------------------------------------------------------------
def test_utf8_markdown_with_emoji_and_bom(tmp_path):
    filename = tmp_path / "mail.conf"
    filename.write_text("email: {}", encoding="utf-8")
    filename.with_suffix(".md").write_text(
        '<!-- var(subject)="Invitation" -->\n\n'
        "## 📍 Détails\n\n📆 Été – événement européen\n",
        encoding="utf-8-sig",
    )
    html = core.compute_conf(core.load_conf(filename))["email"]["html_body"]
    assert "📍" in html
    assert "📆 Été" in html
