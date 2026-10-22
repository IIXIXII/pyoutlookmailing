#!/usr/bin/env python
# -*- coding: utf-8 -*-
# =============================================================================
# Author: Florent TOURNOIS | License: MIT
# =============================================================================

"""Exercise common preferences, campaign priorities and explicit persistence."""

import json
import logging
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import Mock

import pytest
import yaml
from upref import ConfigFormatError

from pyoutlookmailing import cli, core, preferences


# -----------------------------------------------------------------------------
@pytest.fixture
def store():
    return preferences.get_preferences_store()


# -----------------------------------------------------------------------------
@pytest.fixture
def campaign(tmp_path):
    filename = tmp_path / "campagne été.mailmd"
    filename.write_text(
        '<!-- var(subject) = "Invitation été" -->\n'
        '<!-- var(conf/to/list) = "recipient@example.org" -->\n\n'
        "Bonjour **à tous**.",
        encoding="utf-8",
    )
    return filename


# -----------------------------------------------------------------------------
def test_absent_preferences_do_not_create_directories(tmp_path, campaign):
    filename = tmp_path / "absent" / "settings.yaml"
    conf = core.load_conf(campaign, preferences=filename)
    assert conf["email"]["content"]["filename"] == str(campaign)
    assert not filename.parent.exists()
    assert core.compute_conf(conf)["really_send"] is False


# -----------------------------------------------------------------------------
def test_common_sender_template_and_paths_render_from_any_directory(
    tmp_path, campaign, store, monkeypatch
):
    resources = tmp_path / "resources"
    resources.mkdir()
    (resources / "custom.html").write_text(
        "<title>{{ subject }}</title><main>{{ content }}</main>",
        encoding="utf-8",
    )
    store.save(
        {
            "from": "sender@example.org",
            "paths": {"template": "resources"},
            "email": {"template": "custom.html"},
        }
    )
    original = store.path.read_bytes()
    other = tmp_path / "other"
    other.mkdir()
    monkeypatch.chdir(other)
    prepared = core.compute_conf(core.load_conf(campaign))
    assert prepared["from"] == "sender@example.org"
    assert prepared["email"]["html_body"].startswith(
        "<title>Invitation été</title><main>"
    )
    assert "<strong>à tous</strong>" in prepared["email"]["html_body"]
    assert prepared["really_send"] is False
    assert prepared["paths"]["template"] == str(resources)
    assert prepared["paths"]["conf_filename"] == str(campaign)
    assert store.path.read_bytes() == original


# -----------------------------------------------------------------------------
def test_upref_nested_defaults_and_campaign_override_are_used_for_rendering(
    tmp_path, campaign, store
):
    templates = tmp_path / "templates"
    templates.mkdir()
    (templates / "common.html").write_text(
        "<header>{{ branding }}</header><main>{{ content }}</main>"
        "<footer>{{ footer }}</footer>",
        encoding="utf-8",
    )
    store.save(
        {
            "paths": {"template": "templates"},
            "email": {
                "template": "common.html",
                "branding": "Common branding",
                "footer": "Common footer",
            },
        }
    )
    campaign.write_text(
        '<!-- var(conf/email/footer) = "Campaign footer" -->\n'
        + campaign.read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    first = core.compute_conf(core.load_conf(campaign))
    assert "<header>Common branding</header>" in first["email"]["html_body"]
    assert "<footer>Campaign footer</footer>" in first["email"]["html_body"]
    store.update({"email": {"branding": "Updated branding"}})
    second = core.compute_conf(core.load_conf(campaign))
    assert "<header>Updated branding</header>" in second["email"]["html_body"]
    assert "<footer>Campaign footer</footer>" in second["email"]["html_body"]


# -----------------------------------------------------------------------------
@pytest.mark.parametrize(
    "state", ["missing", "empty", "profiles_only", "valid", "invalid"]
)
def test_cli_logs_preference_location_before_loading(
    state, campaign, store, tmp_path, caplog
):
    if state == "empty":
        store.save({})
    elif state == "profiles_only":
        store.save({"profiles": {"unused": {}}})
    elif state == "valid":
        store.save({"email": {"footer": "Shared footer"}})
    elif state == "invalid":
        store.path.write_text("email: [", encoding="utf-8")
    with caplog.at_level(logging.INFO):
        result = cli.main(
            ["--conf", str(campaign), "--preview", str(tmp_path / "out.html")]
        )
    assert result == (1 if state == "invalid" else 0)
    messages = [record.getMessage() for record in caplog.records]
    location = f"Fichier upref (valeurs par défaut) : {store.path}"
    assert messages.count(location) == 1
    if state == "invalid":
        assert messages.index(location) < next(
            i
            for i, record in enumerate(caplog.records)
            if record.levelno >= logging.ERROR
        )
    if state in {"missing", "empty"}:
        status = "absent" if state == "missing" else "vide"
        assert any(f"Fichier upref {status}" in message for message in messages)
    if state == "missing":
        assert not store.exists()


# -----------------------------------------------------------------------------
def test_profiles_preserve_paths_at_their_defining_root(tmp_path, store):
    store.save(
        {
            "paths": {"root": "resources", "jinja": "jinja"},
            "email": {"template": "base.html"},
            "profiles": {
                "ebw": {
                    "paths": {"root": "ebw", "img": "images"},
                    "email": {"template": "ebw.html"},
                }
            },
        }
    )
    filename = tmp_path / "profile.mailmd"
    filename.write_text(
        '<!-- var(conf/profile) = "ebw" -->\nBody', encoding="utf-8"
    )
    conf = core.load_conf(filename)
    assert conf["email"]["template"] == "ebw.html"
    assert conf["paths"]["jinja"] == str(tmp_path / "resources" / "jinja")
    assert conf["paths"]["img"] == str(tmp_path / "ebw" / "images")
    assert conf["paths"]["root"] == str(tmp_path / "ebw")


# -----------------------------------------------------------------------------
def test_priority_includes_main_local_and_content_variables(tmp_path, store):
    store.save(
        {
            "from": "common@example.org",
            "email": {"template": "common.html"},
            "profiles": {"ebw": {"email": {"template": "profile.html"}}},
        }
    )
    (tmp_path / "base.conf").write_text(
        "from: included@example.org\nemail:\n  template: included.html\n"
        "  subject: Included\n",
        encoding="utf-8",
    )
    filename = tmp_path / "mail.mailmd"
    filename.write_text(
        '<!-- var(conf/profile) = "ebw" -->\n'
        '<!-- var(conf/paths/includes) = "base.conf" -->\n'
        '<!-- var(conf/from) = "campaign@example.org" -->\n'
        '<!-- var(conf/email/template) = "main.html" -->\n'
        '<!-- var(subject) = "Body subject" -->\n\nBody',
        encoding="utf-8",
    )
    filename.with_suffix(".local.conf").write_text(
        "from: local@example.org\nemail:\n  template: email.html\n"
        "  subject: Local\n",
        encoding="utf-8",
    )
    conf = core.load_conf(filename)
    assert conf["from"] == "local@example.org"
    assert conf["email"]["template"] == "email.html"
    assert conf["email"]["subject"] == "Local"
    assert core.compute_conf(conf)["email"]["subject"] == "Body subject"


# -----------------------------------------------------------------------------
def test_common_lists_are_replaced_but_campaign_lists_still_append(
    tmp_path, store
):
    store.save(
        {
            "paths": {"base_search": ["common"]},
            "profiles": {"ebw": {"paths": {"base_search": ["profile"]}}},
        }
    )
    filename = tmp_path / "mail.conf"
    filename.write_text("profile: ebw\nemail: {}", encoding="utf-8")
    assert core.load_conf(filename)["paths"]["base_search"] == [
        str(tmp_path / "profile")
    ]
    (tmp_path / "base.conf").write_text(
        "paths:\n  base_search: [included]\n"
        "to:\n  list: [included@example.org]",
        encoding="utf-8",
    )
    filename.write_text(
        "profile: ebw\npaths:\n  includes: [base.conf]\n"
        "  base_search: [campaign]\nto:\n  list: [campaign@example.org]\n"
        "email: {}",
        encoding="utf-8",
    )
    filename.with_suffix(".local.conf").write_text(
        "paths:\n  base_search: [local]\nto:\n  list: [local@example.org]",
        encoding="utf-8",
    )
    conf = core.load_conf(filename)
    assert conf["paths"]["base_search"] == [
        str(tmp_path / name) for name in ("included", "campaign", "local")
    ]
    assert conf["to"]["list"] == [
        f"{name}@example.org" for name in ("included", "campaign", "local")
    ]
    filename.with_suffix(".local.conf").unlink()
    filename.write_text(
        "paths:\n  base_search: []\nemail: {}", encoding="utf-8"
    )
    assert core.load_conf(filename)["paths"]["base_search"] == []


# -----------------------------------------------------------------------------
def test_load_reads_common_preferences_again_on_every_run(campaign, store):
    store.save({"from": "first@example.org"})
    assert core.load_conf(campaign)["from"] == "first@example.org"
    store.update({"from": "second@example.org"})
    assert core.load_conf(campaign)["from"] == "second@example.org"


# -----------------------------------------------------------------------------
def test_no_preferences_bypasses_malformed_store_and_campaign_profile(
    campaign, store
):
    store.path.write_text("invalid: [", encoding="utf-8")
    campaign.write_text(
        '<!-- var(conf/profile) = "unknown" -->\n'
        + campaign.read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    prepared = core.compute_conf(
        core.load_conf(campaign, use_preferences=False)
    )
    assert prepared["email"]["subject"] == "Invitation été"
    assert prepared["really_send"] is False


# -----------------------------------------------------------------------------
def test_default_conf_is_independent_of_user_preferences(store):
    store.save(
        {"from": "sender@example.org", "email": {"template": "missing.html"}}
    )
    conf = core.default_conf()
    assert "from" not in conf
    assert core.compute_conf(conf)["really_send"] is False


# -----------------------------------------------------------------------------
@pytest.mark.parametrize("selection", ["unknown", "", 1, False])
def test_invalid_profile_is_actionable(campaign, store, selection):
    store.save({"profiles": {"ebw": {}}})
    with pytest.raises(ValueError, match="[Pp]rofil"):
        core.load_conf(campaign, profile=selection)


# -----------------------------------------------------------------------------
@pytest.mark.parametrize(
    "data",
    [
        {"really_send": "true"},
        {"really_send": 1},
        {"really_send": None},
        {"to": {"list": ["common@example.org"]}},
        {"to": False},
        {"to": {"individual_email": "true"}},
        {"cc": {"list": ["copy@example.org"]}},
        {"bcc": {"list": ["hidden@example.org"]}},
        {"cc": []},
        {"not_to": {"list": "blocked@example.org"}},
        {"not_to": {"list": [False]}},
        {"not_to": {"excel_file": ""}},
        {"not_to": {"excel_column_name": []}},
        {"not_to": {"unexpected": True}},
        {"email": {"subject": "Common"}},
        {"email": {"attachments": []}},
        {"email": {"content": {"txt": "Body"}}},
        {"paths": {"includes": []}},
        {"paths": {"conf_folder": "wrong"}},
        {"from": False},
        {"paths": []},
        {"paths": {"root": []}},
        {"paths": {"img": [False]}},
        {"email": []},
        {"email": {"template": False}},
        {"profiles": []},
        {"profiles": {"ebw": {"really_send": "true"}}},
        {"profiles": {" ": {}}},
        {"profiles": {"ebw": []}},
    ],
)
def test_invalid_common_preferences_stop_before_delivery(
    campaign, store, monkeypatch, data
):
    store.save(data)
    delivery = Mock()
    monkeypatch.setattr(cli, "send_email", delivery)
    assert cli.main(["--conf", str(campaign)]) == 1
    delivery.assert_not_called()


# -----------------------------------------------------------------------------
@pytest.mark.parametrize("text", ["[]", "email: [", "from: a\nfrom: b\n"])
def test_invalid_preference_yaml_is_not_silently_ignored(campaign, store, text):
    store.path.write_text(text, encoding="utf-8")
    with pytest.raises(ConfigFormatError):
        core.load_conf(campaign)


# -----------------------------------------------------------------------------
def test_explicit_store_overrides_environment(
    tmp_path, campaign, store, caplog
):
    store.save({"from": "environment@example.org"})
    explicit = tmp_path / "explicit.yaml"
    explicit.write_text("from: explicit@example.org", encoding="utf-8")
    with caplog.at_level(logging.INFO):
        assert core.load_conf(campaign, preferences=explicit)["from"] == (
            "explicit@example.org"
        )
    assert str(explicit) in caplog.text
    assert str(store.path) not in caplog.text


# -----------------------------------------------------------------------------
def test_environment_override_requires_absolute_path(monkeypatch):
    monkeypatch.setenv(preferences.PREFERENCES_ENV, "relative.yaml")
    with pytest.raises(ValueError, match="absolu"):
        preferences.get_preferences_store()


# -----------------------------------------------------------------------------
def test_platform_lookup_and_path_command_do_not_write(
    monkeypatch, capsys, tmp_path
):
    monkeypatch.delenv(preferences.PREFERENCES_ENV)
    directory = tmp_path / "platform-user"
    monkeypatch.setattr(
        "upref._paths.user_config_path", lambda **kwargs: directory
    )
    assert preferences.main(["--path"]) == 0
    assert capsys.readouterr().out.strip() == str(
        directory / "preferences.yaml"
    )
    assert not directory.exists()


# -----------------------------------------------------------------------------
def test_cli_profile_overrides_campaign_selector(campaign, store, monkeypatch):
    store.save(
        {
            "profiles": {
                "ebw": {"from": "ebw@example.org"},
                "aptitude": {"from": "aptitude@example.org"},
            }
        }
    )
    campaign.write_text(
        '<!-- var(conf/profile) = "ebw" -->\n'
        + campaign.read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    delivery = Mock()
    monkeypatch.setattr(cli, "send_email", delivery)
    assert cli.main(["--conf", str(campaign), "--profile", "aptitude"]) == 0
    assert delivery.call_args.args[0]["from"] == "aptitude@example.org"
    assert delivery.call_args.args[0]["really_send"] is False


# -----------------------------------------------------------------------------
@pytest.mark.parametrize(
    "arguments",
    [
        ["--preferences", "x.yaml", "--no-preferences"],
        ["--profile", "ebw", "--no-preferences"],
    ],
)
def test_conflicting_cli_preference_options_are_rejected(campaign, arguments):
    with pytest.raises(SystemExit) as error:
        cli.main(["--conf", str(campaign), *arguments])
    assert error.value.code == 2


# -----------------------------------------------------------------------------
def test_import_preserves_paths_and_requires_explicit_replacement(
    tmp_path, store, campaign
):
    source_dir = tmp_path / "portable"
    source_dir.mkdir()
    source = source_dir / "common.yaml"
    data = {
        "paths": {"root": "resources", "jinja": "jinja"},
        "profiles": {"ebw": {"paths": {"img": "images"}}},
    }
    source.write_text(yaml.safe_dump(data), encoding="utf-8")
    before = core.load_conf(campaign, preferences=source, profile="ebw")
    assert preferences.main(["--import", str(source)]) == 0
    after = core.load_conf(campaign, profile="ebw")
    assert before == after
    assert Path(after["paths"]["img"]) == source_dir / "resources" / "images"
    original = store.path.read_bytes()
    source.write_text("from: replacement@example.org", encoding="utf-8")
    assert preferences.main(["--import", str(source)]) == 1
    assert store.path.read_bytes() == original
    assert preferences.main(["--import", str(source), "--replace"]) == 0
    assert store.load() == {"from": "replacement@example.org"}


# -----------------------------------------------------------------------------
def test_invalid_import_keeps_existing_preferences(tmp_path, store):
    store.save({"from": "original@example.org"})
    original = store.path.read_bytes()
    source = tmp_path / "bad.yaml"
    source.write_text('really_send: "true"', encoding="utf-8")
    assert preferences.main(["--import", str(source), "--replace"]) == 1
    assert store.path.read_bytes() == original
    assert preferences.main(["--import", str(tmp_path / "missing.yaml")]) == 1
    assert preferences.main(["--import", str(store.path), "--replace"]) == 1


# -----------------------------------------------------------------------------
def test_replacement_requires_import():
    with pytest.raises(SystemExit) as error:
        preferences.main(["--replace"])
    assert error.value.code == 2


# -----------------------------------------------------------------------------
@pytest.mark.parametrize("configured_send", [None, False, True])
@pytest.mark.parametrize("mode", [None, "conf", "no", "yes"])
def test_approved_upref_delivery_defaults_and_send_overrides(
    campaign, store, monkeypatch, configured_send, mode
):
    store.save(
        {
            "really_send": True,
            "to": {"individual_email": True},
            "cc": None,
            "bcc": None,
            "not_to": {"list": ["blocked@example.org"]},
        }
    )
    declaration = (
        ""
        if configured_send is None
        else (
            f"<!-- var(conf/really_send) = {str(configured_send).lower()} -->\n"
        )
    )
    campaign.write_text(
        declaration
        + '<!-- var(conf/to/list) = "second@example.org" -->\n'
        + '<!-- var(conf/to/list) = "blocked@example.org" -->\n'
        + campaign.read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    mails = [Mock(), Mock()]
    factory = Mock(side_effect=mails)
    monkeypatch.setattr(core, "new_email", factory)
    arguments = ["--conf", str(campaign)]
    if mode is not None:
        arguments.extend(["--send-mail", mode])
    assert cli.main(arguments) == 0
    assert factory.call_count == 2
    assert [mail.To for mail in mails] == [
        "second@example.org",
        "recipient@example.org",
    ]
    should_send = mode == "yes" or (
        mode in (None, "conf") and configured_send is not False
    )
    for mail in mails:
        assert mail.Cc == mail.Bcc == ""
        assert mail.Send.call_count == int(should_send)
        assert mail.Save.call_count == int(not should_send)


# -----------------------------------------------------------------------------
def test_campaign_can_disable_global_individual_delivery(
    campaign, store, monkeypatch
):
    store.save({"really_send": True, "to": {"individual_email": True}})
    campaign.write_text(
        "<!-- var(conf/to/individual_email) = false -->\n"
        '<!-- var(conf/to/list) = "second@example.org" -->\n'
        + campaign.read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    factory = Mock()
    monkeypatch.setattr(core, "new_email", factory)
    assert cli.main(["--conf", str(campaign)]) == 0
    factory.assert_called_once()
    assert (
        factory.return_value.To == "second@example.org; recipient@example.org"
    )
    factory.return_value.Send.assert_called_once()


# -----------------------------------------------------------------------------
def test_profile_campaign_and_local_delivery_values_override_common_defaults(
    campaign, store
):
    store.save(
        {
            "really_send": True,
            "to": {"individual_email": True},
            "profiles": {
                "draft": {
                    "really_send": False,
                    "to": {"individual_email": False},
                }
            },
        }
    )
    campaign.write_text(
        '<!-- var(conf/profile) = "draft" -->\n'
        + campaign.read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    profile_conf = core.compute_conf(core.load_conf(campaign))
    assert profile_conf["really_send"] is False
    assert profile_conf["to"]["individual_email"] is False
    campaign.write_text(
        "<!-- var(conf/really_send) = true -->\n"
        "<!-- var(conf/to/individual_email) = true -->\n"
        + campaign.read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    campaign_conf = core.compute_conf(core.load_conf(campaign))
    assert campaign_conf["really_send"] is True
    assert campaign_conf["to"]["individual_email"] is True
    campaign.with_suffix(".local.conf").write_text(
        "really_send: false\nto:\n  individual_email: false\n", encoding="utf-8"
    )
    local_conf = core.compute_conf(core.load_conf(campaign))
    assert local_conf["really_send"] is False
    assert local_conf["to"]["individual_email"] is False


# -----------------------------------------------------------------------------
def test_no_preferences_ignores_global_send_and_individual_defaults(
    campaign, store, monkeypatch
):
    store.save({"really_send": True, "to": {"individual_email": True}})
    factory = Mock()
    monkeypatch.setattr(core, "new_email", factory)
    assert cli.main(["--conf", str(campaign), "--no-preferences"]) == 0
    factory.return_value.Save.assert_called_once()
    factory.return_value.Send.assert_not_called()


# -----------------------------------------------------------------------------
def test_preview_uses_global_send_default_without_delivering(
    campaign, store, tmp_path, monkeypatch
):
    store.save({"really_send": True, "to": {"individual_email": True}})
    delivery = Mock(side_effect=AssertionError("Preview must not deliver"))
    monkeypatch.setattr(cli, "send_email", delivery)
    destination = tmp_path / "preview.html"
    assert (
        cli.main(["--conf", str(campaign), "--preview", str(destination)]) == 0
    )
    delivery.assert_not_called()
    assert destination.exists()


# -----------------------------------------------------------------------------
def test_local_profile_selector_overrides_included_and_main_selector(
    tmp_path, store
):
    store.save(
        {
            "profiles": {
                name: {"from": f"{name}@example.org"}
                for name in ("included", "main", "local")
            }
        }
    )
    (tmp_path / "base.conf").write_text("profile: included", encoding="utf-8")
    source = tmp_path / "mail.conf"
    source.write_text(
        "profile: main\npaths:\n  includes: [base.conf]\nemail: {}",
        encoding="utf-8",
    )
    source.with_suffix(".local.conf").write_text(
        "profile: local", encoding="utf-8"
    )
    assert core.load_conf(source)["from"] == "local@example.org"
    assert core.load_conf(source, profile="main")["from"] == "main@example.org"


# -----------------------------------------------------------------------------
def test_profile_paths_without_global_root_use_preferences_directory(
    campaign, tmp_path, store
):
    store.save({"profiles": {"ebw": {"paths": {"img": "images"}}}})
    assert core.load_conf(campaign, profile="ebw")["paths"]["img"] == str(
        tmp_path / "images"
    )


# -----------------------------------------------------------------------------
def test_python_api_rejects_preferences_when_disabled(campaign, store):
    with pytest.raises(ValueError, match="désactivées"):
        core.load_conf(campaign, use_preferences=False, preferences=store.path)
    with pytest.raises(ValueError, match="désactivées"):
        core.load_conf(campaign, use_preferences=False, profile="ebw")


# -----------------------------------------------------------------------------
def test_cli_no_preferences_bypasses_invalid_file(
    campaign, store, tmp_path, caplog
):
    store.path.write_text("invalid: [", encoding="utf-8")
    output = tmp_path / "preview.html"
    with caplog.at_level(logging.INFO):
        assert (
            cli.main(
                [
                    "--conf",
                    str(campaign),
                    "--no-preferences",
                    "--preview",
                    str(output),
                ]
            )
            == 0
        )
    assert "<strong>à tous</strong>" in output.read_text(encoding="utf-8")
    assert "Préférences upref désactivées" in caplog.text
    assert "Fichier upref" not in caplog.text


# -----------------------------------------------------------------------------
def test_isolated_cli_uses_preferences_for_preview_from_another_directory(
    tmp_path, campaign, store
):
    store.save(
        {"from": "sender@example.org", "email": {"footer": "Shared footer"}}
    )
    output = tmp_path / "preview.html"
    probe = (
        "from pyoutlookmailing import load_conf; import json, sys; "
        "print(json.dumps(load_conf(sys.argv[1])))"
    )
    result = subprocess.run(
        [sys.executable, "-X", "utf8", "-I", "-c", probe, str(campaign)],
        cwd=tmp_path,
        env=os.environ.copy(),
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
        timeout=20,
    )
    conf = json.loads(result.stdout)
    assert conf["from"] == "sender@example.org"
    assert conf["email"]["footer"] == "Shared footer"
    result = subprocess.run(
        [
            sys.executable,
            "-X",
            "utf8",
            "-I",
            "-m",
            "pyoutlookmailing",
            "--conf",
            str(campaign),
            "--preview",
            str(output),
        ],
        cwd=tmp_path,
        env=os.environ.copy(),
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
        timeout=20,
    )
    assert "Fichier upref (valeurs par défaut)" in result.stderr
    assert str(store.path) in result.stderr
    assert "<strong>à tous</strong>" in output.read_text(encoding="utf-8")
