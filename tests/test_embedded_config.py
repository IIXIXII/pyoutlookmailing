#!/usr/bin/env python
# -*- coding: utf-8 -*-
# =============================================================================
# Author: Florent TOURNOIS | License: MIT
# =============================================================================

import json
from pathlib import Path
from unittest.mock import Mock

import pandas as pd
import pytest
import yaml
from pymdtools.instruction import escape_var_value, set_var_to_md_text

from pyoutlookmailing import cli, core, genenv, outlook
from pyoutlookmailing.embedded import split_configuration


# -----------------------------------------------------------------------------
def write_markdown(filename, configuration, body="Bonjour **à tous**."):
    # --------------------------------------------------------------------------
    def comments(path, value):
        if isinstance(value, dict) and value:
            return "\n".join(
                comments(f"{path}/{key}", item) for key, item in value.items()
            )
        if isinstance(value, list) and value:
            return "\n".join(
                comments(f"{path}/{index}", item)
                for index, item in enumerate(value)
            )
        literal = (
            f'"{escape_var_value(value)}"'
            if isinstance(value, str)
            else json.dumps(value)
        )
        return f"<!-- var({path}) = {literal} -->"

    filename.write_text(
        f"{comments('conf', configuration)}\n\n{body}", encoding="utf-8"
    )
    return filename


# -----------------------------------------------------------------------------
def test_entire_config_in_markdown_with_excel_and_attachments(
    tmp_path, monkeypatch
):
    pd.DataFrame(
        {"Email": ["listed@example.org"], "BLACKLIST": ["blocked@example.org"]}
    ).to_excel(tmp_path / "contacts.xlsx", index=False)
    (tmp_path / "agenda.pdf").write_bytes(b"test attachment")
    (tmp_path / "hero.png").write_bytes(b"test image")
    filename = write_markdown(
        tmp_path / "Invitation été.md",
        {
            "really_send": True,
            "from": "sender@example.org",
            "paths": {"root": ".", "img": "."},
            "to": {
                "excel_file": "contacts.xlsx",
                "excel_column_name": ["Email"],
                "list": ["manual@example.org", "blocked@example.org"],
            },
            "not_to": {
                "excel_file": "contacts.xlsx",
                "excel_column_name": ["BLACKLIST"],
            },
            "cc": {"list": ["copy@example.org"]},
            "bcc": {"list": ["hidden@example.org"]},
            "email": {"subject": "Invitation", "attachments": ["agenda.pdf"]},
        },
        body=(
            "## 📍 Invitation\n\nBonjour **à tous**.\n\n"
            '<img src="cid:hero.png">'
        ),
    )
    elsewhere = tmp_path / "other"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    conf = core.compute_conf(core.load_conf(filename))
    assert conf["really_send"] is True
    assert conf["from"] == "sender@example.org"
    assert Path(conf["paths"]["img"]) == tmp_path
    html = conf["email"]["html_body"]
    assert "<strong>à tous</strong>" in html
    assert "var(conf" not in html
    assert "really_send" not in html
    assert "hidden@example.org" not in html
    factory = Mock()
    outlook.deliver(conf, mail_factory=factory)
    mail = factory.return_value
    assert mail.To == "manual@example.org; listed@example.org"
    assert mail.Cc == "copy@example.org"
    assert mail.Bcc == "hidden@example.org"
    assert mail.Attachments.Add.call_count == 2
    mail.Send.assert_called_once()
    mail.Save.assert_not_called()


# -----------------------------------------------------------------------------
@pytest.mark.parametrize(
    "suffix", [".md", ".markdown", ".MD", ".mailmd", ".MAILMD", ".mail.md"]
)
def test_markdown_source_and_existing_variables(tmp_path, suffix):
    filename = write_markdown(
        tmp_path / f"invitation{suffix}",
        {"email": {"subject": "Initial"}},
        body='<!-- var(subject)="Objet final" -->\n\nBonjour.',
    )
    conf = core.compute_conf(core.load_conf(filename))
    assert conf["email"]["subject"] == "Objet final"
    assert conf["really_send"] is False
    assert "Bonjour" in conf["email"]["html_body"]


# -----------------------------------------------------------------------------
def test_header_config_after_other_comments_and_bom(tmp_path):
    filename = tmp_path / "mail.md"
    filename.write_text(
        '<!-- var(subject)="En-tête" -->\n<!-- author note -->\n'
        "<!-- var(conf/really_send) = false -->\n\nCorps.",
        encoding="utf-8-sig",
    )
    conf = core.compute_conf(core.load_conf(filename))
    assert conf["email"]["subject"] == "En-tête"
    assert "Corps." in conf["email"]["html_body"]


# -----------------------------------------------------------------------------
def test_standard_quoted_pymdtools_variable_is_supported(tmp_path):
    text = set_var_to_md_text(
        "Bonjour.",
        "conf",
        'email:\n  subject: "Invitation"\nreally_send: false',
    )
    filename = tmp_path / "mail.md"
    filename.write_text(text, encoding="utf-8")
    conf = core.compute_conf(core.load_conf(filename))
    assert conf["email"]["subject"] == "Invitation"
    assert "var(conf)" not in conf["email"]["html_body"]


# -----------------------------------------------------------------------------
@pytest.mark.parametrize("suffix", [".md", ".mailmd"])
def test_includes_local_override_and_relative_paths(tmp_path, suffix):
    shared = tmp_path / "shared"
    shared.mkdir()
    (shared / "base.conf").write_text(
        "paths:\n  img: images\nemail:\n  subject: Base\n", encoding="utf-8"
    )
    filename = write_markdown(
        tmp_path / f"mail{suffix}",
        {
            "paths": {"includes": ["shared/base.conf"]},
            "really_send": True,
            "email": {"subject": "Embedded"},
        },
    )
    filename.with_suffix(".local.conf").write_text(
        "really_send: false\nemail:\n  subject: Local", encoding="utf-8"
    )
    conf = core.compute_conf(core.load_conf(filename))
    assert conf["really_send"] is False
    assert conf["email"]["subject"] == "Local"
    assert Path(conf["paths"]["img"]) == shared / "images"


# -----------------------------------------------------------------------------
def test_mixed_markdown_yaml_include_cycle_is_rejected(tmp_path):
    filename = write_markdown(
        tmp_path / "mail.md", {"paths": {"includes": ["base.conf"]}}
    )
    (tmp_path / "base.conf").write_text(
        "paths:\n  includes: [mail.md]", encoding="utf-8"
    )
    with pytest.raises(ValueError, match="Cycle"):
        core.load_conf(filename)


# -----------------------------------------------------------------------------
def test_explicit_conf_takes_precedence_over_config_in_email_body(tmp_path):
    write_markdown(
        tmp_path / "mail.md",
        {
            "really_send": True,
            "to": {"list": ["embedded@example.org"]},
            "email": {"subject": "Embedded"},
        },
    )
    filename = tmp_path / "mail.conf"
    filename.write_text(
        "really_send: false\nto:\n  list: [external@example.org]\n"
        "email:\n  subject: External",
        encoding="utf-8",
    )
    conf = core.compute_conf(core.load_conf(filename))
    assert conf["really_send"] is False
    assert conf["to"]["list"] == ["external@example.org"]
    assert conf["email"]["subject"] == "External"
    assert "embedded@example.org" not in conf["email"]["html_body"]


# -----------------------------------------------------------------------------
@pytest.mark.parametrize(
    "payload", ["", "[]", "false", "email: [", "email: []"]
)
def test_invalid_embedded_yaml_is_rejected(tmp_path, payload):
    filename = tmp_path / "mail.md"
    filename.write_text(
        f"<!-- var(conf) =\n{payload}\n-->\nBonjour", encoding="utf-8"
    )
    with pytest.raises((ValueError, yaml.YAMLError)):
        core.load_conf(filename)


# -----------------------------------------------------------------------------
def test_embedded_yaml_cannot_construct_python_objects(tmp_path):
    filename = tmp_path / "mail.md"
    filename.write_text(
        "<!-- var(conf) =\n!!python/tuple [1, 2]\n-->", encoding="utf-8"
    )
    with pytest.raises(yaml.constructor.ConstructorError):
        core.load_conf(filename)


# -----------------------------------------------------------------------------
@pytest.mark.parametrize(
    "text",
    [
        "Bonjour.",
        "```html\n<!-- var(conf) =\nemail: {}\n-->\n```",
        "Bonjour.\n<!-- var(conf) =\nemail: {}\n-->",
        "<!-- var(conf) =\nemail: {}",
        "<!-- var(conf) =\nemail: {}\n-->\n<!-- var(conf) =\nemail: {}\n-->",
    ],
)
def test_missing_misplaced_unclosed_or_duplicate_config_is_rejected(
    tmp_path, text
):
    filename = tmp_path / "mail.md"
    filename.write_text(text, encoding="utf-8")
    with pytest.raises(ValueError, match="var\\(conf\\)"):
        core.load_conf(filename)


# -----------------------------------------------------------------------------
def test_code_example_is_not_extracted_as_configuration():
    text = "```html\n<!-- var(conf) =\nemail: {}\n-->\n```"
    assert split_configuration(text) == (None, text)


# -----------------------------------------------------------------------------
def test_direct_markdown_render_does_not_expose_configuration():
    text = '<!-- var(conf/to/list/0) = "hidden@example.org" -->\n\n**Bonjour**'
    html = core.md2html(text, genenv.GenerationEnvironment({"paths": {}}), {})
    assert "hidden@example.org" not in html
    assert "var(conf" not in html
    assert "<strong>Bonjour</strong>" in html


# -----------------------------------------------------------------------------
def test_preview_markdown_does_not_deliver_or_leak_configuration(
    tmp_path, monkeypatch
):
    filename = write_markdown(
        tmp_path / "mail.md",
        {
            "really_send": True,
            "to": {"list": ["hidden@example.org"]},
            "email": {"subject": "Invitation"},
        },
    )
    delivery = Mock(side_effect=AssertionError("Must not deliver"))
    monkeypatch.setattr(cli, "send_email", delivery)
    preview = tmp_path / "preview.html"
    assert cli.main(["--conf", str(filename), "--preview", str(preview)]) == 0
    delivery.assert_not_called()
    html = preview.read_text(encoding="utf-8")
    assert "var(conf" not in html
    assert "hidden@example.org" not in html
    assert "<strong>à tous</strong>" in html


# -----------------------------------------------------------------------------
@pytest.mark.parametrize("flag", [True, False])
@pytest.mark.parametrize("mode", [None, "no", "yes"])
def test_embedded_send_flag_and_cli_override(tmp_path, monkeypatch, flag, mode):
    filename = write_markdown(
        tmp_path / "mail.md",
        {
            "really_send": flag,
            "to": {"list": ["test@example.org"]},
            "email": {"subject": "Invitation"},
        },
    )
    factory = Mock()
    monkeypatch.setattr(core, "new_email", factory)
    args = ["--conf", str(filename)]
    if mode:
        args.extend(["--send-mail", mode])
    assert cli.main(args) == 0
    should_send = flag if mode is None else mode == "yes"
    assert factory.return_value.Send.call_count == int(should_send)
    assert factory.return_value.Save.call_count == int(not should_send)


# -----------------------------------------------------------------------------
def test_variable_comments_preserve_types_escaping_and_other_comments():
    text = r"""<!-- var(conf/really_send) = false -->
<!-- var(subject) = "Objet" -->
<!-- var(conf/email/title) = 'L\'été "2026"' -->
<!-- note -->
<!-- var(conf/paths/root) = "C:\\dev\\new folder" -->
<!-- var(conf/email/description) = "Ligne 1\nLigne 2" -->
<!-- var(conf/email/width) = 600 -->
<!-- var(conf/email/ratio) = 1.5 -->
<!-- var(conf/email/string) = "false" -->
<!-- var(conf/email/empty) = "" -->
<!-- var(conf/email/optional) = null -->
<!-- var(conf/email/content) = {} -->
<!-- var(conf/bcc/list) = [] -->

Bonjour.
"""
    conf, body = split_configuration(text, required=True)
    assert conf == {
        "really_send": False,
        "paths": {"root": r"C:\dev\new folder"},
        "email": {
            "title": 'L\'été "2026"',
            "description": "Ligne 1\nLigne 2",
            "width": 600,
            "ratio": 1.5,
            "string": "false",
            "empty": "",
            "optional": None,
            "content": {},
        },
        "bcc": {"list": []},
    }
    assert '<!-- var(subject) = "Objet" -->' in body
    assert "<!-- note -->" in body
    assert "Bonjour." in body
    assert "var(conf" not in body


# -----------------------------------------------------------------------------
def test_indexed_lists_accept_unordered_definitions_and_nested_fields():
    conf, _ = split_configuration(
        '<!-- var(conf/to/list/1) = "second@example.org" -->\n'
        '<!-- var(conf/email/items/0/label) = "Programme" -->\n'
        '<!-- var(conf/to/list/0) = "first@example.org" -->\n'
        '<!-- var(conf/email/items/0/url) = "https://example.org" -->',
        required=True,
    )
    assert conf == {
        "to": {"list": ["first@example.org", "second@example.org"]},
        "email": {
            "items": [{"label": "Programme", "url": "https://example.org"}]
        },
    }


# -----------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("text", "error"),
    [
        ("<!-- var(conf/really_send) = false", "fermé"),
        ("<!-- var(conf/really_send) false -->", "mal formé"),
        ("<!-- var(conf/really_send) = -->", "Valeur invalide"),
        ("<!-- var(conf/really_send) = flase -->", "Valeur invalide"),
        ('<!-- var(conf/email/subject) = "unclosed -->', "Valeur invalide"),
        (
            "<!-- var(conf/email/content) = !!python/tuple [1, 2] -->",
            "Valeur invalide",
        ),
        ("<!-- var(conf/) = false -->", "Chemin invalide"),
        ('<!-- var(conf/to//list/0) = "a@example.org" -->', "Chemin invalide"),
        ('<!-- var(conf/to/list/01) = "a@example.org" -->', "Chemin invalide"),
        ('<!-- var(conf/to/list/1) = "a@example.org" -->', "indices de liste"),
        (
            '<!-- var(conf/to/list/0) = "a@example.org" -->\n'
            '<!-- var(conf/to/list/name) = "b@example.org" -->',
            "indices de liste",
        ),
        (
            "<!-- var(conf/really_send) = false -->\n"
            "<!-- var(conf/really_send) = true -->",
            "plusieurs fois",
        ),
        (
            "<!-- var(conf/to/list) = [] -->\n"
            '<!-- var(conf/to/list/0) = "a@example.org" -->',
            "Conflit",
        ),
        (
            '<!-- var(conf/to/list/0) = "a@example.org" -->\n'
            "<!-- var(conf/to/list) = [] -->",
            "Conflit",
        ),
        (
            "<!-- var(conf) = {} -->\n<!-- var(conf/really_send) = false -->",
            "mélangés",
        ),
        (
            "<!-- var(conf/really_send) = false -->\n<!-- var(conf) = {} -->",
            "mélangés",
        ),
    ],
)
def test_invalid_variable_configuration_is_rejected(text, error):
    with pytest.raises(ValueError, match=error):
        split_configuration(text, required=True)


# -----------------------------------------------------------------------------
@pytest.mark.parametrize("prefix", ["Bonjour.\n", "```html\n", "    "])
def test_variables_in_body_or_code_are_not_configuration(prefix):
    text = prefix + "<!-- var(conf/really_send) = true -->"
    assert split_configuration(text) == (None, text)
    with pytest.raises(ValueError, match="commencer"):
        split_configuration(text, required=True)


# -----------------------------------------------------------------------------
def test_quoted_false_is_rejected_before_outlook_access(
    tmp_path, monkeypatch, caplog
):
    filename = write_markdown(
        tmp_path / "mail.md",
        {"really_send": "false", "email": {"subject": "Invitation"}},
    )
    factory = Mock(side_effect=AssertionError("Must not access Outlook"))
    monkeypatch.setattr(core, "new_email", factory)
    assert cli.main(["--conf", str(filename)]) == 1
    factory.assert_not_called()
    assert "sans guillemets" in caplog.text
