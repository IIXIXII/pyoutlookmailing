#!/usr/bin/env python
# -*- coding: utf-8 -*-
# =============================================================================
# Author: Florent TOURNOIS | License: MIT
# =============================================================================

"""Command-line interface with explicit preview, draft and send modes."""

from __future__ import annotations

import argparse
import ctypes
import logging
import sys
from pathlib import Path

from . import __version__, compute_conf, load_conf, send_email

logger = logging.getLogger(__name__)


# -----------------------------------------------------------------------------
def get_parser_for_command_line() -> argparse.ArgumentParser:
    """Build the CLI parser for configuration, preview, and delivery options.

    The required --conf source is converted to Path. --send-mail defaults to
    conf, so a normal invocation respects really_send from the selected
    configuration.
    """
    parser = argparse.ArgumentParser(
        description="Prepare a Markdown email for Outlook"
    )
    parser.add_argument("--version", action="version", version=__version__)
    parser.add_argument(
        "--conf",
        dest="conf_filename",
        required=True,
        type=Path,
        help=(
            "YAML configuration or .md/.mailmd file "
            "with leading var(conf/...) comments"
        ),
    )
    parser.add_argument(
        "--profile",
        help="Common upref profile overriding conf/profile",
    )
    preferences = parser.add_mutually_exclusive_group()
    preferences.add_argument(
        "--preferences",
        type=Path,
        metavar="YAML",
        help="Use this upref preferences file instead of the user store",
    )
    preferences.add_argument(
        "--no-preferences",
        action="store_true",
        help="Ignore common preferences and the campaign's profile",
    )
    parser.add_argument(
        "--send-mail",
        choices=["yes", "no", "conf"],
        default="conf",
        help=(
            "conf: use really_send (default); "
            "no: save drafts; yes: send messages"
        ),
    )
    parser.add_argument(
        "--preview",
        type=Path,
        metavar="HTML",
        help="Write an HTML preview without opening Outlook",
    )
    parser.add_argument(
        "--windows",
        action="store_true",
        help="Also show errors in a Windows message box",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable debug logs and error tracebacks",
    )
    return parser


# -----------------------------------------------------------------------------
def main(argv: list[str] | None = None) -> int:
    """Run a preview or delivery command and return its process exit status.

    Args:
        argv: Argument strings without the executable name, or None for
            sys.argv.

    Returns:
        0 on success, or 1 when configuration, rendering, or delivery fails.

    Raises:
        SystemExit: argparse handles --help/--version (0) and invalid arguments
            (2).

    Preview writes UTF-8 HTML and avoids Outlook entirely. Other invocations may
    save or send through Outlook. --windows also shows processing errors in a
    Windows message box; --verbose includes a traceback in the log.
    """
    parser = get_parser_for_command_line()
    args = parser.parse_args(argv)
    if args.preview and args.send_mail == "yes":
        parser.error("--preview et --send-mail yes sont incompatibles")
    if args.no_preferences and args.profile is not None:
        parser.error("--no-preferences et --profile sont incompatibles")
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s: %(message)s",
    )
    try:
        conf = compute_conf(
            load_conf(
                args.conf_filename,
                preferences=args.preferences,
                use_preferences=not args.no_preferences,
                profile=args.profile,
            ),
            args,
        )
        if args.preview:
            destination = args.preview.resolve()
            source = args.conf_filename.resolve()
            if destination.suffix.lower() not in {".html", ".htm"}:
                raise ValueError(
                    "Le fichier d’aperçu doit avoir une extension .html ou .htm"
                )
            if destination in {source, source.with_suffix(".md")}:
                raise ValueError("L’aperçu ne peut pas écraser la source")
            destination.write_text(conf["email"]["html_body"], encoding="utf-8")
            logger.info("Aperçu : %s", destination)
        else:
            send_email(conf)
        return 0
    except Exception as exc:  # pylint: disable=broad-exception-caught
        # The CLI must report third-party failures and return a failure status.
        logger.error("%s", exc, exc_info=args.verbose)
        if args.windows and sys.platform == "win32":
            ctypes.windll.user32.MessageBoxW(0, str(exc), "pyoutlookmailing", 0)
        return 1
