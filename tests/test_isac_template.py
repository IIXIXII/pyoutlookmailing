#!/usr/bin/env python
# -*- coding: utf-8 -*-
# =============================================================================
# Author: Florent TOURNOIS | License: MIT
# =============================================================================

"""Exercise the ISAC example through Markdown preparation and preview."""

from pathlib import Path
from unittest.mock import Mock

import pandas as pd
import pytest
from bs4 import BeautifulSoup
from markupsafe import Markup

from pyoutlookmailing import cli, core, genenv, outlook, preferences, renderer

ROOT = Path(__file__).resolve().parents[1]
PATHS = {
    "jinja": str(ROOT / "template/jinja"),
    "template": str(ROOT / "template/html"),
}


# -----------------------------------------------------------------------------
@pytest.fixture
def environment():
    if not (ROOT / "template/html/isac.html").is_file():
        pytest.skip("Repository ISAC templates are unavailable")
    return genenv.get_default_jinja_env(PATHS)


# -----------------------------------------------------------------------------
def test_example_renders_complete_reference_content_without_delivery(
    tmp_path, monkeypatch, environment
):
    source = ROOT / "examples/isac.mailmd"
    if not source.is_file():
        pytest.skip("Repository example is unavailable")

    # -------------------------------------------------------------------------
    def forbid_delivery(*args, **kwargs):
        raise AssertionError("Preview must never deliver a message")

    monkeypatch.setattr(cli, "send_email", forbid_delivery)
    destination = tmp_path / "isac.html"
    assert (
        cli.main(
            [
                "--conf",
                str(source),
                "--no-preferences",
                "--preview",
                str(destination),
            ]
        )
        == 0
    )
    conf = core.compute_conf(core.read_yaml(source, use_preferences=False))
    assert conf["really_send"] is False
    assert conf["email"]["model"] == "isac"
    assert conf["email"]["template"] == "isac.html"
    html = destination.read_text(encoding="utf-8")
    soup = BeautifulSoup(html, "html.parser")
    assert soup.html is not None and soup.html["lang"] == "en"
    headline = soup.select_one("h1.isac-headline")
    assert headline is not None
    assert headline.get_text(strip=True) == "ISAC 4 Identity & Trust Services"
    assert len(soup.select("h2.isac-heading")) == 5
    cards = soup.select(".isac-card-column")
    assert len(cards) == 3
    titles = [card.h3 for card in cards]
    assert all(title is not None for title in titles)
    assert [
        title.get_text(strip=True) for title in titles if title is not None
    ] == [
        "Threat intelligence",
        "Trusted network",
        "Collective voice",
    ]
    assert "Weight in European decisions" in cards[-1].get_text()
    assert soup.select_one(".isac-content ul li") is not None
    assert soup.find("a", href="mailto:contact@isac4id.eu") is not None
    assert len(soup.find_all("a", href="https://isac4id.eu")) == 1
    assert "Florent Tournois" in soup.get_text()
    assert "Bonjour Florent" not in soup.get_text()
    assert "layout=cards" not in html
    assert "var(" not in soup.get_text()
    assert "<!--[if mso]>" in html and 'width="640"' in html
    assert "@media only screen and (max-width:600px)" in html
    assert ".isac-card-column { display:block !important" in html
    header = soup.select_one(".isac-header")
    assert header is not None
    assert "padding:28px 40px 24px" in header["style"]
    assert "ISAC 4 Identity & Trust Services" in header.get_text()
    assert "Information Sharing & Analysis Centre" in header.get_text()
    top_rule = soup.select_one(".isac-header-rule")
    bottom_rule = soup.select_one(".isac-footer-rule")
    assert top_rule is not None and bottom_rule is not None
    assert top_rule["height"] == bottom_rule["height"] == "4"
    assert top_rule["bgcolor"] == bottom_rule["bgcolor"] == "#3F7FD4"
    assert top_rule["style"] == bottom_rule["style"]
    assert not bottom_rule.get_text(strip=True)
    assert bottom_rule.find(["a", "img", "p"]) is None
    assert soup.select_one(".isac-footer") is None
    assert soup.find(["script", "iframe", "img", "v:roundrect"]) is None
    assert all(table.get("role") == "presentation" for table in soup("table"))
    assert len(html.encode("utf-8")) < 100_000


# -----------------------------------------------------------------------------
def test_cards_keep_inline_markup_safe_urls_and_following_content(environment):
    convert = renderer.create_markdown(environment, {"model": "isac"})
    html = convert(
        "## Benefits\n\n"
        "| <!-- layout=cards -->Shared **knowledge** | Contact |\n"
        "| --- | --- |\n"
        "| A **trusted** community | [Join](https://example.org?a=1&b=2) |\n\n"
        "## Follow-up\n\n"
        "A [normal link](https://example.org/info).\n\n"
        "[Unsafe](javascript:alert%281%29)"
    )
    soup = BeautifulSoup(html, "html.parser")
    cards = soup.select(".isac-card-column")
    assert len(cards) == 2
    assert cards[0].strong is not None
    assert cards[0].find_parent("p") is None
    assert cards[1].a is not None
    assert cards[1].a["href"] == "https://example.org?a=1&b=2"
    assert "color:#2A68BD" in cards[1].a["style"]
    assert "&amp;amp;" not in html
    paragraphs = soup.select("p.isac-paragraph")
    assert "A normal link." in paragraphs[0].get_text()
    assert soup.find("a", href="#harmful-link") is not None


# -----------------------------------------------------------------------------
@pytest.mark.parametrize(
    "markdown",
    [
        "| <!-- layout=cards -->Title |\n| --- |\n| First |\n| Second |",
        "| <!-- layout=cards -->A | B | C | D |\n"
        "| --- | --- | --- | --- |\n| a | b | c | d |",
    ],
)
def test_cards_reject_extra_rows_or_too_many_columns(environment, markdown):
    with pytest.raises(ValueError, match="ISAC layout=cards"):
        renderer.create_markdown(environment, {"model": "isac"})(markdown)


# -----------------------------------------------------------------------------
def test_regular_tables_and_other_renderer_models_are_unchanged(environment):
    markdown = "| Name | Value |\n| --- | --- |\n| First | One |"
    isac = renderer.create_markdown(environment, {"model": "isac"})(markdown)
    assert BeautifulSoup(isac, "html.parser").select_one("table.table thead")
    default = renderer.create_markdown(environment, {})(
        markdown.replace("Name", "<!-- layout=cards -->Name")
    )
    assert "isac-cards" not in default
    assert BeautifulSoup(default, "html.parser").select_one("table.table")


# -----------------------------------------------------------------------------
def test_template_escapes_metadata_and_customizes_its_optional_blocks(
    environment,
):
    html = environment.get_template("isac.html").render(
        subject='Title & "details"',
        headline="Identity <script>alert(1)</script>",
        content=Markup("<p>Rendered <strong>body</strong>.</p>"),
        author="Florent & colleagues",
        role="Coordinator",
        lang="fr",
        signoff="Bien cordialement,",
        contact_email="",
        website_url="javascript:alert(1)",
        isac_width=720,
        isac_navy="#112233",
    )
    soup = BeautifulSoup(html, "html.parser")
    assert soup.script is None
    assert "<script>alert(1)</script>" in soup.get_text()
    assert soup.select_one(".isac-content strong") is not None
    assert "Florent & colleagues" in soup.get_text()
    assert "Bien cordialement," in soup.get_text()
    assert "Coordinator" in soup.get_text()
    assert soup.select_one(".isac-contact") is None
    assert soup.find("a") is None
    assert soup.find("img") is None
    assert "max-width:720px" in html and 'width="720"' in html
    assert 'bgcolor="#112233"' in html


# -----------------------------------------------------------------------------
@pytest.mark.parametrize("send", [False, True])
def test_initial_header_reaches_delivery_as_text_without_attachments(
    environment, send
):
    conf = core.compute_conf(
        core.read_yaml(ROOT / "examples/isac.mailmd", use_preferences=False)
    )
    conf["really_send"] = send
    factory = Mock()
    outlook.deliver(conf, mail_factory=factory)
    mail = factory.return_value
    mail.Attachments.Add.assert_not_called()
    soup = BeautifulSoup(mail.HTMLBody, "html.parser")
    headline = soup.select_one("h1.isac-headline")
    assert headline is not None
    assert headline.get_text(strip=True) == "ISAC 4 Identity & Trust Services"
    assert soup.find("img") is None
    assert mail.Send.call_count == int(send)
    assert mail.Save.call_count == int(not send)


# -----------------------------------------------------------------------------
def test_example_uses_isac_profile_and_shared_blacklist_from_mails(
    tmp_path, monkeypatch, environment
):
    project = tmp_path / "project"
    example_folder = project / "examples"
    mails = project / "mails"
    template_folder = project / "template/html"
    jinja_folder = project / "template/jinja"
    for folder in (example_folder, mails, template_folder, jinja_folder):
        folder.mkdir(parents=True, exist_ok=True)
    template_folder.joinpath("isac.html").write_bytes(
        (ROOT / "template/html/isac.html").read_bytes()
    )
    for component in (ROOT / "template/jinja").glob("isac-*.j2"):
        jinja_folder.joinpath(component.name).write_bytes(
            component.read_bytes()
        )
    source = example_folder / "isac.mailmd"
    source.write_bytes((ROOT / "examples/isac.mailmd").read_bytes())
    pd.DataFrame({"BLACKLIST": ["blocked@example.org"]}).to_excel(
        mails / "mail_list.xlsx", index=False
    )
    preferences.get_preferences_store().save(
        {
            "paths": {"root": str(project)},
            "really_send": True,
            "not_to": {
                "excel_file": "mail_list.xlsx",
                "excel_column_name": ["BLACKLIST"],
            },
            "profiles": {
                "isac": {
                    "email": {
                        "model": "isac",
                        "template": "isac.html",
                        "isac_width": 800,
                    }
                }
            },
        }
    )

    # -------------------------------------------------------------------------
    def forbid_delivery(*args, **kwargs):
        raise AssertionError("Preview must never deliver a message")

    monkeypatch.setattr(cli, "send_email", forbid_delivery)
    destination = tmp_path / "profile-preview.html"
    assert cli.main(["--conf", str(source), "--preview", str(destination)]) == 0
    prepared = core.compute_conf(core.read_yaml(source))
    assert prepared["profile"] == "isac"
    assert prepared["not_to"]["list"] == ["blocked@example.org"]
    assert prepared["really_send"] is False
    html = destination.read_text(encoding="utf-8")
    assert "max-width:800px" in html and 'width="800"' in html
