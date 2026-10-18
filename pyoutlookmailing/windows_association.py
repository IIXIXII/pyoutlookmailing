#!/usr/bin/env python
# -*- coding: utf-8 -*-
# =============================================================================
# Author: Florent TOURNOIS | License: MIT
# =============================================================================

"""Install a per-user Windows association for .mailmd, leaving .md untouched."""

from __future__ import annotations

import argparse
import ctypes
import os
import subprocess
import sys
from pathlib import Path, PurePath

EXTENSION = ".mailmd"
PROG_ID = "pyoutlookmailing.MailMarkdown.1"
CLASSES = r"Software\Classes"
USER_CHOICE = (
    r"Software\Microsoft\Windows\CurrentVersion"
    r"\Explorer\FileExts\.mailmd\UserChoice"
)
OWNER = "pyoutlookmailing"


# -----------------------------------------------------------------------------
def registration(
    pythonw: PurePath, editor: PurePath, launcher: PurePath | None = None
) -> dict[str, dict[str, str]]:
    """Build registry entries for the .mailmd association without writing them.

    Args:
        pythonw: Path to pythonw.exe for direct execution. With a batch
            launcher, python.exe in the same directory is used instead.
        editor: Editor executable used by the document's edit action.
        launcher: Optional .bat path; the Windows bridge passes the selected
            file as one argument while preserving spaces and shell
            metacharacters.

    Returns:
        A mapping from paths relative to HKCU/Software/Classes to dictionaries
        of registry value names and string values.

    Pure paths are accepted so commands can be inspected and tested on other
    platforms. This function neither checks file existence nor accesses the
    registry.
    """
    command = f'"{pythonw}" -I -m pyoutlookmailing --windows --conf "%1"'
    if launcher is not None:
        python = pythonw.with_name("python.exe")
        command = (
            f'"{python}" -I -m pyoutlookmailing.windows_launcher '
            f'--batch "{launcher}" "%1"'
        )
    icon = pythonw.with_name("python.exe") if launcher is not None else pythonw
    return {
        PROG_ID: {"": "Courriel Markdown (pyoutlookmailing)", "Owner": OWNER},
        PROG_ID + r"\DefaultIcon": {"": f'"{icon}",0'},
        PROG_ID + r"\shell": {"": "open"},
        PROG_ID + r"\shell\open": {"": "Exécuter le courriel avec Outlook"},
        PROG_ID + r"\shell\open\command": {"": command},
        PROG_ID + r"\shell\edit": {"": "Modifier le Markdown"},
        PROG_ID + r"\shell\edit\command": {"": f'"{editor}" "%1"'},
        EXTENSION: {"": PROG_ID},
    }


# -----------------------------------------------------------------------------
def _value(reg, root, path, name=""):
    """Read a registry value as (data, type), returning None when absent.

    The reg argument is winreg or a compatible test double. Access errors other
    than a missing key/value propagate.
    """
    try:
        with reg.OpenKey(root, path) as key:
            return reg.QueryValueEx(key, name)
    except FileNotFoundError:
        return None


# -----------------------------------------------------------------------------
def _exists(reg, root, path):
    """Return whether a registry key exists; propagate permission errors."""
    try:
        with reg.OpenKey(root, path):
            return True
    except FileNotFoundError:
        return False


# -----------------------------------------------------------------------------
def _delete_empty_key(reg, path):
    """Delete an empty HKCU key, leaving nonempty and missing keys unchanged."""
    try:
        with reg.OpenKey(reg.HKEY_CURRENT_USER, path) as key:
            subkeys, values, _ = reg.QueryInfoKey(key)
        if subkeys == values == 0:
            reg.DeleteKey(reg.HKEY_CURRENT_USER, path)
    except FileNotFoundError:
        pass


# -----------------------------------------------------------------------------
def install(reg, entries):
    """Install this application's registry entries for the current user.

    Args:
        reg: winreg or a compatible test double.
        entries: Mapping returned by registration.

    Raises:
        ValueError: The effective association or existing ProgID belongs to
            another app.
        OSError: Registry access fails. On write failure, previous values are
            restored and newly created empty keys are removed before the error
            is re-raised.

    Writes only the supplied values under HKCU/Software/Classes. The protected
    Windows UserChoice key is read for conflict detection but is never changed.
    """
    choice = _value(reg, reg.HKEY_CURRENT_USER, USER_CHOICE, "ProgId")
    association = _value(reg, reg.HKEY_CLASSES_ROOT, EXTENSION)
    if any(value and value[0] != PROG_ID for value in (choice, association)):
        raise ValueError(
            ".mailmd est déjà associé à une autre application ; "
            "association conservée"
        )
    prog_path = CLASSES + "\\" + PROG_ID
    owner = _value(reg, reg.HKEY_CURRENT_USER, prog_path, "Owner")
    if _exists(reg, reg.HKEY_CURRENT_USER, prog_path) and owner != (
        OWNER,
        reg.REG_SZ,
    ):
        raise ValueError(
            "Le ProgID .mailmd existe déjà "
            "et n’appartient pas à pyoutlookmailing"
        )
    previous = []
    created = []
    try:
        for relative, values in entries.items():
            path = CLASSES + "\\" + relative
            if not _exists(reg, reg.HKEY_CURRENT_USER, path):
                created.append(path)
            with reg.CreateKeyEx(
                reg.HKEY_CURRENT_USER, path, 0, reg.KEY_SET_VALUE
            ) as key:
                for name, value in values.items():
                    old = _value(reg, reg.HKEY_CURRENT_USER, path, name)
                    previous.append((path, name, old))
                    reg.SetValueEx(key, name, 0, reg.REG_SZ, value)
    except OSError:
        for path, name, old in reversed(previous):
            with reg.OpenKey(
                reg.HKEY_CURRENT_USER, path, 0, reg.KEY_SET_VALUE
            ) as key:
                if old is not None:
                    reg.SetValueEx(key, name, 0, old[1], old[0])
                else:
                    try:
                        reg.DeleteValue(key, name)
                    except FileNotFoundError:
                        pass
        for path in reversed(created):
            _delete_empty_key(reg, path)
        raise


# -----------------------------------------------------------------------------
def uninstall(reg, entries):
    """Remove this application's association values while preserving foreign
    data.

    The reg argument is winreg or a test double; entries comes from
    registration. Removal requires the application's owner marker. A changed
    extension association, unrelated values, and nonempty keys are retained.
    Missing keys are tolerated. No document files are deleted; registry access
    errors otherwise propagate.
    """
    prog_path = CLASSES + "\\" + PROG_ID
    if _value(reg, reg.HKEY_CURRENT_USER, prog_path, "Owner") != (
        OWNER,
        reg.REG_SZ,
    ):
        return
    for relative, values in reversed(entries.items()):
        path = CLASSES + "\\" + relative
        if relative == EXTENSION and _value(
            reg, reg.HKEY_CURRENT_USER, path
        ) != (
            PROG_ID,
            reg.REG_SZ,
        ):
            continue
        try:
            with reg.OpenKey(
                reg.HKEY_CURRENT_USER, path, 0, reg.KEY_SET_VALUE
            ) as key:
                for name in values:
                    try:
                        reg.DeleteValue(key, name)
                    except FileNotFoundError:
                        pass
        except FileNotFoundError:
            pass
        _delete_empty_key(reg, path)


# -----------------------------------------------------------------------------
def _notify_shell():
    """Notify Explorer of association changes; do nothing outside Windows."""
    # SHCNE_ASSOCCHANGED / SHCNF_IDLIST, documented by Microsoft.
    if sys.platform == "win32":
        ctypes.windll.shell32.SHChangeNotify(0x08000000, 0, None, None)


# -----------------------------------------------------------------------------
def main(argv=None) -> int:
    """Install, remove, or print the per-user .mailmd registry association.

    argv is an argument list or None for sys.argv. Return 0 on success and 1 for
    handled installation errors; argparse may raise SystemExit. --dry-run prints
    the planned entries without changing the registry. Windows is required even
    for a dry run; use registration directly for platform-independent
    inspection.
    """
    parser = argparse.ArgumentParser(
        description="Associate .mailmd files with pyoutlookmailing on Windows"
    )
    parser.add_argument(
        "action", choices=("install", "uninstall"), nargs="?", default="install"
    )
    parser.add_argument(
        "--launcher",
        type=Path,
        help="Batch file that receives the .mailmd path",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show entries without changing the registry",
    )
    args = parser.parse_args(argv)
    try:
        if sys.platform != "win32":
            raise ValueError("L’association de fichiers nécessite Windows")
        import winreg

        pythonw = Path(sys.executable).resolve().with_name("pythonw.exe")
        editor = Path(os.environ["SystemRoot"]) / "System32" / "notepad.exe"
        launcher = args.launcher.resolve() if args.launcher else None
        entries = registration(pythonw, editor, launcher)
        if args.action == "install" and launcher is not None:
            if launcher.suffix.lower() != ".bat" or not launcher.is_file():
                raise ValueError(f"Lanceur .bat introuvable : {launcher}")
        if args.dry_run:
            print(f"Action : {args.action} (simulation, registre inchangé)")
            for path, values in entries.items():
                print(f"HKCU\\{CLASSES}\\{path}: {values}")
            return 0
        if args.action == "install":
            interpreter = (
                pythonw.with_name("python.exe") if launcher else pythonw
            )
            if not interpreter.is_file():
                raise ValueError(f"Interpréteur introuvable : {interpreter}")
            # The Explorer working directory is arbitrary. Verify the installed
            # package.
            subprocess.run(
                [sys.executable, "-I", "-m", "pyoutlookmailing", "--version"],
                check=True,
                capture_output=True,
                text=True,
            )
            install(winreg, entries)
            print("Association .mailmd installée pour votre compte Windows.")
            if launcher:
                print(f"Lanceur : {launcher}")
            print(
                "Double-clic : really_send=true envoie ; "
                "false ou absent crée un brouillon."
            )
        else:
            uninstall(winreg, entries)
            print("Association .mailmd de pyoutlookmailing retirée.")
        _notify_shell()
        return 0
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
