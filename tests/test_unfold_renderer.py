from pathlib import Path

from bs4 import BeautifulSoup
import pymdtools.instruction as mdinst
import pymdtools.mistunege as mistune

from pyoutlookmailing import genenv, renderer


ROOT = Path(__file__).resolve().parents[1]
PATHS = {
    "jinja": str(ROOT / "template" / "jinja"),
    "template": str(ROOT / "template" / "html"),
    "conf_folder": str(ROOT / "mails"),
    "img": str(ROOT / "template" / "img"),
}
NEON_COLORS = ("#5BB8FF", "#8F6BFF", "#E052C7", "#F0B36F")


def _environment():
    return genenv.get_default_jinja_env(PATHS)


def _render_markdown(markdown, context):
    environment = _environment()
    render_context = dict(context)
    render_context["paths"] = PATHS
    dispatch = renderer.RendererDispatch(
        jinja_env=environment,
        context=render_context,
    )
    content = mistune.Markdown(renderer=dispatch)(markdown)
    return environment, content


def test_unfold_renderer_uses_neon_components():
    markdown = """## Event details

Normal text.

[<!-- link-model=unfold-button2 -->Register](https://example.test?a=1&b=2)
"""
    _, content = _render_markdown(markdown, {"model": "unfold"})
    soup = BeautifulSoup(content, "html.parser")

    heading = soup.select_one("h2.unfold-title")
    paragraph = soup.select_one("p.unfold-normal")
    button = soup.select_one("table.unfold-button")
    anchor = button.select_one("a.button-a")

    assert renderer.RendererGenerator.is_renderer("model:unfold")
    assert renderer.RendererGenerator.is_renderer("model-unfold")
    assert heading is not None
    assert paragraph.get_text(strip=True) == "Normal text."
    assert anchor["href"] == "https://example.test?a=1&b=2"
    assert anchor.select_one("span.button-link").get_text(strip=True) == "Register"
    assert "unfold-link" not in anchor.get("class", [])
    assert "text-decoration:none !important" in anchor["style"]
    assert button.find_parent("p") is None
    assert button.find_parent(["h1", "h2", "h3"]) is None
    assert "<v:roundrect" in content
    assert "<w:anchorlock/>" in content
    assert "https://example.test?a=1&amp;b=2" in content
    assert "&amp;amp;" not in content
    assert all(color in content for color in NEON_COLORS)


def test_apt_renderer_keeps_its_existing_components():
    _, content = _render_markdown(
        "## Existing APTITUDE title\n\n"
        "Existing [link](https://normal.test) and "
        "https://autolink.test.",
        {"model": "apt"},
    )

    assert "color:#4e3568" in content
    assert "unfold-title" not in content
    assert "unfold-normal" not in content
    assert "unfold-link" not in content


def test_unfold_button_receives_global_and_inline_palette():
    markdown = """[<!-- link-model=unfold-button2 --><!-- c1=#ABCDEF -->Register](https://button.test)

[Normal link](https://normal.test)

https://autolink.test/path?a=1&b=2

<hello@example.test>
"""
    _, content = _render_markdown(
        markdown,
        {
            "model": "unfold",
            "c1": "#111111",
            "c2": "#223344",
            "c3": "#334455",
            "c4": "#445566",
            "buttoncolor": "#0A0B0C",
        },
    )
    soup = BeautifulSoup(content, "html.parser")

    assert "#ABCDEF" in content
    assert "#111111" not in content
    assert all(color in content for color in ("#223344", "#334455", "#445566"))
    assert "#0A0B0C" in content
    assert soup.select_one("table.unfold-button a[href='https://button.test']")
    normal_link = soup.select_one(
        "p.unfold-normal a.unfold-link[href='https://normal.test']"
    )
    assert normal_link is not None
    assert "color:#FFFFFF !important" in normal_link["style"]
    assert "text-decoration:underline !important" in normal_link["style"]
    assert "color:#FFFFFF !important" in normal_link.span["style"]
    assert "text-decoration:underline !important" in normal_link.span["style"]
    auto_link = soup.select_one(
        "a.unfold-link[href='https://autolink.test/path?a=1&b=2']"
    )
    email_link = soup.select_one(
        "a.unfold-link[href='mailto:hello@example.test']"
    )
    assert auto_link is not None
    assert email_link is not None
    assert auto_link.get_text(strip=True) == \
        "https://autolink.test/path?a=1&b=2"
    assert email_link.get_text(strip=True) == "hello@example.test"
    assert "&amp;amp;" not in content
    assert len(soup.select("table.unfold-button")) == 1


def test_unfold_components_keep_edge_cases_email_safe():
    environment = _environment()
    header = environment.get_template("unfold-header.j2").render(
        begin="",
        level=2,
        text="<strong>Title</strong>",
        mt=0,
        mb=0,
        under_mb=0,
        under_w=241,
    )
    button = environment.get_template("unfold-button2.j2").render(
        link={
            "url": "https://example.test?a=1&amp;b=2",
            "name": "Visible label",
            "title": "Tooltip & information",
        },
        radius=0,
    )
    normal = environment.get_template("unfold-normal.j2").render(
        text="<strong>Text</strong>",
        mt=0,
        mb=0,
    )
    soup = BeautifulSoup(button, "html.parser")
    anchor = soup.select_one("a.button-a")
    main_template = (ROOT / "template" / "html" / "unfold v2.html").read_text(
        encoding="utf-8"
    )

    assert "margin:0px 0 0px 0" in header
    assert "margin:0 0 0px 0" in header
    assert 'width="241"' in header
    assert 'width="61"' in header
    assert "margin:0px 0 0px 0" in normal
    assert "border-radius:0px" in button
    assert anchor.get_text(strip=True) == "Visible label"
    assert anchor["title"] == "Tooltip & information"
    assert anchor["href"] == "https://example.test?a=1&b=2"
    assert "<v:roundrect" in button
    assert "<w:anchorlock/>" in button
    assert "https://example.test?a=1&amp;b=2" in button
    assert ".txt-main .unfold-title *" in main_template
    assert ".txt-main .unfold-normal *" in main_template
    assert ".txt-main a:visited" in main_template
    assert "text-decoration-color:#ffffff !important" in main_template
    assert ".txt-main span.MsoHyperlinkFollowed" in main_template


def test_current_unfold_mail_renders_end_to_end():
    markdown_path = ROOT / "mails" / "2026-08-26 - Invit Unflod.md"
    markdown = markdown_path.read_text(encoding="utf-8")
    context = mdinst.get_vars_from_md_text(markdown)
    environment, content = _render_markdown(markdown, context)
    context["content"] = content
    html = environment.get_template("unfold v2.html").render(context)
    soup = BeautifulSoup(html, "html.parser")

    assert context["model"] == "unfold"
    assert soup.select_one("h2.unfold-title") is not None
    assert soup.select_one("table.unfold-button a.button-a") is not None
    assert soup.select_one(
        "a.unfold-link[href='https://luma.com/11psfn6a']"
    ) is not None
    assert soup.select_one("table.unfold-button").find_parent("p") is None
    assert soup.select_one("img[src='cid:unfold_800.png']") is not None
    assert soup.select_one("table.email-frame")["bgcolor"] == "#eeb961"
    assert all(color in html for color in NEON_COLORS)


if __name__ == "__main__":
    test_unfold_renderer_uses_neon_components()
    test_apt_renderer_keeps_its_existing_components()
    test_unfold_button_receives_global_and_inline_palette()
    test_unfold_components_keep_edge_cases_email_safe()
    test_current_unfold_mail_renders_end_to_end()
    print("5 targeted renderer tests: OK")
