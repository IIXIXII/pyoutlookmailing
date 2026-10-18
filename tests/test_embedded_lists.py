#!/usr/bin/env python
# -*- coding: utf-8 -*-
# =============================================================================
# Author: Florent TOURNOIS | License: MIT
# =============================================================================

from unittest.mock import Mock

import pandas as pd
import pytest

from pyoutlookmailing import cli, core
from pyoutlookmailing.embedded import split_configuration


# -----------------------------------------------------------------------------
def test_repeated_recipients_excel_columns_and_attachments_reach_outlook(
    tmp_path, monkeypatch
):
    pd.DataFrame(
        {"Email": ["excel@example.org"], "Other": ["blocked@example.org"]}
    ).to_excel(tmp_path / "contacts.xlsx", index=False)
    for name in ("programme.pdf", "plan.pdf"):
        (tmp_path / name).write_bytes(b"attachment")
    filename = tmp_path / "invitation.md"
    filename.write_text(
        """<!-- var(conf/really_send) = true -->
<!-- var(conf/to/excel_file) = "contacts.xlsx" -->
<!-- var(conf/to/excel_column_name) = "Email" -->
<!-- var(conf/to/excel_column_name) = "Other" -->
<!-- var(conf/to/list) = "[Alice](mailto:alice@example.org)" -->
<!-- var(subject) = "Invitation | European Business Wallet" -->
<!-- var(conf/to/list) = "bob@example.org" -->
<!-- var(summary) = "[EBW] Matinée de travail" -->
<!-- var(conf/to/list) = "[Duplicate](mailto:ALICE@example.org)" -->
<!-- var(conf/cc/list) = "[Copie](mailto:copy@example.org)" -->
<!-- var(conf/cc/list) = "blocked@example.org" -->
<!-- var(conf/bcc/list) = "[Copie cachée](mailto:hidden@example.org)" -->
<!-- var(conf/bcc/list) = "blocked@example.org" -->
<!-- var(conf/not_to/list) = "[Exclusion](mailto:blocked@example.org)" -->
<!-- var(conf/email/attachments) = "programme.pdf" -->
<!-- var(conf/email/attachments) = "plan.pdf" -->

Bonjour **à tous**.
""",
        encoding="utf-8",
    )
    factory = Mock()
    monkeypatch.setattr(core, "new_email", factory)
    assert cli.main(["--conf", str(filename)]) == 0
    mail = factory.return_value
    assert mail.To == "alice@example.org; bob@example.org; excel@example.org"
    assert mail.Cc == "copy@example.org"
    assert mail.Bcc == "hidden@example.org"
    assert mail.Subject == "Invitation | European Business Wallet"
    assert (
        factory.call_args.args[0]["email"]["summary"]
        == "[EBW] Matinée de travail"
    )
    assert [call.args[0] for call in mail.Attachments.Add.call_args_list] == [
        str(tmp_path / "programme.pdf"),
        str(tmp_path / "plan.pdf"),
    ]
    assert "<strong>à tous</strong>" in mail.HTMLBody
    assert "var(conf" not in mail.HTMLBody
    assert "hidden@example.org" not in mail.HTMLBody
    mail.Send.assert_called_once()
    mail.Save.assert_not_called()


# -----------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("destinataire@example.org", "destinataire@example.org"),
        (
            "[destinataire@example.org](mailto:destinataire@example.org)",
            "destinataire@example.org",
        ),
        (
            "[Nom **affiché**](MAILTO:actual%2Btag@example.org)",
            "actual+tag@example.org",
        ),
        ("mailto:actual+tag@example.org", "actual+tag@example.org"),
    ],
)
@pytest.mark.parametrize("suffix", ["", "/0"])
def test_single_recipient_uses_the_link_target_and_preserves_plus(
    value, expected, suffix
):
    conf, _ = split_configuration(
        f'<!-- var(conf/to/list{suffix}) = "{value}" -->'
    )
    assert conf is not None
    assert conf["to"]["list"] == [expected]


# -----------------------------------------------------------------------------
def test_repeated_path_inclusions_preserve_order_and_merge_with_local_config(
    tmp_path,
):
    (tmp_path / "first.conf").write_text(
        "to:\n  list: [first@example.org]\nemail:\n  subject: First\n",
        encoding="utf-8",
    )
    (tmp_path / "second.conf").write_text(
        "to:\n  list: [second@example.org]\nemail:\n  subject: Second\n",
        encoding="utf-8",
    )
    (tmp_path / "mail.local.conf").write_text(
        "to:\n  list: [local@example.org]\n", encoding="utf-8"
    )
    filename = tmp_path / "mail.md"
    filename.write_text(
        """<!-- var(conf/paths/includes) = "first.conf" -->
<!-- var(conf/paths/includes) = "second.conf" -->
<!-- var(conf/to/list) = "[Principal](mailto:main@example.org)" -->

Bonjour.
""",
        encoding="utf-8",
    )
    conf = core.compute_conf(core.load_conf(filename))
    assert conf["to"]["list"] == [
        "first@example.org",
        "second@example.org",
        "main@example.org",
        "local@example.org",
    ]
    assert conf["email"]["subject"] == "Second"


# -----------------------------------------------------------------------------
def test_empty_list_adds_nothing_and_keeps_preceding_items():
    conf, _ = split_configuration(
        "<!-- var(conf/to/list) = [] -->\n"
        '<!-- var(conf/to/list) = "first@example.org" -->\n'
        "<!-- var(conf/to/list) = [] -->\n"
        '<!-- var(conf/to/list) = "second@example.org" -->\n'
        '<!-- var(conf/paths/base_search) = "files" -->\n'
        '<!-- var(conf/paths/base_search) = "attachments" -->'
    )
    assert conf is not None
    assert conf["to"]["list"] == ["first@example.org", "second@example.org"]
    assert conf["paths"]["base_search"] == ["files", "attachments"]


# -----------------------------------------------------------------------------
@pytest.mark.parametrize(
    "value",
    [
        "[Name](https://example.org)",
        "[First](mailto:first@example.org) [Second](mailto:second@example.org)",
        "[Name](mailto:name@example.org?cc=other@example.org)",
        "[Name](mailto:name@example.org#fragment)",
        "[Name](mailto:)",
        "[Incomplete](mailto:name@example.org",
    ],
)
def test_recipient_requires_one_mailto_link_without_parameters(value):
    with pytest.raises(ValueError, match="mailto"):
        split_configuration(f'<!-- var(conf/to/list) = "{value}" -->')


# -----------------------------------------------------------------------------
@pytest.mark.parametrize("value", ["true", "null", "3", "{}"])
def test_list_elements_must_be_strings(value):
    with pytest.raises(ValueError, match="élément entre guillemets"):
        split_configuration(f"<!-- var(conf/to/list) = {value} -->")


# -----------------------------------------------------------------------------
@pytest.mark.parametrize("reverse", [False, True])
def test_indexed_and_appended_values_cannot_target_the_same_list(reverse):
    comments = [
        '<!-- var(conf/to/list) = "first@example.org" -->',
        '<!-- var(conf/to/list/0) = "second@example.org" -->',
    ]
    if reverse:
        comments.reverse()
    with pytest.raises(ValueError, match="Conflit"):
        split_configuration("\n".join(comments))


# -----------------------------------------------------------------------------
@pytest.mark.parametrize(
    "value",
    [
        "[Group](mailto:first@example.org,second@example.org)",
        "mailto:first@example.org%0A",
    ],
)
def test_invalid_mailto_address_fails_before_outlook_access(
    tmp_path, monkeypatch, value
):
    filename = tmp_path / "mail.md"
    filename.write_text(
        f'<!-- var(conf/to/list) = "{value}" -->\n'
        '<!-- var(subject) = "Test" -->\n\nBonjour.',
        encoding="utf-8",
    )
    factory = Mock(side_effect=AssertionError("Must not access Outlook"))
    monkeypatch.setattr(core, "new_email", factory)
    assert cli.main(["--conf", str(filename)]) == 1
    factory.assert_not_called()
