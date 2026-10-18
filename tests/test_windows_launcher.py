#!/usr/bin/env python
# -*- coding: utf-8 -*-
# =============================================================================
# Author: Florent TOURNOIS | License: MIT
# =============================================================================

"""Exercise cmd.exe argument forwarding without accessing Outlook."""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


# -----------------------------------------------------------------------------
@pytest.mark.skipif(sys.platform != "win32", reason="Windows batch launcher")
def test_launcher_preserves_spaced_paths_and_prints_complete_command(tmp_path):
    launcher = ROOT / "scripts" / "common.bat"
    if not launcher.is_file():
        pytest.skip(
            "Windows launchers are not included in the source distribution"
        )
    probe = tmp_path / "argument probe.py"
    probe.write_text(
        'import json, sys\nprint("PROBE:" + json.dumps(sys.argv[1:]))\n',
        encoding="utf-8",
    )
    config = tmp_path / "2026-09-23 - EBW invitation.conf"
    preview = tmp_path / "EBW invitation preview.html"
    env = {**os.environ, "PYTHON_READY": "1", "PYTHON": sys.executable}
    result = subprocess.run(
        [
            os.environ.get("COMSPEC", "cmd.exe"),
            "/d",
            "/c",
            str(launcher),
            ":PYTHON_FROM_MAKE",
            "python",
            str(probe),
            "--conf",
            str(config),
            "--preview",
            str(preview),
        ],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=True,
        timeout=20,
    )
    line = next(
        line for line in result.stdout.splitlines() if line.startswith("PROBE:")
    )
    assert json.loads(line.removeprefix("PROBE:")) == [
        "--conf",
        str(config),
        "--preview",
        str(preview),
    ]
    assert f'--conf "{config}" --preview "{preview}"' in result.stdout


# -----------------------------------------------------------------------------
def run_batch(filename, *arguments, env=None):
    return subprocess.run(
        [
            os.environ.get("COMSPEC", "cmd.exe"),
            "/d",
            "/c",
            "call",
            str(filename),
            *arguments,
        ],
        cwd=filename.parent,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=20,
    )


# -----------------------------------------------------------------------------
@pytest.mark.skipif(sys.platform != "win32", reason="Windows batch launcher")
@pytest.mark.parametrize("source", ["conf", "md", "missing"])
def test_campaign_launcher_selects_conf_or_markdown(tmp_path, source):
    model = ROOT / "scripts/mail_launcher_model.bat"
    if not model.is_file():
        pytest.skip(
            "Windows launchers are not included in the source distribution"
        )
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    mails = tmp_path / "mails"
    mails.mkdir()
    (scripts / "mailing.py").write_text(
        'import json, sys\nprint("PROBE:" + json.dumps(sys.argv[1:]))\n',
        encoding="utf-8",
    )
    # This isolated make.bat only runs the argument probe, never the real
    # mailer.
    (tmp_path / "make.bat").write_text(
        '@ECHO OFF\n"%PYTHON%" "%~2" %3 %4\nEXIT /B %ERRORLEVEL%\n',
        encoding="utf-8",
    )
    launcher = mails / "2026-09-23 - EBW invitation.bat"
    shutil.copyfile(model, launcher)
    if source != "missing":
        launcher.with_suffix(".md").write_text("Example", encoding="utf-8")
    if source == "conf":
        launcher.with_suffix(".conf").write_text("email: {}", encoding="utf-8")
    result = run_batch(launcher, env={**os.environ, "PYTHON": sys.executable})
    if source == "missing":
        assert result.returncode == 1
        assert "configuration source not found" in result.stdout
    else:
        assert result.returncode == 0, result.stdout + result.stderr
        line = next(
            line
            for line in result.stdout.splitlines()
            if line.startswith("PROBE:")
        )
        assert json.loads(line.removeprefix("PROBE:")) == [
            "--conf",
            str(launcher.with_suffix("." + source)),
        ]


# -----------------------------------------------------------------------------
@pytest.mark.skipif(sys.platform != "win32", reason="Windows batch generator")
def test_generator_supports_embedded_config_and_preserves_existing_launchers(
    tmp_path,
):
    generator = ROOT / "scripts/generate_launchers.bat"
    if not generator.is_file():
        pytest.skip(
            "Windows launchers are not included in the source distribution"
        )
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    mails = tmp_path / "mails"
    mails.mkdir()
    for name in ("generate_launchers.bat", "mail_launcher_model.bat"):
        shutil.copyfile(ROOT / "scripts" / name, scripts / name)
    (scripts / "common.bat").write_text(
        "@ECHO OFF\nEXIT /B 0\n", encoding="utf-8"
    )
    embedded = (
        "<!-- var(conf/really_send) = false -->\n"
        '<!-- var(conf/email/subject) = "Test" -->\nBody'
    )
    (mails / "embedded only.md").write_text(embedded, encoding="utf-8")
    (mails / "existing.md").write_text(embedded, encoding="utf-8")
    existing = mails / "existing.bat"
    existing.write_text("REM custom launcher", encoding="utf-8")
    (mails / "legacy.md").write_text("Body", encoding="utf-8")
    (mails / "legacy.conf").write_text("email: {}", encoding="utf-8")
    (mails / "notes.md").write_text("No configuration", encoding="utf-8")
    result = run_batch(scripts / "generate_launchers.bat", "--once")
    assert result.returncode == 0, result.stdout + result.stderr
    assert (mails / "embedded only.bat").is_file()
    assert (mails / "legacy.bat").is_file()
    assert not (mails / "notes.bat").exists()
    assert existing.read_text(encoding="utf-8") == "REM custom launcher"
