#!/usr/bin/env python
# -*- coding: utf-8 -*-
# =============================================================================
# Author: Florent TOURNOIS | License: MIT
# =============================================================================

from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from pyoutlookmailing import outlook


# -----------------------------------------------------------------------------
@pytest.fixture
def conf(tmp_path):
    return {
        "to": {
            "list": ["ONE@example.org", "one@example.org", "two@example.org"]
        },
        "cc": {"list": ["copy@example.org"]},
        "bcc": {"list": ["blind@example.org"]},
        "paths": {"base_search": [str(tmp_path)], "img": str(tmp_path)},
        "email": {"subject": "Test", "html_body": "<p>Test</p>"},
    }


# -----------------------------------------------------------------------------
def test_default_is_draft_and_bcc_is_private(conf):
    factory = Mock()
    original = deepcopy(conf)
    outlook.deliver(conf, mail_factory=factory)
    mail = factory.return_value
    assert mail.To == "one@example.org; two@example.org"
    assert mail.Cc == "copy@example.org"
    assert mail.Bcc == "blind@example.org"
    mail.Save.assert_called_once()
    mail.Send.assert_not_called()
    assert conf == original


# -----------------------------------------------------------------------------
def test_exclusions_apply_to_all_recipient_types(conf):
    conf["not_to"] = {
        "list": ["ONE@example.org", "copy@example.org", "blind@example.org"]
    }
    factory = Mock()
    outlook.deliver(conf, mail_factory=factory)
    assert factory.return_value.To == "two@example.org"
    assert factory.return_value.Cc == ""
    assert factory.return_value.Bcc == ""


# -----------------------------------------------------------------------------
def test_empty_recipient_set_never_creates_mail(conf):
    conf["to"]["list"] = []
    conf.pop("cc")
    conf.pop("bcc")
    factory = Mock()
    with pytest.raises(ValueError, match="destinataire"):
        outlook.deliver(conf, mail_factory=factory)
    factory.assert_not_called()


# -----------------------------------------------------------------------------
def test_individual_messages_do_not_mutate_input(conf):
    conf["to"]["individual_email"] = True
    conf["really_send"] = True
    original = deepcopy(conf)
    mails = [Mock(), Mock()]
    outlook.deliver(conf, mail_factory=Mock(side_effect=mails))
    assert [mail.To for mail in mails] == ["one@example.org", "two@example.org"]
    for mail in mails:
        mail.Send.assert_called_once()
        mail.Save.assert_not_called()
    assert conf == original


# -----------------------------------------------------------------------------
def test_individual_failure_preserves_input(conf):
    conf["to"]["individual_email"] = True
    original = deepcopy(conf)
    with pytest.raises(RuntimeError):
        outlook.deliver(
            conf,
            mail_factory=Mock(
                side_effect=[Mock(), RuntimeError("COM failure")]
            ),
        )
    assert conf == original


# -----------------------------------------------------------------------------
def test_all_attachments_validated_before_any_delivery(conf):
    conf["email"]["attachments"] = ["missing.pdf"]
    factory = Mock()
    with pytest.raises(FileNotFoundError):
        outlook.deliver(conf, mail_factory=factory)
    factory.assert_not_called()


# -----------------------------------------------------------------------------
def test_cid_with_spaces_and_accents_is_attached_once(conf, tmp_path):
    picture = tmp_path / "été image.png"
    picture.write_bytes(b"example")
    attachment = tmp_path / "agenda.pdf"
    attachment.write_bytes(b"example")
    conf["email"]["html_body"] = (
        '<img src="cid:été image.png"><img SRC = "cid:été image.png">'
    )
    conf["email"]["attachments"] = ["agenda.pdf"]
    factory = Mock()
    outlook.deliver(conf, mail_factory=factory)
    mail = factory.return_value
    assert mail.Attachments.Add.call_count == 2
    mail.Attachments.Add.assert_any_call(str(picture), 1, 0)
    set_property = (
        mail.Attachments.Add.return_value.PropertyAccessor.SetProperty
    )
    set_property.assert_called_once_with(
        "http://schemas.microsoft.com/mapi/proptag/0x3712001F", "été image.png"
    )


# -----------------------------------------------------------------------------
@pytest.mark.parametrize(
    "address",
    [
        "x@example.org; other@example.org",
        "x@example.org\nbcc:y@test.org",
        "invalid",
    ],
)
def test_invalid_addresses_rejected_before_outlook(conf, address):
    conf["to"]["list"] = [address]
    factory = Mock()
    with pytest.raises(ValueError):
        outlook.deliver(conf, mail_factory=factory)
    factory.assert_not_called()


# -----------------------------------------------------------------------------
def test_string_send_flag_rejected(conf):
    conf["really_send"] = "false"
    with pytest.raises(ValueError, match="really_send"):
        outlook.deliver(conf, mail_factory=Mock())


# -----------------------------------------------------------------------------
def test_exact_sender_account(monkeypatch):
    import win32com.client

    account = SimpleNamespace(SmtpAddress="me@example.org")
    application = Mock()
    application.Session.Accounts = [account]
    monkeypatch.setattr(
        win32com.client, "Dispatch", Mock(return_value=application)
    )
    mail = outlook.new_email({"from": "ME@example.org"})
    assert mail.SendUsingAccount is account
    application.CreateItem.reset_mock()
    with pytest.raises(ValueError, match="expéditeur"):
        outlook.new_email({"from": "me"})
    application.CreateItem.assert_not_called()


# -----------------------------------------------------------------------------
def test_missing_pywin32_has_actionable_error(monkeypatch):
    import sys

    monkeypatch.setitem(sys.modules, "win32com.client", None)
    with pytest.raises(RuntimeError, match="Outlook classique"):
        outlook.new_email({})
