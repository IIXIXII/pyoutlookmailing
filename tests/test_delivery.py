#!/usr/bin/env python
# -*- coding: utf-8 -*-
# =============================================================================
# Author: Florent TOURNOIS | License: MIT
# =============================================================================

import logging
from copy import deepcopy
from email import policy
from email.message import EmailMessage
from email.parser import BytesParser
from types import SimpleNamespace
from unittest.mock import Mock
from urllib.parse import unquote

import pytest
from bs4 import BeautifulSoup

from pyoutlookmailing import outlook


# -----------------------------------------------------------------------------
class ComPropertyError(Exception):
    """Expose pywin32 COM error fields without importing Windows APIs."""

    def __init__(self, hresult, excepinfo=None):
        self.hresult = hresult
        self.excepinfo = excepinfo
        super().__init__(
            hresult, "Une exception s'est produite.", excepinfo, None
        )


# -----------------------------------------------------------------------------
def read_only_property_error():
    """Reproduce the exact nested SCODE reported by the user's Outlook."""
    return ComPropertyError(
        -2147352567,
        (
            4096,
            "Microsoft Outlook",
            "La propriété ne prend pas en charge cette opération.",
            None,
            0,
            -2147024891,
        ),
    )


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
@pytest.mark.parametrize("send", [False, True])
def test_delivery_logs_addresses_immediately_after_status(conf, caplog, send):
    conf["really_send"] = send
    conf["to"]["individual_email"] = True
    with caplog.at_level(logging.INFO):
        outlook.deliver(conf, mail_factory=Mock())
    status = "envoyé" if send else "brouillon enregistré"
    messages = [record.getMessage() for record in caplog.records]
    for index, address in enumerate(("one@example.org", "two@example.org"), 1):
        assert (
            f"Message {index}/2 : {status} {address}"
            " | Cc : copy@example.org | Cci : blind@example.org"
        ) in messages


# -----------------------------------------------------------------------------
def test_group_log_includes_all_recipient_categories(conf, caplog):
    conf["really_send"] = True
    with caplog.at_level(logging.INFO):
        outlook.deliver(conf, mail_factory=Mock())
    assert (
        "envoyé one@example.org; two@example.org"
        " | Cc : copy@example.org | Cci : blind@example.org"
    ) in caplog.text


# -----------------------------------------------------------------------------
def test_blacklist_logs_removed_addresses_and_counts(conf, caplog):
    conf["not_to"] = {
        "list": [
            " ONE@example.org\u00a0",
            "COPY@example.org",
            "blind@example.org",
        ]
    }
    with caplog.at_level(logging.INFO):
        outlook.deliver(conf, mail_factory=Mock())
    assert "Blacklist not_to : 3 adresses ; exclusions To=1, Cc=1, Cci=1" in (
        caplog.text
    )
    for address in ("one@example.org", "copy@example.org", "blind@example.org"):
        assert f"Exclu (not_to) : {address}" in caplog.text
    success = [
        record.getMessage()
        for record in caplog.records
        if "brouillon enregistré" in record.getMessage()
    ]
    assert success == ["Message 1/1 : brouillon enregistré two@example.org"]


# -----------------------------------------------------------------------------
@pytest.mark.parametrize("individual", [False, True])
def test_fully_blacklisted_recipients_never_create_a_message(conf, individual):
    conf["really_send"] = True
    conf["to"]["individual_email"] = individual
    conf["not_to"] = {
        "list": [
            "one@example.org",
            "two@example.org",
            "copy@example.org",
            "blind@example.org",
        ]
    }
    original = deepcopy(conf)
    factory = Mock()
    with pytest.raises(ValueError, match="destinataire"):
        outlook.deliver(conf, mail_factory=factory)
    factory.assert_not_called()
    assert conf == original


# -----------------------------------------------------------------------------
@pytest.mark.parametrize("value", [False, [], 0, ""])
def test_falsey_malformed_blacklist_is_not_silently_ignored(conf, value):
    conf["not_to"] = value
    factory = Mock()
    with pytest.raises(ValueError, match="not_to"):
        outlook.deliver(conf, mail_factory=factory)
    factory.assert_not_called()


# -----------------------------------------------------------------------------
def test_unloaded_excel_blacklist_prevents_outlook_access(conf):
    conf["not_to"] = {
        "excel_file": "contacts.xlsx",
        "excel_column_name": "BLACKLIST",
    }
    factory = Mock()
    with pytest.raises(ValueError, match="compute_conf"):
        outlook.deliver(conf, mail_factory=factory)
    factory.assert_not_called()


# -----------------------------------------------------------------------------
def test_legacy_bcc_is_filtered_even_if_lowercase_bcc_is_null(conf):
    conf["Bcc"] = conf["bcc"]
    conf["bcc"] = None
    conf["not_to"] = {"list": ["blind@example.org"]}
    factory = Mock()
    outlook.deliver(conf, mail_factory=factory)
    assert factory.return_value.Bcc == ""


# -----------------------------------------------------------------------------
def test_failed_send_has_no_success_log(conf, caplog):
    conf["really_send"] = True
    mail = Mock()
    mail.Send.side_effect = RuntimeError("Send failed")
    with caplog.at_level(logging.INFO), pytest.raises(RuntimeError):
        outlook.deliver(conf, mail_factory=Mock(return_value=mail))
    assert "envoyé" not in caplog.text


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
    ids = outlook.CID_PATTERN.findall(mail.HTMLBody)
    assert len(ids) == 2 and ids[0] == ids[1]
    content_id = ids[0]
    assert content_id.isascii() and "@" in content_id
    assert not any(char.isspace() for char in content_id)
    assert "%" not in content_id
    set_property.assert_any_call(outlook.ATTACH_CONTENT_ID, content_id)
    set_property.assert_any_call(outlook.ATTACH_MIME_TAG, "image/png")
    set_property.assert_any_call(outlook.ATTACH_FLAGS, 4)
    set_property.assert_any_call(outlook.ATTACHMENT_HIDDEN, True)
    assert "cid:été image.png" in conf["email"]["html_body"]


# -----------------------------------------------------------------------------
def test_encoded_cid_aliases_resolve_to_one_mime_part(conf, tmp_path):
    picture = tmp_path / "été & logo.png"
    picture.write_bytes(b"image content")
    conf["email"]["html_body"] = (
        '<img src="cid:%C3%A9t%C3%A9%20%26%20logo.png" alt="First">'
        "<img SRC = 'CID:été &amp; logo.png' alt='Second'>"
    )
    original = deepcopy(conf)
    factory = Mock()
    outlook.deliver(conf, mail_factory=factory)
    mail = factory.return_value
    mail.Attachments.Add.assert_called_once_with(str(picture), 1, 0)
    accessor = mail.Attachments.Add.return_value.PropertyAccessor
    properties = dict(call.args for call in accessor.SetProperty.call_args_list)
    content_id = properties[outlook.ATTACH_CONTENT_ID]
    references = [
        str(image["src"])[4:]
        for image in BeautifulSoup(mail.HTMLBody, "html.parser").find_all("img")
    ]
    assert references == [content_id, content_id]
    assert unquote(content_id) == content_id
    assert properties[outlook.ATTACH_MIME_TAG] == "image/png"
    assert properties[outlook.ATTACH_FLAGS] == 4

    # Check the link against a serialized MIME Content-ID, after normal URI
    # decoding. This was mismatched when an encoded filename was copied as-is.
    message = EmailMessage()
    message.set_content(mail.HTMLBody, subtype="html")
    message.add_related(
        picture.read_bytes(),
        maintype="image",
        subtype="png",
        cid=f"<{content_id}>",
        disposition="inline",
        filename=picture.name,
    )
    received = BytesParser(policy=policy.default).parsebytes(message.as_bytes())
    images = [
        part
        for part in received.walk()
        if part.get_content_type() == "image/png"
    ]
    assert len(images) == 1
    assert images[0]["Content-ID"] == f"<{unquote(references[0])}>"
    assert images[0].get_content_disposition() == "inline"
    assert images[0].get_payload(decode=True) == picture.read_bytes()
    assert conf == original


# -----------------------------------------------------------------------------
@pytest.mark.parametrize("send", [False, True])
def test_individual_messages_get_unique_matching_inline_ids(
    conf, tmp_path, send
):
    picture = tmp_path / "logo.jpg"
    picture.write_bytes(b"image content")
    conf["really_send"] = send
    conf["to"]["individual_email"] = True
    conf["email"]["html_body"] = '<img src="cid:logo.jpg">'
    messages = [Mock(), Mock()]
    outlook.deliver(conf, mail_factory=Mock(side_effect=messages))
    identifiers = []
    for mail in messages:
        references = outlook.CID_PATTERN.findall(mail.HTMLBody)
        assert len(references) == 1
        content_id = references[0]
        identifiers.append(content_id)
        properties = mail.Attachments.Add.return_value.PropertyAccessor
        properties.SetProperty.assert_any_call(
            outlook.ATTACH_CONTENT_ID, content_id
        )
        properties.SetProperty.assert_any_call(
            outlook.ATTACH_MIME_TAG, "image/jpeg"
        )
        assert mail.Send.call_count == int(send)
        assert mail.Save.call_count == int(not send)
    assert len(set(identifiers)) == 2


# -----------------------------------------------------------------------------
def test_all_inline_images_are_validated_before_creating_any_message(
    conf, tmp_path
):
    (tmp_path / "exists.png").write_bytes(b"image content")
    conf["email"]["html_body"] = (
        '<img src="cid:exists.png"><img src="cid:missing.png">'
    )
    factory = Mock()
    with pytest.raises(FileNotFoundError):
        outlook.deliver(conf, mail_factory=factory)
    factory.assert_not_called()


# -----------------------------------------------------------------------------
@pytest.mark.parametrize("send", [False, True])
@pytest.mark.parametrize(
    "schema", [outlook.ATTACH_FLAGS, outlook.ATTACHMENT_HIDDEN]
)
def test_read_only_optional_inline_metadata_keeps_matching_cids_and_delivery(
    conf, tmp_path, caplog, send, schema
):
    picture = tmp_path / "logo.png"
    picture.write_bytes(b"image content")
    conf["really_send"] = send
    conf["to"]["individual_email"] = True
    conf["email"]["html_body"] = '<img src="cid:logo.png">'
    original = deepcopy(conf)
    messages = [Mock(), Mock()]
    properties_by_message = [{}, {}]

    # -------------------------------------------------------------------------
    def set_property(index, key, value):
        if key == schema:
            if schema == outlook.ATTACH_FLAGS:
                raise read_only_property_error()
            raise ComPropertyError(0x80040102 - (1 << 32))
        properties_by_message[index][key] = value

    for index, mail in enumerate(messages):
        accessor = mail.Attachments.Add.return_value.PropertyAccessor
        accessor.SetProperty.side_effect = lambda key, value, index=index: (
            set_property(index, key, value)
        )
    with caplog.at_level(logging.WARNING):
        outlook.deliver(conf, mail_factory=Mock(side_effect=messages))
    for index, mail in enumerate(messages):
        content_id = outlook.CID_PATTERN.findall(mail.HTMLBody)[0]
        assert (
            properties_by_message[index][outlook.ATTACH_CONTENT_ID]
            == content_id
        )
        assert (
            properties_by_message[index][outlook.ATTACH_MIME_TAG] == "image/png"
        )
        assert mail.Send.call_count == int(send)
        assert mail.Save.call_count == int(not send)
    assert caplog.text.count("propriété facultative") == 1
    assert schema.rsplit("/", 1)[-1] in caplog.text
    assert "logo.png" in caplog.text
    # Unsupported flags are attempted just once per delivery, not per recipient.
    calls = []
    for mail in messages:
        accessor = mail.Attachments.Add.return_value.PropertyAccessor
        calls.extend(
            call.args[0] for call in accessor.SetProperty.call_args_list
        )
    assert calls.count(schema) == 1
    assert conf == original

    # Capability detection must reset for a later delivery (e.g. another store).
    later_factory = Mock()
    outlook.deliver(conf, mail_factory=later_factory)
    later_accessor = (
        later_factory.return_value.Attachments.Add.return_value.PropertyAccessor
    )
    assert any(
        call.args[0] == schema
        for call in later_accessor.SetProperty.call_args_list
    )


# -----------------------------------------------------------------------------
@pytest.mark.parametrize(
    "schema", [outlook.ATTACH_CONTENT_ID, outlook.ATTACH_MIME_TAG]
)
def test_denied_required_inline_properties_still_block_delivery(
    conf, tmp_path, schema
):
    (tmp_path / "logo.png").write_bytes(b"image content")
    conf["really_send"] = True
    conf["email"]["html_body"] = '<img src="cid:logo.png">'
    factory = Mock()
    error = read_only_property_error()

    # -------------------------------------------------------------------------
    def set_property(key, value):
        if key == schema:
            raise error

    accessor = (
        factory.return_value.Attachments.Add.return_value.PropertyAccessor
    )
    accessor.SetProperty.side_effect = set_property
    with pytest.raises(ComPropertyError) as caught:
        outlook.deliver(conf, mail_factory=factory)
    assert caught.value is error
    factory.return_value.Send.assert_not_called()
    factory.return_value.Save.assert_not_called()


# -----------------------------------------------------------------------------
@pytest.mark.parametrize("com_error", [False, True])
def test_unexpected_optional_property_failure_still_blocks_delivery(
    conf, tmp_path, com_error
):
    (tmp_path / "logo.png").write_bytes(b"image content")
    conf["really_send"] = True
    conf["email"]["html_body"] = '<img src="cid:logo.png">'
    factory = Mock()
    error = (
        ComPropertyError(-2147467259)
        if com_error
        else RuntimeError("provider failure")
    )

    # -------------------------------------------------------------------------
    def set_property(key, value):
        if key == outlook.ATTACH_FLAGS:
            raise error

    accessor = (
        factory.return_value.Attachments.Add.return_value.PropertyAccessor
    )
    accessor.SetProperty.side_effect = set_property
    with pytest.raises(type(error)) as caught:
        outlook.deliver(conf, mail_factory=factory)
    assert caught.value is error
    factory.return_value.Send.assert_not_called()
    factory.return_value.Save.assert_not_called()


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
