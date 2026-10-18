#!/usr/bin/env python
# -*- coding: utf-8 -*-
# =============================================================================
# Author: Florent TOURNOIS | License: MIT
# =============================================================================

from copy import deepcopy
from pathlib import Path

import pytest
from bs4 import BeautifulSoup
from jinja2 import DictLoader, Environment

from pyoutlookmailing import genenv, renderer

ROOT = Path(__file__).resolve().parents[1]


# -----------------------------------------------------------------------------
def parser(context=None, paths=None):
    paths = paths or {
        "jinja": str(ROOT / "template/jinja"),
        "template": str(ROOT / "template/html"),
    }
    return renderer.create_markdown(
        genenv.get_default_jinja_env(paths), context or {}
    )


# -----------------------------------------------------------------------------
def test_mistune3_plugins_and_core_elements():
    html = parser()("""# Title

> Quote

3. third
4. fourth

~~old~~ and `code` and *emphasis*.[^note]

| A | B |
| :- | -: |
| x | y |

```python
print("hello")
```

[^note]: footnote
""")
    soup = BeautifulSoup(html, "html.parser")
    heading = soup.h1
    ordered_list = soup.ol
    deleted = soup.select_one("del")
    header_cell = soup.select_one("table thead th")
    body_cell = soup.select_one("table tbody td")
    assert heading is not None
    assert ordered_list is not None
    assert deleted is not None
    assert header_cell is not None
    assert body_cell is not None
    assert heading.get_text() == "Title"
    assert soup.blockquote is not None
    assert ordered_list["start"] == "3"
    assert deleted.get_text() == "old"
    assert header_cell.get_text() == "A"
    assert body_cell.get_text() == "x"
    assert soup.select_one("code.language-python") is not None
    assert soup.select_one("section.footnotes") is not None


# -----------------------------------------------------------------------------
@pytest.mark.parametrize("model", ["fi", "apt", "unfold"])
def test_all_models_keep_inline_markup(model):
    html = parser({"model": model})(
        "## Heading **bold**\n\nText with **bold** and "
        "[link](https://example.org?a=1&b=2)."
    )
    soup = BeautifulSoup(html, "html.parser")
    heading = soup.select_one("h2 strong")
    paragraph = soup.select_one("p strong")
    anchor = soup.a
    assert heading is not None
    assert paragraph is not None
    assert anchor is not None
    assert heading.get_text() == "bold"
    assert paragraph.get_text() == "bold"
    assert anchor["href"] == "https://example.org?a=1&b=2"
    assert "&amp;amp;" not in html


# -----------------------------------------------------------------------------
@pytest.mark.parametrize("value", ["true", "false", "yes", "no"])
def test_boolean_heading_instructions_do_not_crash(value):
    html = parser({"model": "apt"})(f"## <!-- underline={value} -->Title")
    assert "<h2 " in html
    assert ("linear-gradient" in html) is (value in {"true", "yes"})


# -----------------------------------------------------------------------------
def test_urls_and_attributes_are_escaped_once():
    html = parser()(
        "[label](https://example.org?a=1&b=2 '\" onmouseover=\"bad')"
    )
    anchor = BeautifulSoup(html, "html.parser").a
    assert anchor is not None
    assert anchor["href"] == "https://example.org?a=1&b=2"
    assert anchor["title"] == '" onmouseover="bad'
    assert "onmouseover" not in anchor.attrs
    assert "&amp;amp;" not in html


# -----------------------------------------------------------------------------
@pytest.mark.parametrize(
    "url", ["javascript:alert%281%29", "vbscript:bad", "data:text/html,bad"]
)
def test_unsafe_link_schemes_are_blocked(url):
    anchor = BeautifulSoup(parser()(f"[link]({url})"), "html.parser").a
    assert anchor is not None
    assert anchor["href"] == "#harmful-link"


# -----------------------------------------------------------------------------
def test_remote_image_never_reads_a_local_file():
    html = parser()('![Remote](https://example.org/image.png "Caption")')
    image = BeautifulSoup(html, "html.parser").img
    assert image is not None
    assert image["src"] == "https://example.org/image.png"
    assert image["title"] == "Caption"


# -----------------------------------------------------------------------------
def test_inline_image_uses_real_mime_type(tmp_path):
    picture = tmp_path / "été.jpg"
    picture.write_bytes(b"jpeg")
    paths = {"conf_folder": str(tmp_path)}
    html = parser(paths=paths)("![<!-- inline=true -->Photo](été.jpg)")
    image = BeautifulSoup(html, "html.parser").img
    assert image is not None
    assert image["src"] == "data:image/jpeg;base64,anBlZw=="
    assert renderer.html_img(picture).startswith('<img src="data:image/jpeg;')


# -----------------------------------------------------------------------------
def test_section_closing_hook_and_parser_reuse():
    env = Environment(
        loader=DictLoader(
            {
                "header_1.j2": (
                    "{% if begin is defined %}<section><h1>{{ text }}</h1>"
                    "{% else %}</section>{% endif %}"
                ),
            }
        )
    )
    convert = renderer.create_markdown(env, {})
    first = convert("# A\n\nText\n\n# B\n\nEnd")
    assert first.count("<section>") == first.count("</section>") == 2
    assert first.endswith("</section>")
    assert convert("plain") == "<p>plain</p>"


# -----------------------------------------------------------------------------
def test_render_pair_does_not_mutate_context():
    env = Environment(
        loader=DictLoader(
            {"pair": "{% if begin is defined %}A{% else %}Z{% endif %}"}
        )
    )
    context = {"nested": {"value": 1}}
    original = deepcopy(context)
    assert renderer.get_render_couple(env.get_template("pair"), context) == (
        "A",
        "Z",
    )
    assert context == original


# -----------------------------------------------------------------------------
def test_raw_outlook_html_and_html_paragraph_links_survive():
    html = parser({"model": "unfold"})(
        "<!--[if mso]><v:rect>MSO</v:rect><![endif]-->\n\n"
        '<p style="text-align:center">https://example.org?a=1&b=2</p>'
    )
    assert "<v:rect>MSO</v:rect>" in html
    anchor = BeautifulSoup(html, "html.parser").select_one("a.unfold-link")
    assert anchor is not None
    assert anchor["href"] == "https://example.org?a=1&b=2"


# -----------------------------------------------------------------------------
def test_markdown_filter_marks_generated_html_safe():
    env = genenv.get_default_jinja_env({})
    assert (
        env.from_string("{{ text | markdown }}").render(text="**bold**")
        == "<p><strong>bold</strong></p>\n"
    )


# -----------------------------------------------------------------------------
def test_table_class_instruction_is_preserved():
    html = parser()("| <!-- class=compact -->A | B |\n| - | - |\n| x | y |")
    table = BeautifulSoup(html, "html.parser").table
    assert table is not None
    assert table["class"] == ["compact"]
    header_cell = table.th
    assert header_cell is not None
    assert header_cell.get_text(strip=True) == "A"
