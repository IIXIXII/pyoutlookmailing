#!/usr/bin/env python
# -*- coding: utf-8 -*-
# =============================================================================
# Author: Florent TOURNOIS | License: MIT
# =============================================================================

import ctypes
import json
import os
import subprocess
import sys
from contextlib import contextmanager
from copy import deepcopy
from pathlib import Path, PureWindowsPath
from unittest.mock import Mock

import pytest

from pyoutlookmailing import cli, core, windows_launcher
from pyoutlookmailing import windows_association as association

ROOT = Path(__file__).resolve().parents[1]


class MemoryRegistry:
    """An isolated registry; ordinary tests must not change Windows settings."""

    HKEY_CURRENT_USER = "HKCU"
    HKEY_CLASSES_ROOT = "HKCR"
    REG_SZ = 1
    KEY_SET_VALUE = 2

    # --------------------------------------------------------------------------
    def __init__(self):
        self.data = {
            ("HKCU", "Software"): {},
            ("HKCU", association.CLASSES): {},
        }
        self.fail_on: str | None = None

    # --------------------------------------------------------------------------
    @contextmanager
    def OpenKey(self, root, path, *args):
        key = (root, path)
        if root == self.HKEY_CLASSES_ROOT:
            user_key = (
                self.HKEY_CURRENT_USER,
                association.CLASSES + "\\" + path,
            )
            if user_key in self.data:
                key = user_key
        if key not in self.data:
            raise FileNotFoundError(path)
        yield key

    # --------------------------------------------------------------------------
    @contextmanager
    def CreateKeyEx(self, root, path, *args):
        parts = path.split("\\")
        for size in range(1, len(parts) + 1):
            self.data.setdefault((root, "\\".join(parts[:size])), {})
        yield root, path

    # --------------------------------------------------------------------------
    def QueryValueEx(self, key, name):
        try:
            return self.data[key][name]
        except KeyError as exc:
            raise FileNotFoundError(name) from exc

    # --------------------------------------------------------------------------
    def SetValueEx(self, key, name, reserved, kind, value):
        if key[1] == self.fail_on:
            self.fail_on = None
            raise PermissionError("Simulated write failure")
        self.data[key][name] = (value, kind)

    # --------------------------------------------------------------------------
    def DeleteValue(self, key, name):
        try:
            del self.data[key][name]
        except KeyError as exc:
            raise FileNotFoundError(name) from exc

    # --------------------------------------------------------------------------
    def QueryInfoKey(self, key):
        children = sum(
            root == key[0] and path.startswith(key[1] + "\\")
            for root, path in self.data
        )
        return children, len(self.data[key]), 0

    # --------------------------------------------------------------------------
    def DeleteKey(self, root, path):
        key = (root, path)
        if any(self.QueryInfoKey(key)[:2]):
            raise OSError("Key is not empty")
        del self.data[key]


# -----------------------------------------------------------------------------
@pytest.fixture
def entries():
    return association.registration(
        PureWindowsPath("C:/Python with spaces/pythonw.exe"),
        PureWindowsPath("C:/Windows/System32/notepad.exe"),
    )


# -----------------------------------------------------------------------------
def test_install_and_uninstall_preserve_markdown_and_other_values(entries):
    registry = MemoryRegistry()
    registry.data[("HKCU", association.CLASSES + r"\.md")] = {
        "": ("Editor.Markdown", 1)
    }
    registry.data[("HKCU", association.CLASSES + r"\.mailmd")] = {
        "Custom": ("retain", 1)
    }
    original = deepcopy(registry.data)
    association.install(registry, entries)
    association.install(registry, entries)
    assert registry.data[("HKCU", association.CLASSES + r"\.mailmd")][""] == (
        association.PROG_ID,
        1,
    )
    association.uninstall(registry, entries)
    association.uninstall(registry, entries)
    assert registry.data == original


# -----------------------------------------------------------------------------
@pytest.mark.parametrize("location", ["extension", "user_choice", "prog_id"])
def test_install_refuses_foreign_associations_without_writes(entries, location):
    registry = MemoryRegistry()
    if location == "extension":
        registry.data[("HKCR", ".mailmd")] = {"": ("Other.Application", 1)}
    elif location == "user_choice":
        registry.data[("HKCU", association.USER_CHOICE)] = {
            "ProgId": ("Other.Application", 1)
        }
    else:
        registry.data[
            ("HKCU", association.CLASSES + "\\" + association.PROG_ID)
        ] = {"Owner": ("another application", 1)}
    original = deepcopy(registry.data)
    with pytest.raises(ValueError):
        association.install(registry, entries)
    assert registry.data == original


# -----------------------------------------------------------------------------
@pytest.mark.parametrize("reinstall", [False, True])
def test_failed_install_restores_registry(entries, reinstall):
    registry = MemoryRegistry()
    if reinstall:
        previous = association.registration(
            PureWindowsPath("D:/Old Python/pythonw.exe"),
            PureWindowsPath("C:/Windows/notepad.exe"),
        )
        association.install(registry, previous)
    original = deepcopy(registry.data)
    registry.fail_on = association.CLASSES + r"\.mailmd"
    with pytest.raises(PermissionError):
        association.install(registry, entries)
    assert registry.data == original


# -----------------------------------------------------------------------------
def test_uninstall_preserves_later_changes_by_other_apps(entries):
    registry = MemoryRegistry()
    association.install(registry, entries)
    extension = ("HKCU", association.CLASSES + r"\.mailmd")
    registry.data[extension][""] = ("Another.Editor", 1)
    icon = (
        "HKCU",
        association.CLASSES + "\\" + association.PROG_ID + r"\DefaultIcon",
    )
    registry.data[icon]["Custom"] = ("Keep", 1)
    association.uninstall(registry, entries)
    assert registry.data[extension][""] == ("Another.Editor", 1)
    assert registry.data[icon] == {"Custom": ("Keep", 1)}


# -----------------------------------------------------------------------------
def test_install_batch_replaces_previous_direct_association_and_can_be_removed(
    entries,
):
    registry = MemoryRegistry()
    original = deepcopy(registry.data)
    association.install(registry, entries)
    replacement = association.registration(
        PureWindowsPath("D:/Other PC/.venv/Scripts/pythonw.exe"),
        PureWindowsPath("C:/Windows/notepad.exe"),
        PureWindowsPath("D:/Other PC/scripts/run_mailmd.bat"),
    )
    association.install(registry, replacement)
    command_key = (
        "HKCU",
        association.CLASSES
        + "\\"
        + association.PROG_ID
        + r"\shell\open\command",
    )
    command = registry.data[command_key][""][0]
    assert "windows_launcher" in command
    assert "D:\\Other PC\\scripts\\run_mailmd.bat" in command
    association.uninstall(registry, replacement)
    assert registry.data == original


# -----------------------------------------------------------------------------
def windows_arguments(command: str) -> list[str]:
    if sys.platform != "win32":
        pytest.skip("Windows command line parsing")
    parse = ctypes.windll.shell32.CommandLineToArgvW
    parse.argtypes = [ctypes.c_wchar_p, ctypes.POINTER(ctypes.c_int)]
    parse.restype = ctypes.POINTER(ctypes.c_wchar_p)
    count = ctypes.c_int()
    arguments = parse(command, ctypes.byref(count))
    try:
        return [arguments[i] for i in range(count.value)]
    finally:
        free = ctypes.windll.kernel32.LocalFree
        free.argtypes = [ctypes.c_void_p]
        free.restype = ctypes.c_void_p
        free(arguments)


# -----------------------------------------------------------------------------
@pytest.mark.skipif(
    sys.platform != "win32", reason="Windows command line parsing"
)
def test_open_command_preserves_filename_and_respects_configuration(
    entries,
):
    filename = r"C:\Mes courriels\Invitation été & 100% !.mailmd"
    command = entries[association.PROG_ID + r"\shell\open\command"][""].replace(
        "%1", filename
    )
    assert windows_arguments(command) == [
        r"C:\Python with spaces\pythonw.exe",
        "-I",
        "-m",
        "pyoutlookmailing",
        "--windows",
        "--conf",
        filename,
    ]


# -----------------------------------------------------------------------------
@pytest.mark.parametrize("send", [True, False])
def test_mailmd_delivery_respects_really_send(tmp_path, monkeypatch, send):
    filename = tmp_path / "invitation.mailmd"
    filename.write_text(
        f"<!-- var(conf/really_send) = {str(send).lower()} -->\n"
        '<!-- var(conf/to/list) = "test@example.org" -->\n'
        '<!-- var(subject) = "Test" -->\n\nBonjour.',
        encoding="utf-8",
    )
    factory = Mock()
    monkeypatch.setattr(core, "new_email", factory)
    assert cli.main(["--windows", "--conf", str(filename)]) == 0
    assert factory.return_value.Send.call_count == int(send)
    assert factory.return_value.Save.call_count == int(not send)


# -----------------------------------------------------------------------------
@pytest.mark.skipif(sys.platform != "win32", reason="Windows GUI interpreter")
def test_pythonw_association_command_can_render_from_another_directory(
    tmp_path,
):
    pythonw = Path(sys.executable).with_name("pythonw.exe")
    if not pythonw.exists():
        pytest.skip("pythonw.exe unavailable in this Python installation")
    filename = tmp_path / "Invitation été & 100% !.mailmd"
    filename.write_text(
        "<!-- var(conf/really_send) = true -->\n"
        '<!-- var(subject) = "Test" -->\n\nBonjour **à tous**.',
        encoding="utf-8",
    )
    entries = association.registration(
        pythonw, Path(os.environ["SystemRoot"]) / "notepad.exe"
    )
    command = entries[association.PROG_ID + r"\shell\open\command"][""].replace(
        "%1", str(filename)
    )
    destination = tmp_path / "preview.html"
    # --preview deliberately prevents any Outlook access in this separate
    # process.
    arguments = windows_arguments(command)
    arguments.remove(
        "--windows"
    )  # Avoid interactive error dialogs in automated tests.
    subprocess.run(
        [*arguments, "--preview", str(destination)],
        cwd=tmp_path,
        check=True,
        timeout=30,
    )
    assert "<strong>à tous</strong>" in destination.read_text(encoding="utf-8")


# -----------------------------------------------------------------------------
@pytest.mark.skipif(sys.platform != "win32", reason="Windows batch execution")
@pytest.mark.parametrize("exit_code", [0, 7])
def test_association_preserves_batch_filename_and_exit_code(
    tmp_path, exit_code
):
    folder = tmp_path / "Other project été & %MAILMD_TEST% !"
    folder.mkdir()
    batch = folder / "run_mailmd.bat"
    batch.write_text(
        "@ECHO OFF\nSETLOCAL DisableDelayedExpansion\n"
        '"%PYOUTLOOKMAILING_PYTHON%" "%~dp0probe.py" "%~1"\n'
        "EXIT /B %ERRORLEVEL%\n",
        encoding="ascii",
    )
    (folder / "probe.py").write_text(
        'import json, sys\nprint("PROBE:" + json.dumps(sys.argv[1:]))\n'
        f"sys.exit({exit_code})\n",
        encoding="ascii",
    )
    source = folder / "Invitation été (EBW) & %MAILMD_TEST% !.mailmd"
    source.write_text("Only an argument probe, no email", encoding="ascii")
    entries = association.registration(
        Path(sys.executable).with_name("pythonw.exe"),
        Path("notepad.exe"),
        batch,
    )
    command = entries[association.PROG_ID + r"\shell\open\command"][""].replace(
        "%1", str(source)
    )
    result = subprocess.run(
        windows_arguments(command),
        cwd=tmp_path,
        env={**os.environ, "MAILMD_TEST": "must-not-expand"},
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=20,
    )
    assert result.returncode == exit_code, result.stdout + result.stderr
    line = next(
        line for line in result.stdout.splitlines() if line.startswith("PROBE:")
    )
    assert json.loads(line.removeprefix("PROBE:")) == [str(source)]


# -----------------------------------------------------------------------------
def run_project_batch(script, arguments, cwd, *, answers="N\n"):
    filename = ROOT / "scripts" / script
    if not filename.is_file():
        pytest.skip("Batch scripts unavailable in this distribution")
    command_processor = str(
        Path(os.environ["SystemRoot"]) / "System32" / "cmd.exe"
    )
    command = (
        f'"{command_processor}" /d /v:off /s /c ""{filename}" {arguments}"'
    )
    return subprocess.run(
        command,
        executable=command_processor,
        cwd=cwd,
        env={**os.environ, "PYOUTLOOKMAILING_PYTHON": sys.executable},
        input=answers,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=20,
    )


# -----------------------------------------------------------------------------
@pytest.mark.skipif(sys.platform != "win32", reason="Windows installer batch")
@pytest.mark.parametrize("action", ["install", "uninstall"])
def test_separate_install_and_uninstall_scripts_in_dry_run(tmp_path, action):
    result = run_project_batch(f"{action}_mailmd.bat", "--dry-run", tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr
    assert f"Action : {action}" in result.stdout
    assert "windows_launcher" in result.stdout
    assert "run_mailmd.bat" in result.stdout


# -----------------------------------------------------------------------------
@pytest.mark.skipif(sys.platform != "win32", reason="Windows batch launcher")
def test_run_mailmd_batch_renders_selected_file_without_using_outlook(tmp_path):
    source = tmp_path / "Invitation été & EBW.mailmd"
    source.write_text(
        "<!-- var(conf/really_send) = true -->\n"
        '<!-- var(subject) = "Invitation" -->\n\nBonjour **à tous**.',
        encoding="utf-8",
    )
    source.with_suffix(".conf").write_text(
        "This configuration must not be loaded", encoding="utf-8"
    )
    destination = tmp_path / "apercu été.html"
    # No recipients: a dropped --preview would fail before any COM access.
    result = run_project_batch(
        "run_mailmd.bat", f'"{source}" --preview "{destination}"', tmp_path
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "<strong>à tous</strong>" in destination.read_text(encoding="utf-8")


# -----------------------------------------------------------------------------
@pytest.mark.skipif(sys.platform != "win32", reason="Windows batch launcher")
def test_mailmd_console_applies_user_profile_on_each_run(tmp_path):
    from pyoutlookmailing.preferences import get_preferences_store

    template_dir = tmp_path / "templates"
    template_dir.mkdir()
    (template_dir / "shared.html").write_text(
        "<main>{{ content }}</main><footer>{{ branding }}</footer>",
        encoding="utf-8",
    )
    store = get_preferences_store()
    store.save(
        {
            "paths": {"template": "templates"},
            "profiles": {
                "ebw": {
                    "email": {
                        "template": "shared.html",
                        "branding": "Shared EBW profile",
                    }
                }
            },
        }
    )
    source = tmp_path / "Invitation été & EBW.mailmd"
    source.write_text(
        '<!-- var(conf/profile) = "ebw" -->\n'
        "<!-- var(conf/really_send) = true -->\n"
        '<!-- var(subject) = "Invitation" -->\n\nBonjour.',
        encoding="utf-8",
    )
    destination = tmp_path / "preview.html"
    # A missing preview flag would fail on absent recipients before COM access.
    result = run_project_batch(
        "run_mailmd.bat",
        f'"{source}" --preview "{destination}"',
        tmp_path,
        answers="ON",
    )
    assert result.returncode == 0, result.stdout + result.stderr
    html = destination.read_text(encoding="utf-8")
    assert "Bonjour." in html
    assert "<footer>Shared EBW profile</footer>" in html
    assert result.stderr.count(str(store.path)) == 2


# -----------------------------------------------------------------------------
@pytest.mark.skipif(
    sys.platform != "win32", reason="Windows interactive batch launcher"
)
@pytest.mark.parametrize(
    ("answers", "runs"), [("N", 1), ("ON", 2), ("OON", 3), ("", 1)]
)
@pytest.mark.parametrize("valid", [True, False])
def test_mailmd_console_retries_preserve_options_and_status(
    tmp_path, answers, runs, valid
):
    source = tmp_path / "Invitation été & EBW.mailmd"
    source.write_text(
        "<!-- var(conf/really_send) = true -->\n"
        f'<!-- var(subject) = "{"Invitation" if valid else ""}" -->\n\n'
        "Bonjour.",
        encoding="utf-8",
    )
    destination = tmp_path / "preview.html"
    # No recipients, and --preview on every iteration: never access a real
    # Outlook session.
    result = run_project_batch(
        "run_mailmd.bat",
        f'"{source}" --preview "{destination}"',
        tmp_path,
        answers=answers,
    )
    assert result.returncode == (0 if valid else 1), (
        result.stdout + result.stderr
    )
    assert (
        result.stdout.count("PYOUTLOOKMAILING - traitement du courriel") == runs
    )
    assert (
        result.stdout.count("Relancer le traitement du meme fichier ?") == runs
    )
    assert (
        result.stdout.count(f'--conf "{source}" --preview "{destination}"')
        == runs
    )
    if valid:
        assert result.stdout.count("Traitement termine.") == runs
        assert "Bonjour." in destination.read_text(encoding="utf-8")
    else:
        assert (
            result.stdout.count("ERROR: echec du traitement, code 1.") == runs
        )
        assert not destination.exists()


# -----------------------------------------------------------------------------
@pytest.mark.skipif(sys.platform != "win32", reason="Windows batch launcher")
def test_batch_rejects_other_extensions_and_returns_error(tmp_path):
    source = tmp_path / "ordinary.md"
    source.write_text("Ordinary Markdown", encoding="utf-8")
    result = run_project_batch("run_mailmd.bat", f'"{source}"', tmp_path)
    assert result.returncode == 2
    assert "a .mailmd file is required" in result.stdout


# -----------------------------------------------------------------------------
@pytest.mark.skipif(sys.platform != "win32", reason="Windows batch launcher")
def test_bridge_rejects_missing_file_before_starting_batch(
    tmp_path, monkeypatch
):
    batch = tmp_path / "run_mailmd.bat"
    batch.write_text("@ECHO OFF", encoding="ascii")
    process = Mock()
    monkeypatch.setattr(windows_launcher.subprocess, "run", process)
    with pytest.raises(ValueError, match="mailmd introuvable"):
        windows_launcher.launch(batch, tmp_path / "missing.mailmd")
    process.assert_not_called()
