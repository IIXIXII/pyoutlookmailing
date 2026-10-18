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
from urllib.parse import unquote

from .files import find_file

logger = logging.getLogger(__name__)
CID_PATTERN = re.compile(r"""\bsrc\s*=\s*['"]cid:([^'"]+)['"]""", re.IGNORECASE)


# -----------------------------------------------------------------------------
def new_email(conf):
    """Create an unsaved Outlook mail item, optionally selecting a sender
    account.

    Args:
        conf: Configuration whose optional from string is an account email
            address.

    Returns:
        An Outlook COM MailItem with SendUsingAccount set when from is supplied.

    Raises:
        RuntimeError: win32com cannot be imported.
        ValueError: No configured account exactly matches from, ignoring case.

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
    account = None
    if conf.get("from"):
        sender = conf["from"].strip().casefold()
        for candidate in outlook.Session.Accounts:
            if str(candidate.SmtpAddress).casefold() == sender:
                account = candidate
                break
        if account is None:
            raise ValueError(
                "Le compte expéditeur demandé est introuvable dans Outlook"
            )
    mail = outlook.CreateItem(0)
    if account is not None:
        mail.SendUsingAccount = account
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

    All addresses are normalized and exclusions apply to To, Cc, and Bcc. Files
    are resolved before the first factory call. CID names are deduplicated per
    item. Each item is processed sequentially; factory and COM errors propagate
    without retry or rollback of messages already saved or sent.
    """
    from .core import _addresses

    prepared = deepcopy(conf)
    send = prepared.get("really_send", False)
    if not isinstance(send, bool):
        raise ValueError(
            "really_send doit être un booléen YAML (true ou false)"
        )
    exclusion = prepared.get("not_to") or {}
    if not isinstance(exclusion, dict):
        raise ValueError("not_to doit être un objet YAML")
    excluded = set(_addresses(exclusion.get("list"), "not_to"))
    recipients = {}
    for field in ("to", "cc", "bcc"):
        section = prepared.get(
            field, prepared.get("Bcc", {}) if field == "bcc" else {}
        )
        if section is None:
            section = {}
        if not isinstance(section, dict):
            raise ValueError(f"{field} doit être un objet YAML")
        recipients[field] = [
            address
            for address in _addresses(section.get("list"), field)
            if address not in excluded
        ]
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
    for index, group in enumerate(groups, start=1):
        mail = mail_factory(prepared)
        mail.To = "; ".join(group)
        mail.Cc = "; ".join(recipients["cc"])
        mail.Bcc = "; ".join(recipients["bcc"])
        mail.Subject = email["subject"]
        mail.HTMLBody = email["html_body"]
        for name, filename in cid.items():
            attached = mail.Attachments.Add(str(filename), 1, 0)
            attached.PropertyAccessor.SetProperty(
                "http://schemas.microsoft.com/mapi/proptag/0x3712001F", name
            )
        for filename in attachments:
            mail.Attachments.Add(str(filename))
        if send:
            mail.Send()
        else:
            mail.Save()
        logger.info(
            "Message %d/%d : %s",
            index,
            len(groups),
            "envoyé" if send else "brouillon enregistré",
        )
    return conf
