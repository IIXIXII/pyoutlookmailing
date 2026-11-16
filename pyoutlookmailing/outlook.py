#!/usr/bin/env python
# -*- coding: utf-8 -*-
# =============================================================================
# Author: Florent TOURNOIS | License: MIT
# =============================================================================

"""Outlook COM boundary. Importing this module never starts Outlook."""

from __future__ import annotations

import logging
import re
from copy import deepcopy
from html import unescape
from mimetypes import guess_type
from urllib.parse import unquote
from uuid import uuid4

from .files import find_file

logger = logging.getLogger(__name__)
CID_PATTERN = re.compile(r"""\bsrc\s*=\s*['"]cid:([^'"]+)['"]""", re.IGNORECASE)
ATTACH_CONTENT_ID = "http://schemas.microsoft.com/mapi/proptag/0x3712001F"
ATTACH_MIME_TAG = "http://schemas.microsoft.com/mapi/proptag/0x370E001F"
ATTACH_FLAGS = "http://schemas.microsoft.com/mapi/proptag/0x37140003"
ATTACHMENT_HIDDEN = "http://schemas.microsoft.com/mapi/proptag/0x7FFE000B"
ATTACH_RENDERED_IN_BODY = 0x00000004
OL_FOLDER_DRAFTS = 16
OL_FOLDER_SENT_MAIL = 5


# -----------------------------------------------------------------------------
def _set_optional_inline_property(
    properties, schema, value, filename, unsupported
):
    """Skip only provider-denied or unsupported optional attachment metadata.

    Inspect the nested Outlook SCODE when present: the outer COM HRESULT often
    reports only DISP_E_EXCEPTION. Keep pywin32 optional for non-Windows tests.
    Recheck capabilities on the next delivery call, not for every recipient.
    """
    if schema in unsupported:
        return
    try:
        properties.SetProperty(schema, value)
    except Exception as exc:
        code = getattr(exc, "hresult", None)
        details = getattr(exc, "excepinfo", None)
        if isinstance(details, (tuple, list)) and len(details) > 5:
            if isinstance(details[5], int) and details[5]:
                code = details[5]
        # E_ACCESSDENIED / MAPI_E_NO_ACCESS and MAPI_E_NO_SUPPORT.
        if not isinstance(code, int) or code & 0xFFFFFFFF not in {
            0x80070005,
            0x80040102,
        }:
            raise
        unsupported.add(schema)
        logger.warning(
            "Outlook : propriété facultative %s non modifiable pour %s ; "
            "références Content-ID conservées",
            schema.rsplit("/", 1)[-1],
            filename.name,
        )


# -----------------------------------------------------------------------------
def _select_account(application, sender):
    """Select an explicit sender, an active folder account, or a sole account.

    Never interpret an unrelated archive store as a sending account. Ambiguous
    sessions require an explicit from address rather than guessing an account.
    """
    accounts = list(application.Session.Accounts)
    if sender:
        matches = [
            account
            for account in accounts
            if str(account.SmtpAddress).strip().casefold()
            == sender.strip().casefold()
        ]
        if len(matches) != 1:
            raise ValueError(
                "Le compte expéditeur demandé est introuvable ou ambigu "
                "dans Outlook"
            )
        return matches[0]
    explorer = application.ActiveExplorer()
    if explorer is not None and explorer.CurrentFolder is not None:
        store_id = explorer.CurrentFolder.Store.StoreID
        matches = [
            account
            for account in accounts
            if account.DeliveryStore is not None
            and account.DeliveryStore.StoreID == store_id
        ]
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            raise ValueError(
                "Plusieurs comptes Outlook utilisent le dossier actif ; "
                "renseignez from pour choisir le compte expéditeur"
            )
    if len(accounts) == 1:
        return accounts[0]
    raise ValueError(
        "Impossible d'identifier le compte Outlook actif ; "
        "renseignez from dans la configuration ou les préférences"
    )


# -----------------------------------------------------------------------------
def new_email(conf):
    """Create an unsaved message in the selected account's Drafts folder.

    Args:
        conf: Configuration whose optional from string is an account email
            address.

    Returns:
        A MailItem bound to the account and its Sent Items folder.

    Raises:
        RuntimeError: win32com cannot be imported.
        ValueError: The sender cannot be identified unambiguously or its store
            does not provide Drafts and Sent Items folders.

    Dispatch may start Outlook. The function neither saves nor sends the item.
    COM errors propagate; a requested but missing account never falls back
    silently.
    """
    try:
        import win32com.client
    except ImportError as exc:
        raise RuntimeError(
            "La livraison nécessite Windows, pywin32 et Outlook classique."
        ) from exc
    outlook = win32com.client.Dispatch("Outlook.Application")
    account = _select_account(outlook, conf.get("from"))
    store = account.DeliveryStore
    if store is None:
        raise ValueError("Le compte Outlook sélectionné n'a pas de stockage")
    drafts = store.GetDefaultFolder(OL_FOLDER_DRAFTS)
    sent = store.GetDefaultFolder(OL_FOLDER_SENT_MAIL)
    if drafts is None or sent is None:
        raise ValueError(
            "Les dossiers Brouillons et Éléments envoyés sont introuvables "
            "pour le compte Outlook sélectionné"
        )
    logger.info(
        "Compte Outlook : %s ; Brouillons : %s ; Éléments envoyés : %s",
        account.SmtpAddress,
        drafts.FolderPath,
        sent.FolderPath,
    )
    mail = drafts.Items.Add("IPM.Note")
    mail.SendUsingAccount = account
    mail.SaveSentMessageFolder = sent
    mail.DeleteAfterSubmit = False
    return mail


# -----------------------------------------------------------------------------
def deliver(conf, *, mail_factory=new_email):
    """Validate a prepared email and save or send its Outlook messages.

    Args:
        conf: Prepared configuration with subject and html_body. really_send
            must be a boolean; False or absence saves drafts.
            to.individual_email=True creates one item per To address and repeats
            Cc/Bcc on each item.
        mail_factory: Callable receiving a prepared configuration copy and
            returning an Outlook-compatible mail object. Tests inject a fake
            here.

    Returns:
        The original configuration object, unchanged.

    Raises:
        ValueError: Delivery fields are invalid or exclusions leave no
            recipients.
        FileNotFoundError: A regular attachment or referenced CID image is
            missing.

    All addresses are normalized and exclusions apply to To, Cc, and Bcc. Excel
    blacklists must already be loaded by compute_conf. Logs identify removed
    addresses and the recipients of each successfully sent or saved item. Files
    are resolved before the first factory call. CID names are deduplicated per
    item. Each item is processed sequentially; factory and COM errors propagate
    without retry or rollback of messages already saved or sent. Local CID
    filenames are replaced with globally unique ASCII Content-IDs per message.
    Inline attachments receive MIME type and rendered-in-body metadata when
    writable. Provider-denied optional flags are logged without blocking the
    required Content-ID/MIME properties; unrelated errors still propagate.
    """
    from .core import _addresses

    prepared = deepcopy(conf)
    send = prepared.get("really_send", False)
    if not isinstance(send, bool):
        raise ValueError(
            "really_send doit être un booléen YAML (true ou false)"
        )
    exclusion = prepared.get("not_to")
    if exclusion is None:
        exclusion = {}
    if not isinstance(exclusion, dict):
        raise ValueError("not_to doit être un objet YAML")
    if any(
        key in exclusion
        for key in ("excel_file", "excel_column_name", "_excel_sources")
    ):
        raise ValueError(
            "not_to : blacklist Excel non chargée ; "
            "appelez compute_conf avant l'envoi"
        )
    excluded = set(_addresses(exclusion.get("list"), "not_to"))
    recipients = {}
    removed = {}
    for field in ("to", "cc", "bcc"):
        section = prepared.get(field)
        if field == "bcc" and section is None:
            section = prepared.get("Bcc")
        if section is None:
            section = {}
        if not isinstance(section, dict):
            raise ValueError(f"{field} doit être un objet YAML")
        addresses = _addresses(section.get("list"), field)
        removed[field] = [
            address for address in addresses if address in excluded
        ]
        recipients[field] = [
            address for address in addresses if address not in excluded
        ]
    logger.info(
        "Blacklist not_to : %d adresses ; exclusions To=%d, Cc=%d, Cci=%d",
        len(excluded),
        len(removed["to"]),
        len(removed["cc"]),
        len(removed["bcc"]),
    )
    for field, addresses in removed.items():
        for address in addresses:
            logger.info("Exclu (not_to) : %s [%s]", address, field)
    if not any(recipients.values()):
        raise ValueError("Aucun destinataire après application des exclusions")
    individual = (prepared.get("to") or {}).get("individual_email", False)
    if not isinstance(individual, bool):
        raise ValueError("to.individual_email doit être un booléen")
    if individual and not recipients["to"]:
        raise ValueError(
            "Le mode individuel nécessite au moins un destinataire to"
        )
    email = prepared.get("email", {})
    for key in ("subject", "html_body"):
        if not isinstance(email.get(key), str) or not email[key].strip():
            raise ValueError(f"email.{key} est requis")
    paths = prepared.get("paths", {})
    folders = paths.get("base_search", [paths.get("conf_folder", ".")])
    cid = {
        name: find_file(
            unquote(unescape(name)),
            [paths.get("img", "."), *folders],
            ("", "img", "conf", "files"),
        )
        for name in dict.fromkeys(CID_PATTERN.findall(email["html_body"]))
    }
    names = email.get("attachments", [])
    if not isinstance(names, list) or not all(
        isinstance(name, str) for name in names
    ):
        raise ValueError("email.attachments doit être une liste de fichiers")
    attachments = [
        find_file(name, folders, ("", "conf", "files")) for name in names
    ]
    groups = (
        [[address] for address in recipients["to"]]
        if individual
        else [recipients["to"]]
    )
    unsupported_inline_properties: set[str] = set()
    for index, group in enumerate(groups, start=1):
        content_ids = {
            filename: f"image-{uuid4().hex}@pyoutlookmailing.invalid"
            for filename in dict.fromkeys(cid.values())
        }

        # ---------------------------------------------------------------------
        def replace_cid(match, content_ids=content_ids):
            """Replace only the CID value, preserving the authored attribute."""
            start = match.start(1) - match.start()
            end = match.end(1) - match.start()
            content_id = content_ids[cid[match.group(1)]]
            return match.group()[:start] + content_id + match.group()[end:]

        html_body = CID_PATTERN.sub(replace_cid, email["html_body"])
        mail = mail_factory(prepared)
        # Keep an implicit active account stable for an individual-mail batch.
        # Injected test factories need not expose Outlook account properties.
        if not prepared.get("from"):
            smtp = getattr(
                getattr(mail, "SendUsingAccount", None), "SmtpAddress", None
            )
            if isinstance(smtp, str) and smtp.strip():
                prepared["from"] = smtp.strip()
        mail.To = "; ".join(group)
        mail.Cc = "; ".join(recipients["cc"])
        mail.Bcc = "; ".join(recipients["bcc"])
        mail.Subject = email["subject"]
        for filename, content_id in content_ids.items():
            attached = mail.Attachments.Add(str(filename), 1, 0)
            properties = attached.PropertyAccessor
            properties.SetProperty(ATTACH_CONTENT_ID, content_id)
            properties.SetProperty(
                ATTACH_MIME_TAG,
                guess_type(str(filename))[0] or "application/octet-stream",
            )
            _set_optional_inline_property(
                properties,
                ATTACH_FLAGS,
                ATTACH_RENDERED_IN_BODY,
                filename,
                unsupported_inline_properties,
            )
            _set_optional_inline_property(
                properties,
                ATTACHMENT_HIDDEN,
                True,
                filename,
                unsupported_inline_properties,
            )
        for filename in attachments:
            mail.Attachments.Add(str(filename))
        # Resolve inline attachments before Outlook processes their HTML refs.
        mail.HTMLBody = html_body
        if send:
            mail.Send()
        else:
            mail.Save()
        destinations = ["; ".join(group)] if group else []
        for field, label in (("cc", "Cc"), ("bcc", "Cci")):
            if recipients[field]:
                destinations.append(f"{label} : {'; '.join(recipients[field])}")
        logger.info(
            "Message %d/%d : %s %s",
            index,
            len(groups),
            "envoyé" if send else "brouillon enregistré",
            " | ".join(destinations),
        )
    return conf
