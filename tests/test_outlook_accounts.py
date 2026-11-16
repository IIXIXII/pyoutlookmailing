#!/usr/bin/env python
# -*- coding: utf-8 -*-
# =============================================================================
# Author: Florent TOURNOIS | License: MIT
# =============================================================================

"""Keep drafts and sent copies in the sending account, not an archive PST."""

import logging
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from pyoutlookmailing import outlook


# -----------------------------------------------------------------------------
def make_account(address, store_id):
    drafts = Mock(FolderPath=f"\\\\{address}\\Brouillons")
    sent = Mock(FolderPath=f"\\\\{address}\\Éléments envoyés")
    store = Mock(StoreID=store_id)
    store.GetDefaultFolder.side_effect = {
        outlook.OL_FOLDER_DRAFTS: drafts,
        outlook.OL_FOLDER_SENT_MAIL: sent,
    }.get
    return (
        SimpleNamespace(SmtpAddress=address, DeliveryStore=store),
        drafts,
        sent,
    )


# -----------------------------------------------------------------------------
@pytest.fixture
def application(monkeypatch):
    import win32com.client

    application = Mock()
    application.Session.Accounts = []
    application.ActiveExplorer.return_value = None
    application.CreateItem.side_effect = AssertionError("Wrong default store")
    application.Session.GetDefaultFolder.side_effect = AssertionError(
        "Wrong default store"
    )
    monkeypatch.setattr(
        win32com.client, "Dispatch", Mock(return_value=application)
    )
    return application


# -----------------------------------------------------------------------------
@pytest.mark.parametrize("send", [False, True])
def test_draft_and_sent_copy_use_explicit_account_despite_default_archive(
    application, caplog, send
):
    other, other_drafts, _ = make_account("other@example.org", "OTHER")
    account, drafts, sent = make_account("work@example.org", "WORK")
    application.Session.Accounts = [other, account]
    application.Session.DefaultStore = Mock(StoreID="ARCHIVE_PST")
    application.ActiveExplorer.return_value = SimpleNamespace(
        CurrentFolder=SimpleNamespace(Store=other.DeliveryStore)
    )
    conf = {
        "from": " WORK@example.org ",
        "really_send": send,
        "to": {"list": ["recipient@example.org"]},
        "email": {"subject": "Test", "html_body": "<p>Body</p>"},
    }
    original = deepcopy(conf)
    with caplog.at_level(logging.INFO):
        outlook.deliver(conf)
    mail = drafts.Items.Add.return_value
    drafts.Items.Add.assert_called_once_with("IPM.Note")
    other_drafts.Items.Add.assert_not_called()
    application.CreateItem.assert_not_called()
    assert mail.SendUsingAccount is account
    assert mail.SaveSentMessageFolder is sent
    assert mail.DeleteAfterSubmit is False
    assert mail.Send.call_count == int(send)
    assert mail.Save.call_count == int(not send)
    assert "Compte Outlook : work@example.org" in caplog.text
    assert drafts.FolderPath in caplog.text
    assert sent.FolderPath in caplog.text
    assert conf == original


# -----------------------------------------------------------------------------
def test_without_from_uses_account_of_active_folder(application):
    other, other_drafts, _ = make_account("other@example.org", "OTHER")
    active, drafts, sent = make_account("active@example.org", "ACTIVE")
    application.Session.Accounts = [other, active]
    application.ActiveExplorer.return_value = SimpleNamespace(
        CurrentFolder=SimpleNamespace(Store=active.DeliveryStore)
    )
    mail = outlook.new_email({})
    assert mail is drafts.Items.Add.return_value
    assert mail.SendUsingAccount is active
    assert mail.SaveSentMessageFolder is sent
    other_drafts.Items.Add.assert_not_called()


# -----------------------------------------------------------------------------
def test_single_account_works_without_an_explorer(application):
    account, drafts, _ = make_account("work@example.org", "WORK")
    application.Session.Accounts = [account]
    mail = outlook.new_email({})
    assert mail is drafts.Items.Add.return_value
    assert mail.SendUsingAccount is account


# -----------------------------------------------------------------------------
@pytest.mark.parametrize("active_store", [None, "ARCHIVE_PST", "SHARED"])
def test_ambiguous_or_archived_active_folder_requires_from(
    application, active_store
):
    first, first_drafts, _ = make_account("first@example.org", "SHARED")
    second, second_drafts, _ = make_account("second@example.org", "SHARED")
    application.Session.Accounts = [first, second]
    if active_store is not None:
        application.ActiveExplorer.return_value = SimpleNamespace(
            CurrentFolder=SimpleNamespace(
                Store=SimpleNamespace(StoreID=active_store)
            )
        )
    with pytest.raises(ValueError, match="from"):
        outlook.new_email({})
    first_drafts.Items.Add.assert_not_called()
    second_drafts.Items.Add.assert_not_called()
    application.CreateItem.assert_not_called()


# -----------------------------------------------------------------------------
@pytest.mark.parametrize("missing", ["store", "drafts", "sent"])
def test_missing_account_storage_never_falls_back_to_an_archive(
    application, missing
):
    account, drafts, sent = make_account("work@example.org", "WORK")
    application.Session.Accounts = [account]
    if missing == "store":
        account.DeliveryStore = None
    else:
        account.DeliveryStore.GetDefaultFolder.side_effect = {
            outlook.OL_FOLDER_DRAFTS: None if missing == "drafts" else drafts,
            outlook.OL_FOLDER_SENT_MAIL: None if missing == "sent" else sent,
        }.get
    with pytest.raises(ValueError, match="stockage|dossiers"):
        outlook.new_email({"from": "work@example.org"})
    drafts.Items.Add.assert_not_called()
    application.CreateItem.assert_not_called()


# -----------------------------------------------------------------------------
def test_individual_batch_pins_initial_active_account(application):
    active, drafts, _ = make_account("active@example.org", "ACTIVE")
    other, other_drafts, _ = make_account("other@example.org", "OTHER")
    application.Session.Accounts = [active, other]
    explorer = SimpleNamespace(
        CurrentFolder=SimpleNamespace(Store=active.DeliveryStore)
    )
    application.ActiveExplorer.return_value = explorer

    # -------------------------------------------------------------------------
    def move_to_other_account():
        explorer.CurrentFolder = SimpleNamespace(Store=other.DeliveryStore)

    drafts.Items.Add.return_value.Send.side_effect = move_to_other_account
    conf = {
        "really_send": True,
        "to": {
            "individual_email": True,
            "list": ["first@example.org", "second@example.org"],
        },
        "email": {"subject": "Test", "html_body": "<p>Body</p>"},
    }
    original = deepcopy(conf)
    outlook.deliver(conf)
    assert drafts.Items.Add.call_count == 2
    assert drafts.Items.Add.return_value.Send.call_count == 2
    other_drafts.Items.Add.assert_not_called()
    application.ActiveExplorer.assert_called_once()
    assert conf == original
