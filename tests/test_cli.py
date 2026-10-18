#!/usr/bin/env python
# -*- coding: utf-8 -*-
# =============================================================================
# Author: Florent TOURNOIS | License: MIT
# =============================================================================

from unittest.mock import Mock

import pytest

from pyoutlookmailing import cli, core


# -----------------------------------------------------------------------------
@pytest.fixture
def config(tmp_path):
    filename = tmp_path / "mail.conf"
    filename.write_text(
        "really_send: true\nto:\n  list: [test@example.org]\n"
        'email:\n  subject: Test\n  content:\n    txt: "**Hello**"',
        encoding="utf-8",
    )
    return filename


# -----------------------------------------------------------------------------
def test_preview_writes_html_and_never_uses_outlook(
    config, tmp_path, monkeypatch
):
    delivery = Mock(side_effect=AssertionError("must not deliver"))
    monkeypatch.setattr(cli, "send_email", delivery)
    preview = tmp_path / "preview.html"
    assert cli.main(["--conf", str(config), "--preview", str(preview)]) == 0
    assert "<strong>Hello</strong>" in preview.read_text(encoding="utf-8")
    delivery.assert_not_called()


# -----------------------------------------------------------------------------
@pytest.mark.parametrize("configured_send", [True, False, None])
@pytest.mark.parametrize("mode", [None, "conf", "yes", "no"])
def test_cli_delivery_respects_config_and_explicit_override(
    config, monkeypatch, configured_send, mode
):
    text = config.read_text(encoding="utf-8")
    setting = (
        ""
        if configured_send is None
        else f"really_send: {str(configured_send).lower()}\n"
    )
    config.write_text(
        text.replace("really_send: true\n", setting), encoding="utf-8"
    )
    factory = Mock()
    monkeypatch.setattr(core, "new_email", factory)
    arguments = ["--conf", str(config)]
    if mode is not None:
        arguments.extend(["--send-mail", mode])

    assert cli.main(arguments) == 0
    factory.assert_called_once()
    should_send = mode == "yes" or (
        mode in (None, "conf") and configured_send is True
    )
    mail = factory.return_value
    if should_send:
        mail.Send.assert_called_once()
        mail.Save.assert_not_called()
    else:
        mail.Save.assert_called_once()
        mail.Send.assert_not_called()


# -----------------------------------------------------------------------------
def test_missing_file_returns_error(tmp_path):
    assert cli.main(["--conf", str(tmp_path / "missing.conf")]) == 1


# -----------------------------------------------------------------------------
def test_delivery_error_returns_error(config, monkeypatch):
    monkeypatch.setattr(
        cli, "send_email", Mock(side_effect=RuntimeError("COM unavailable"))
    )
    assert cli.main(["--conf", str(config)]) == 1


# -----------------------------------------------------------------------------
def test_argument_errors_keep_nonzero_exit():
    with pytest.raises(SystemExit) as error:
        cli.main([])
    assert error.value.code == 2


# -----------------------------------------------------------------------------
def test_preview_cannot_overwrite_markdown(config):
    assert (
        cli.main(
            ["--conf", str(config), "--preview", str(config.with_suffix(".md"))]
        )
        == 1
    )


# -----------------------------------------------------------------------------
def test_preview_and_send_are_incompatible(config, tmp_path):
    with pytest.raises(SystemExit) as error:
        cli.main(
            [
                "--conf",
                str(config),
                "--preview",
                str(tmp_path / "x.html"),
                "--send-mail",
                "yes",
            ]
        )
    assert error.value.code == 2
