#!/usr/bin/env python
# -*- coding: utf-8 -*-
# =============================================================================
# Author: Florent TOURNOIS | License: MIT
# =============================================================================

"""Store common user settings through Upref, separately from campaigns.

Loading never creates files or asks for input. The module command prints the
store location or explicitly imports validated preferences into that store.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path
from typing import Any

from upref import ConfigStore

PREFERENCES_ENV = "PYOUTLOOKMAILING_PREFERENCES"
COMMON_SECTIONS = {
    "from",
    "paths",
    "email",
    "not_to",
    "really_send",
    "to",
    "cc",
    "bcc",
}
CAMPAIGN_EMAIL_FIELDS = {
    "subject",
    "summary",
    "content",
    "html_body",
    "attachments",
}
SOURCE_PATH_FIELDS = {"includes", "conf_folder", "conf_filename"}
logger = logging.getLogger(__name__)


# -----------------------------------------------------------------------------
def get_preferences_store(
    filename: str | os.PathLike | None = None,
) -> ConfigStore:
    """Return the preference store without reading or creating any files.

    Args:
        filename: Explicit file, relative to the current working directory when
            needed. Otherwise use the absolute PYOUTLOOKMAILING_PREFERENCES file
            or Upref's platform user directory with filename preferences.yaml.

    Returns:
        A fresh ConfigStore for this application, without an optional GUI.

    Raises:
        ValueError: The environment override is not an absolute filename.
        upref.ConfigPathError: Upref cannot resolve the store location.
    """
    if filename is None:
        override = os.environ.get(PREFERENCES_ENV)
        if override is not None:
            if not override or not Path(override).expanduser().is_absolute():
                raise ValueError(
                    f"{PREFERENCES_ENV} doit être un chemin absolu de fichier"
                )
            filename = override
    if filename is None:
        return ConfigStore("pyoutlookmailing", filename="preferences.yaml")
    location = Path(filename).expanduser().resolve()
    return ConfigStore(
        "pyoutlookmailing", filename=location.name, directory=location.parent
    )


# -----------------------------------------------------------------------------
def _validate_common(data: Any, context: str) -> None:
    """Validate the allowed common fields without rendering or delivery."""
    if not isinstance(data, dict):
        raise ValueError(f"{context} doit être un objet de configuration")
    unexpected = set(data) - COMMON_SECTIONS
    if unexpected:
        fields = ", ".join(sorted(unexpected))
        raise ValueError(
            f"{context} : champs réservés à la campagne ou inconnus : {fields}"
        )
    if "from" in data and (
        not isinstance(data["from"], str) or not data["from"].strip()
    ):
        raise ValueError(f"{context}.from doit être une adresse non vide")
    if "really_send" in data and not isinstance(data["really_send"], bool):
        raise ValueError(f"{context}.really_send doit être un booléen")
    if "to" in data:
        _validate_delivery_defaults(data["to"], f"{context}.to")
    for field in ("cc", "bcc"):
        if field in data and data[field] is not None and data[field] != {}:
            raise ValueError(
                f"{context}.{field} doit être null ou un objet vide ; "
                "les destinataires appartiennent à la campagne"
            )
    if "not_to" in data:
        _validate_blacklist_defaults(data["not_to"], f"{context}.not_to")
    if "paths" in data:
        paths = data["paths"]
        if not isinstance(paths, dict):
            raise ValueError(f"{context}.paths doit être un objet")
        if SOURCE_PATH_FIELDS & paths.keys():
            raise ValueError(
                f"{context}.paths : les inclusions et métadonnées de source "
                "appartiennent à la campagne"
            )
        _validate_paths(paths, f"{context}.paths")
    if "email" in data:
        email = data["email"]
        if not isinstance(email, dict):
            raise ValueError(f"{context}.email doit être un objet")
        forbidden = CAMPAIGN_EMAIL_FIELDS & email.keys()
        if forbidden:
            fields = ", ".join(sorted(forbidden))
            raise ValueError(
                f"{context}.email : champs réservés à la campagne : {fields}"
            )
        for name in ("model", "template"):
            if name in email and (
                not isinstance(email[name], str) or not email[name].strip()
            ):
                raise ValueError(
                    f"{context}.email.{name} doit être une chaîne non vide"
                )


# -----------------------------------------------------------------------------
def _validate_delivery_defaults(data: Any, context: str) -> None:
    """Allow the individual-email default without shared delivery addresses."""
    if data is None:
        return
    if not isinstance(data, dict):
        raise ValueError(f"{context} doit être un objet ou null")
    unexpected = set(data) - {"individual_email"}
    if unexpected:
        raise ValueError(
            f"{context} : seul individual_email peut être partagé ; "
            "les destinataires appartiennent à la campagne"
        )
    if "individual_email" in data and not isinstance(
        data["individual_email"], bool
    ):
        raise ValueError(f"{context}.individual_email doit être un booléen")


# -----------------------------------------------------------------------------
def _validate_blacklist_defaults(data: Any, context: str) -> None:
    """Validate shared exclusions; preferences cannot add delivery targets."""
    if data is None:
        return
    if not isinstance(data, dict):
        raise ValueError(f"{context} doit être un objet ou null")
    allowed = {"list", "excel_file", "excel_column_name"}
    unexpected = set(data) - allowed
    if unexpected:
        raise ValueError(
            f"{context} : champs inconnus : {', '.join(sorted(unexpected))}"
        )
    if "list" in data and (
        not isinstance(data["list"], list)
        or not all(isinstance(value, str) for value in data["list"])
    ):
        raise ValueError(f"{context}.list doit être une liste d'adresses")
    if "excel_file" in data and (
        not isinstance(data["excel_file"], str)
        or not data["excel_file"].strip()
    ):
        raise ValueError(f"{context}.excel_file doit être un chemin non vide")
    if "excel_column_name" in data:
        columns = data["excel_column_name"]
        if isinstance(columns, str):
            columns = [columns]
        if (
            not isinstance(columns, list)
            or not columns
            or not all(
                isinstance(column, str) and column.strip() for column in columns
            )
        ):
            raise ValueError(
                f"{context}.excel_column_name doit désigner des colonnes"
            )


# -----------------------------------------------------------------------------
def _validate_paths(paths: dict, context: str) -> None:
    """Check paths before an explicit import can write invalid preferences."""
    for name, value in paths.items():
        if name == "root":
            if not isinstance(value, str):
                raise ValueError(f"{context}.root doit être un chemin")
        elif isinstance(value, dict):
            _validate_paths(value, f"{context}.{name}")
        elif isinstance(value, list):
            if not all(isinstance(item, str) for item in value):
                raise ValueError(
                    f"{context}.{name} doit être une liste de chemins"
                )
        elif not isinstance(value, str):
            raise ValueError(f"{context}.{name} doit être un chemin")


# -----------------------------------------------------------------------------
def validate_preferences(data: dict[str, Any]) -> None:
    """Validate global settings and every named profile in a loaded mapping.

    Sender, paths, presentation, exclusions, really_send and individual_email
    defaults may be shared. Delivery addresses, content and attachments stay
    in the campaign; Cc/Bcc defaults can only be empty. The optional profiles
    mapping contains common-setting overrides. Upref separately checks
    serializable types and string keys.

    Raises:
        ValueError: A common setting or profile has an invalid shape or field.
    """
    _validate_common(
        {key: value for key, value in data.items() if key != "profiles"},
        "Préférences upref",
    )
    profiles = data.get("profiles", {})
    if not isinstance(profiles, dict):
        raise ValueError("Préférences upref.profiles doit être un objet")
    for name, profile in profiles.items():
        if (
            not isinstance(name, str)
            or not name.strip()
            or name != name.strip()
        ):
            raise ValueError("Les noms de profils upref doivent être non vides")
        _validate_common(profile, f"Profil upref {name!r}")


# -----------------------------------------------------------------------------
def read_preferences(
    filename: str | os.PathLike | None = None,
) -> tuple[ConfigStore, dict[str, Any]]:
    """Load and validate a fresh preference tree without writing or prompting.

    Log the resolved filename before reading, even for missing, empty, or
    invalid settings. This makes the editable location visible in batch logs.

    Returns:
        The resolved store and its detached preferences. A missing or empty
        file returns an empty dictionary. The profile is selected by core.

    Raises:
        ValueError: Application preferences contain invalid or campaign fields.
        upref.UprefError: Storage path, YAML data, or file access is invalid.
    """
    store = get_preferences_store(filename)
    logger.info("Fichier upref (valeurs par défaut) : %s", store.path)
    data = store.load()
    validate_preferences(data)
    if not data:
        status = "vide" if store.exists() else "absent"
        logger.info(
            "Fichier upref %s : aucune préférence commune appliquée", status
        )
    return store, data


# -----------------------------------------------------------------------------
def main(argv: list[str] | None = None) -> int:
    """Print the store path or explicitly import preferences atomically.

    --import accepts a YAML preference document. Existing preferences are kept
    unless --replace is explicitly supplied. Imports never open Outlook.
    Relative resource paths retain the import file's origin by conversion to
    absolute paths before saving. An explicit --preferences selects a portable
    destination; otherwise the environment or platform user store is used.

    Returns:
        0 on success, 1 on storage or validation errors. Argument errors use
        argparse's SystemExit with code 2.
    """
    parser = argparse.ArgumentParser(description="Manage common Upref settings")
    actions = parser.add_mutually_exclusive_group()
    actions.add_argument(
        "--path",
        action="store_true",
        help="Print the preference file location (default)",
    )
    actions.add_argument(
        "--import",
        dest="source",
        type=Path,
        metavar="YAML",
        help="Import a validated common configuration",
    )
    parser.add_argument(
        "--preferences",
        type=Path,
        metavar="YAML",
        help="Use this preference file as the destination",
    )
    parser.add_argument(
        "--replace",
        action="store_true",
        help="Permit replacement of existing preferences",
    )
    args = parser.parse_args(argv)
    if args.replace and args.source is None:
        parser.error("--replace nécessite --import")
    try:
        store = get_preferences_store(args.preferences)
        if args.source is None:
            print(store.path)
            return 0
        source = args.source.expanduser().resolve()
        if not source.is_file():
            raise FileNotFoundError(
                f"Préférences à importer absentes : {source}"
            )
        if source == store.path:
            raise ValueError(
                "La source et la destination doivent être distinctes"
            )
        _, data = read_preferences(source)
        # Import core only for path expansion, after validating the document.
        from .core import expand_preferences_paths

        data = expand_preferences_paths(data, source.parent)
        if store.exists() and not args.replace:
            raise FileExistsError(
                f"Préférences existantes : {store.path}. "
                "Utilisez --replace pour les remplacer explicitement."
            )
        store.save(data)
        print(f"Préférences enregistrées : {store.path}")
        return 0
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
