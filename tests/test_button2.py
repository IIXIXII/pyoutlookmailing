#!/usr/bin/env python
# -*- coding: utf-8 -*-
# =============================================================================
# Author: Florent TOURNOIS | License: MIT
# =============================================================================

"""Keep registration buttons as real HTML links in the Outlook delivery path."""

import re
from pathlib import Path
from unittest.mock import Mock

import pytest
from bs4 import BeautifulSoup

from pyoutlookmailing import cli, genenv, outlook, renderer

ROOT = Path(__file__).resolve().parents[1]


# -----------------------------------------------------------------------------
def environment():
    if not (ROOT / "template/jinja/button2.j2").is_file():
        pytest.skip("Repository button templates are unavailable")
    return genenv.get_default_jinja_env(
        {
            "jinja": str(ROOT / "template/jinja"),
            "template": str(ROOT / "template/html"),
        }
    )


# -----------------------------------------------------------------------------
def outlook_view(html):
    """Apply the MSO branches used by the old button to expose regressions."""
    html = re.sub(
        r"<!--\[if !mso\]><!-->.*?<!--<!\[endif\]-->",
        "",
        html,
        flags=re.IGNORECASE | re.DOTALL,
    )
    html = re.sub(
        r"<!--\[if mso\]>(.*?)<!\[endif\]-->",
        r"\1",
        html,
        flags=re.IGNORECASE | re.DOTALL,
    )
    return BeautifulSoup(html, "html.parser")


# -----------------------------------------------------------------------------
@pytest.mark.parametrize("model", ["default", "fi", "apt", "unfold"])
def test_registration_button_keeps_a_real_outlook_link_and_following_content(
    model,
):
    convert = renderer.create_markdown(environment(), {"model": model})
    html = convert(
        "[<!-- link-model=button2 -->Register & **join**]"
        '(https://example.org/register?a=1&b=2 "Register here")\n\n'
        "A **normal** [link](https://example.org/agenda)."
    )
    soup = BeautifulSoup(html, "html.parser")
    table = soup.select_one("table.button2")
    assert table is not None
    assert table.find_parent("p") is None
    cell = table.find("td")
    assert cell is not None and cell["align"] == "center"
    anchor = table.select_one("a.button2-link")
    assert anchor is not None
    assert anchor["href"] == "https://example.org/register?a=1&b=2"
    assert anchor.get_text(strip=True) == "Register &join"
    assert anchor.strong is not None
    assert anchor["target"] == "_blank"
    assert anchor["title"] == "Register here"
    assert anchor["aria-label"] == "Register & join"
    outlook_anchor = outlook_view(html).select_one("a.button2-link")
    assert outlook_anchor is not None
    assert outlook_anchor["href"] == anchor["href"]
    assert outlook_anchor["target"] == anchor["target"]
    assert outlook_anchor.strong is not None
    assert len(table.find_all("a")) == 1
    assert table.find(["img", "v:roundrect", "v:shape", "svg"]) is None
    assert "<!--[if" not in str(table)
    assert "&amp;amp;" not in html
    assert len(soup.select("table.button2")) == 1
    normal = soup.find("a", href="https://example.org/agenda")
    assert normal is not None and normal.find_parent("p") is not None
    assert "normal" in soup.get_text()


# -----------------------------------------------------------------------------
def test_custom_button_keeps_dimensions_colors_and_destination():
    options = {
        "link-model": "button2",
        "color": "#FFFFFF",
        "buttontextcolor": "#11458C",
        "bordercolor": "#11458C",
        "border_width": "2",
        "border_style": "dashed",
        "radius": "12",
        "button_width": "300",
        "button_height": "60",
        "padding_x": "24",
        "font_family": "Georgia,serif",
        "font_size": "18",
        "font_weight": "400",
        "line_height": "26",
        "letter_spacing": "0",
        "text_decoration": "underline",
        "mt": "8",
        "mb": "24",
        "align": "right",
        "label": "Book a seat",
        "title": "Registration & information",
        "target": "_self",
        "aria_label": "Book your seat at the conference",
    }
    comments = "".join(
        f"<!-- {key}={value} -->" for key, value in options.items()
    )
    html = renderer.create_markdown(environment(), {})(
        f"[{comments}Register](https://example.org/register)"
    )
    soup = BeautifulSoup(html, "html.parser")
    anchor = soup.select_one("a.button2-link")
    assert anchor is not None
    assert anchor.get_text(strip=True) == "Book a seat"
    assert anchor["title"] == "Registration & information"
    assert anchor["aria-label"] == "Book your seat at the conference"
    assert anchor["target"] == "_self"
    for declaration in (
        "display:block",
        "width:100%",
        "padding:0",
        "border:0",
        "background-color:#FFFFFF",
        "color:#11458C !important",
        "font-family:Georgia,serif",
        "font-size:18px",
        "font-weight:400",
        "line-height:26px",
        "letter-spacing:0.0px",
        "text-decoration:underline !important",
    ):
        assert declaration in anchor["style"]
    cell = anchor.find_parent("td")
    assert cell is not None and cell["bgcolor"] == "#FFFFFF"
    assert cell["width"] == "248"
    assert cell["height"] == "26"
    assert "padding:15.0px 24px" in cell["style"]
    assert "border:2px dashed #11458C" in cell["style"]
    assert "border-radius:12.0px" in cell["style"]
    frame = soup.select_one("table.button2-frame")
    assert frame is not None and frame["width"] == "300"
    assert frame["align"] == "right"
    spacing = frame.find_parent("td")
    assert spacing is not None and spacing["align"] == "right"
    assert "padding:8px 0 24px 0" in spacing["style"]
    outlook_anchor = outlook_view(html).select_one("a.button2-link")
    assert outlook_anchor is not None
    assert outlook_anchor["href"] == anchor["href"]
    assert outlook_anchor["target"] == anchor["target"]


# -----------------------------------------------------------------------------
@pytest.mark.parametrize(
    "options, expected_height",
    [
        ({}, 52),
        ({"padding_y": 20}, 64),
        ({"button_height": 61, "border_width": 2}, 61),
        (
            {
                "button_height": 1,
                "line_height": 26,
                "font_size": 18,
                "border_width": 2,
            },
            30,
        ),
    ],
)
def test_button_height_uses_symmetric_cell_padding_and_normal_text_leading(
    options, expected_height
):
    html = (
        environment()
        .get_template("button2.j2")
        .render(
            link={"url": "https://example.org", "name": "Register"},
            **options,
        )
    )
    soup = BeautifulSoup(html, "html.parser")
    anchor = soup.select_one("a.button2-link")
    assert anchor is not None
    cell = anchor.find_parent("td")
    label = anchor.find("span")
    paragraph = anchor.find_parent("p")
    assert cell is not None and label is not None and paragraph is not None
    height = cell["height"]
    assert isinstance(height, str)
    text_height = int(height)
    font_size = options.get("font_size", 16)
    assert text_height == max(
        options.get("line_height", font_size + 6), font_size
    )
    cell_style = cell["style"]
    assert isinstance(cell_style, str)
    padding = re.search(r"padding:([0-9.]+)px ([0-9.]+)px;", cell_style)
    assert padding is not None
    assert (
        text_height + 2 * float(padding[1]) + 2 * options.get("border_width", 1)
        == expected_height
    )
    assert cell["valign"] == "middle"
    # Padding controls button height, independently of the label's leading.
    # This checks the generated box model, not Outlook's visual rendering.
    for element in (cell, paragraph, anchor, label):
        assert f"line-height:{text_height}px;" in element["style"]
        assert f"font-size:{font_size}px;" in element["style"]
    assert "margin:0;" in paragraph["style"]
    assert "display:block;" in anchor["style"]
    assert "border:0;" in anchor["style"]
    assert "padding:0;" in anchor["style"]
    assert anchor.get_text(strip=True) == "Register"
    assert anchor["href"] == "https://example.org"


# -----------------------------------------------------------------------------
def test_zero_radius_border_and_spacing_do_not_revert_to_defaults():
    html = (
        environment()
        .get_template("button2.j2")
        .render(
            link={"url": "https://example.org", "name": "Register"},
            radius=0,
            border_width=0,
            padding_x=0,
            padding_y=0,
            mt=0,
            mb=0,
            letter_spacing=0,
            font_size=12,
            line_height=14,
        )
    )
    soup = BeautifulSoup(html, "html.parser")
    anchor = soup.select_one("a.button2-link")
    assert anchor is not None
    assert "border:0;" in anchor["style"]
    cell = anchor.find_parent("td")
    assert cell is not None and "border:0px solid" in cell["style"]
    assert "border-radius:0.0px" in cell["style"]
    assert "padding:0.0px 0px" in cell["style"]
    assert cell["height"] == "14"
    frame = cell.find_parent("table")
    assert frame is not None
    spacing = frame.find_parent("td")
    assert spacing is not None and "padding:0px 0 0px 0" in spacing["style"]
    assert outlook_view(html).select_one("a.button2-link") is not None


# -----------------------------------------------------------------------------
@pytest.mark.parametrize("link", [None, {}, {"url": "", "name": "Register"}])
def test_missing_destination_does_not_produce_a_dead_button(link):
    html = environment().get_template("button2.j2").render(link=link)
    assert not html.strip()


# -----------------------------------------------------------------------------
@pytest.mark.parametrize(
    "url", ["javascript:alert%281%29", "data:text/html,bad"]
)
def test_button_does_not_bypass_the_renderers_url_policy(url):
    html = renderer.create_markdown(environment(), {})(
        f"[<!-- link-model=button2 -->Register]({url})"
    )
    soup = BeautifulSoup(html, "html.parser")
    anchor = soup.select_one("a.button2-link")
    outlook_anchor = outlook_view(html).select_one("a.button2-link")
    assert anchor is not None and outlook_anchor is not None
    assert anchor["href"] == outlook_anchor["href"] == "#harmful-link"


# -----------------------------------------------------------------------------
def test_plain_template_values_are_escaped_and_label_has_a_fallback():
    template = environment().get_template("button2.j2")
    soup = BeautifulSoup(
        template.render(
            link={"url": "https://example.org?a=1&b=2", "name": ""},
            label='<img src="invalid"> & Register',
            title='Information " & details',
        ),
        "html.parser",
    )
    assert soup.img is None
    anchor = soup.select_one("a.button2-link")
    assert anchor is not None
    assert anchor["title"] == 'Information " & details'
    assert anchor.get_text(strip=True) == '<img src="invalid"> & Register'
    assert "Register" in template.render(link={"url": "https://example.org"})


# -----------------------------------------------------------------------------
@pytest.mark.parametrize("model", ["default", "fi", "apt", "unfold"])
def test_emphasized_registration_link_stays_outside_paragraphs(model):
    html = renderer.create_markdown(environment(), {"model": model})(
        "**[<!-- link-model=button2 -->Register](https://example.org)**"
    )
    soup = BeautifulSoup(html, "html.parser")
    button = soup.select_one("table.button2")
    assert button is not None
    assert button.find_parent(["p", "strong", "em"]) is None
    assert outlook_view(html).select_one("a.button2-link") is not None


# -----------------------------------------------------------------------------
def test_button_options_do_not_leak_to_the_next_button():
    html = renderer.create_markdown(environment(), {"model": "unfold"})(
        "[<!-- link-model=button2 --><!-- color=#AA0000 -->"
        "<!-- align=left --><!-- radius=0 -->First](https://example.org/first)"
        "\n\n[<!-- link-model=button2 -->Second](https://example.org/second)"
    )
    buttons = BeautifulSoup(html, "html.parser").select("table.button2")
    assert len(buttons) == 2
    first, second = buttons
    first_cell, second_cell = first.find("td"), second.find("td")
    assert first_cell is not None and first_cell["align"] == "left"
    assert second_cell is not None and second_cell["align"] == "center"
    first_anchor = first.select_one("a.button2-link")
    second_anchor = second.select_one("a.button2-link")
    assert first_anchor is not None and second_anchor is not None
    assert "background-color:#AA0000" in first_anchor["style"]
    assert "background-color:#11458C" in second_anchor["style"]
    second_button_cell = second_anchor.find_parent("td")
    assert second_button_cell is not None
    assert "border-radius:6.0px" in second_button_cell["style"]


# -----------------------------------------------------------------------------
def test_example_campaign_can_be_previewed_without_delivery(
    tmp_path, monkeypatch
):
    source = ROOT / "examples/button2.mailmd"
    if not source.is_file():
        pytest.skip("Example campaign is unavailable")

    # -------------------------------------------------------------------------
    def forbid_delivery(*args, **kwargs):
        raise AssertionError("Preview must never deliver a message")

    monkeypatch.setattr(cli, "send_email", forbid_delivery)
    destination = tmp_path / "button2-preview.html"
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
    soup = BeautifulSoup(destination.read_text(encoding="utf-8"), "html.parser")
    assert len(soup.select("table.button2")) == 3
    assert len(soup.select("a.button2-link")) == 3
    for button in soup.select("table.button2"):
        assert button.find_parent("p") is None
        assert (
            outlook_view(str(button)).select_one("a.button2-link") is not None
        )


# -----------------------------------------------------------------------------
@pytest.mark.parametrize("send", [False, True])
def test_outlook_adapter_receives_a_visible_link_without_a_shape_or_attachment(
    send,
):
    html = renderer.create_markdown(environment(), {"model": "apt"})(
        "[<!-- link-model=button2 --><!-- button_width=300 -->"
        "Register](https://example.org/register?a=1&b=2)"
    )
    factory = Mock()
    outlook.deliver(
        {
            "really_send": send,
            "to": {"list": ["recipient@example.org"]},
            "email": {"subject": "Registration", "html_body": html},
        },
        mail_factory=factory,
    )
    mail = factory.return_value
    anchor = outlook_view(mail.HTMLBody).select_one("a.button2-link")
    assert anchor is not None
    assert anchor["href"] == "https://example.org/register?a=1&b=2"
    assert anchor.get_text(strip=True) == "Register"
    assert "v:roundrect" not in mail.HTMLBody
    assert "<img" not in mail.HTMLBody
    mail.Attachments.Add.assert_not_called()
    assert mail.Send.call_count == int(send)
    assert mail.Save.call_count == int(not send)
