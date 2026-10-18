#!/usr/bin/env python
# -*- coding: utf-8 -*-
# =============================================================================
# Author: Florent TOURNOIS | License: MIT
# =============================================================================

"""Render trusted Markdown emails with Mistune 3 and Jinja templates."""

from __future__ import annotations

import base64
import copy
import re
from collections.abc import Callable
from html import unescape
from itertools import count
from mimetypes import guess_type
from urllib.parse import unquote

import pymdtools.common as common
from markupsafe import Markup
from pymdtools import mistune_integration as mistune

from .files import find_file

__comment_re__ = r"<!--(?P<comment>[\s\S]*?)-->"

__instruction_re__ = r"(?P<name>[a-zA-Z0-9_-]+)\s*[:=]\s*(?P<value>.*)"

_id_counter = count(1)


# -----------------------------------------------------------------------------
def encode_img(filename):
    """Read an existing local file and return its ASCII-compatible Base64 text.

    The filename is a string or path-like object. File validation and reading
    errors propagate; no MIME prefix or HTML tag is included in the result.
    """
    filename = common.check_file(filename)
    image_file = filename.read_bytes()
    return base64.b64encode(image_file).decode("utf-8")


# -----------------------------------------------------------------------------
def html_img(filename):
    """Return an HTML img tag containing the local file as a data URL.

    Infer the MIME type from the filename, falling back to
    application/octet-stream. The file is read immediately and
    missing/unreadable file errors propagate.
    """
    mime = guess_type(str(filename))[0] or "application/octet-stream"
    return f'<img src="data:{mime};base64,{encode_img(filename)}"/>'


# -----------------------------------------------------------------------------
def get_new_id(label: str | None = None) -> str:
    """Return a process-local HTML identifier using a label and an increasing
    counter.

    The optional label is converted to an ASCII slug, stripped of separators,
    and truncated to ten characters. The counter is shared across calls and
    starts at 1.
    """
    identifier = next(_id_counter)
    result = label

    if result is None:
        result = "id"

    result = common.to_ascii(result)
    result = common.slugify(result).replace("-", "")
    result = result.replace("_", "")
    result = f"id{result[:10]}{identifier:04d}"

    return result


# -----------------------------------------------------------------------------
def strip_xml_comment(text):
    """Remove all HTML/XML comments from text, including multiline comments."""
    result = re.sub(__comment_re__, "", text)
    return result


# -----------------------------------------------------------------------------
def read_instructions(text):
    """Read name=value or name:value instructions from HTML comments.

    Return lowercase names with string values. Later occurrences replace earlier
    ones. This renderer syntax is distinct from the var(...) configuration
    syntax.
    """
    result = {}
    comments = re.finditer(__comment_re__, text)
    for comment in comments:
        line = comment.group("comment").strip()
        match = re.search(__instruction_re__, line)
        if match is not None:
            result[match.group("name").lower()] = match.group("value")
    return result


# -----------------------------------------------------------------------------
def get_render_couple(template, context):
    """Render a Jinja template twice to obtain opening and closing HTML
    fragments.

    Pass begin="" for the first render and end="" for the second, discarding any
    existing begin/end keys in the supplied context. Return (begin_html,
    end_html) without changing the input context.
    """
    context = {
        key: value
        for key, value in context.items()
        if key not in {"begin", "end"}
    }
    begin = template.render({**context, "begin": ""})
    end = template.render({**context, "end": ""})

    return (begin, end)


class RendererGenerator:
    """Map case-insensitive renderer names to factory callables."""

    __generator: dict[str, Callable[..., RendererDefault]] = {}

    # --------------------------------------------------------------------------
    @staticmethod
    def is_renderer(name: str) -> bool:
        """Return whether a renderer factory is registered under name,
        ignoring case.
        """
        return name.lower() in RendererGenerator.__generator

    # --------------------------------------------------------------------------
    @staticmethod
    def register(name: str, creator: Callable[..., RendererDefault]) -> bool:
        """Register or replace a renderer factory and return True.

        The creator callable receives the keyword arguments passed to create and
        returns a RendererDefault-compatible instance. Registration changes
        global state.
        """
        RendererGenerator.__generator[name.lower()] = creator
        return True

    # --------------------------------------------------------------------------
    @staticmethod
    def create(name: str, **kwargs) -> RendererDefault:
        """Call a registered factory with kwargs; raise KeyError for an
        unknown name.
        """
        return RendererGenerator.__generator[name.lower()](**kwargs)


class ContextManagment:
    """Combine base context, initial instructions, and current instructions.

    The historical class spelling is retained for compatibility. Reading context
    returns a deep copy with instruction overrides; the stored mappings remain
    mutable.
    """

    # --------------------------------------------------------------------------
    def __init__(self, context):
        """Store the base context by reference and initialize empty
        instruction mappings.
        """
        self.__context = context
        self.__init_instructions = {}
        self.__instructions = {}

    # --------------------------------------------------------------------------
    @property
    def init_instructions(self):
        """Return the mutable initial-instruction mapping."""
        return self.__init_instructions

    # --------------------------------------------------------------------------
    @init_instructions.setter
    def init_instructions(self, value):
        """Replace the initial-instruction mapping by reference."""
        self.__init_instructions = value

    # --------------------------------------------------------------------------
    @property
    def instructions(self):
        """Return the mutable current-instruction mapping."""
        return self.__instructions

    # --------------------------------------------------------------------------
    @instructions.setter
    def instructions(self, value):
        """Replace the current-instruction mapping by reference."""
        self.__instructions = value

    # --------------------------------------------------------------------------
    def del_instructions(self):
        """Clear current instructions while retaining initial instructions
        and base context.
        """
        self.__instructions = {}

    # --------------------------------------------------------------------------
    @property
    def context(self):
        """Return a deep copy with initial then current instructions
        overriding base values.
        """
        result = copy.deepcopy(self.__context)
        for key in self.__init_instructions:
            result[key] = copy.deepcopy(self.__init_instructions[key])
        for key in self.__instructions:
            result[key] = copy.deepcopy(self.__instructions[key])

        return result


class JinjaEnvManagment:
    """Provide shared access to a Jinja environment for component renderers.

    The historical class spelling is retained for compatibility.
    """

    # --------------------------------------------------------------------------
    def __init__(self, jinja_env):
        """Store the supplied Jinja environment by reference."""
        self.__jinja_env = jinja_env

    # --------------------------------------------------------------------------
    @property
    def jinja_env(self):
        """Return the Jinja environment used to load component templates."""
        return self.__jinja_env


class RendererDefault(JinjaEnvManagment):
    """Render basic email components using HTML and the default Jinja templates.

    Header methods return opening/closing pairs; other methods return complete
    HTML fragments. The dispatch adapter converts Mistune 3 calls to these
    legacy component signatures. Text arguments already contain rendered inline
    HTML.
    """

    # --------------------------------------------------------------------------
    @staticmethod
    def generate(**kwargs):
        """Create a default renderer from the required jinja_env keyword
        argument.
        """
        return RendererDefault(jinja_env=kwargs["jinja_env"])

    # --------------------------------------------------------------------------
    def __init__(self, jinja_env):
        """Initialize the component renderer with its Jinja environment."""
        JinjaEnvManagment.__init__(self, jinja_env)

    # --------------------------------------------------------------------------
    def header(self, text, level, raw=None):
        """Return opening/closing HTML for a heading of the supplied level.

        Level 1 uses header_1.j2; other levels emit a complete heading and an
        empty closing fragment. The legacy raw argument is accepted but unused.
        """
        if level == 1:
            return self.header_1(text)

        begin = f"<h{level}>{text}</h{level}>\n"
        end = ""
        return (begin, end)

    # --------------------------------------------------------------------------
    def header_1(self, text):
        """Render header_1.j2 as a pair of fragments with trusted inline
        heading HTML.
        """
        begin = self.jinja_env.get_template("header_1.j2").render(
            {"begin": "", "text": Markup(text)}
        )
        end = self.jinja_env.get_template("header_1.j2").render(
            {"end": "", "text": Markup(text)}
        )
        return (begin, end)

    # --------------------------------------------------------------------------
    def table(self, header, body):
        """Wrap rendered header/body rows in a table, honoring a header class
        instruction.
        """
        inst = read_instructions(header)
        header = strip_xml_comment(header)

        bclass = "table"
        if "class" in inst:
            bclass = inst["class"]
        return (
            f'<table class="{mistune.escape(bclass)}">\n'
            f"<thead>{header}</thead>\n"
            f"<tbody>\n{body}</tbody>\n</table>\n"
        )

    # --------------------------------------------------------------------------
    def paragraph(self, text):
        """Wrap inline HTML in a paragraph, applying alert-start, alert-end,
        and fa instructions.
        """
        inst = read_instructions(text)
        text = strip_xml_comment(text)
        start_p = "<p>"
        end_p = "</p>"
        if "alert-start" in inst:
            start_p = (
                '<div class="alert alert-{}" role="alert">'.format(
                    mistune.escape(inst["alert-start"])
                )
                + start_p
            )

        if "alert-end" in inst:
            end_p = end_p + "</div>"
        if "fa" in inst:
            start_p = start_p + '<i class="fa fa-{}"></i>  '.format(
                mistune.escape(inst["fa"])
            )

        return start_p + text.strip(" ") + end_p

    # --------------------------------------------------------------------------
    def image(self, src, title, text):
        """Render image.j2 from a URL, optional title, and rendered alternative
        text.

        Instructions in the alternative text become template variables. Presence
        of inline resolves a local file under paths.conf_folder, paths.img, or
        their img subfolders and embeds its Base64 data; otherwise the source
        remains a URL. Missing local files raise FileNotFoundError.
        """
        context = read_instructions(text)
        text = strip_xml_comment(text)

        context["src"] = safe_link(src)
        context["alt"] = unescape(text)
        if "inline" in context:
            paths = self.jinja_env.globals["paths"]
            filename = find_file(
                unquote(unescape(src)),
                [paths.get("conf_folder", "."), paths.get("img", ".")],
                ("", "img"),
            )
            context["base64"] = encode_img(filename)
            context["mime"] = (
                guess_type(str(filename))[0] or "application/octet-stream"
            )
        if title:
            context["title"] = title

        result = self.jinja_env.get_template("image.j2").render(context)
        return result

    # --------------------------------------------------------------------------
    def link(self, link, title, text):
        """Render a URL, optional title, and inline HTML label through a link
        template.

        Use link_normal.j2 unless a link-model instruction names another .j2
        template. The destination is processed by safe_link before entering the
        Jinja context.
        """
        context = read_instructions(text)
        text = strip_xml_comment(text)

        context["link"] = {"url": safe_link(link), "name": Markup(text)}
        if title is not None:
            context["link"]["title"] = title

        if "link-model" not in context:
            return self.jinja_env.get_template("link_normal.j2").render(context)

        return self.jinja_env.get_template(
            context["link-model"] + ".j2"
        ).render(context)


class RendererFi(RendererDefault, ContextManagment):
    """Render FI headings and paragraphs using fi_header.j2 and fi_*.j2
    templates.
    """

    # --------------------------------------------------------------------------
    @staticmethod
    def generate(**kwargs):
        """Create an FI renderer from the required jinja_env and context
        keywords.
        """
        return RendererFi(
            jinja_env=kwargs["jinja_env"], context=kwargs["context"]
        )

    # --------------------------------------------------------------------------
    def __init__(self, jinja_env, context):
        """Initialize FI templates and the shared email context."""
        RendererDefault.__init__(self, jinja_env)
        ContextManagment.__init__(self, context)

    # --------------------------------------------------------------------------
    def header(self, text, level, raw=None):
        """Render an FI heading with local instructions and an empty closing
        fragment.
        """
        self.instructions = read_instructions(text)
        text = strip_xml_comment(text)
        context = self.context

        context["level"] = level
        context["text"] = Markup(text)

        (begin, end) = get_render_couple(
            self.jinja_env.get_template("fi_header.j2"), context
        )

        self.del_instructions()
        return (begin, "")

    # --------------------------------------------------------------------------
    def paragraph(self, text):
        """Render fi_<p>.j2 (default: fi_normal.j2); omit empty paragraphs."""
        inst = read_instructions(text)
        text = strip_xml_comment(text)
        context = self.context

        context["text"] = Markup(text).strip(" ")
        if len(context["text"]) == 0:
            return ""

        if "p" not in inst:
            inst["p"] = "normal"

        return self.jinja_env.get_template("fi_" + inst["p"] + ".j2").render(
            context
        )


class RendererApt(RendererDefault, ContextManagment):
    """Render APTITUDE components, with template_prefix overridable by
    subclasses.
    """

    # Prefix used for the Jinja components of this renderer.
    template_prefix = "apt"

    # --------------------------------------------------------------------------
    @staticmethod
    def generate(**kwargs):
        """Create an APTITUDE renderer from jinja_env and context keywords."""
        return RendererApt(
            jinja_env=kwargs["jinja_env"], context=kwargs["context"]
        )

    # --------------------------------------------------------------------------
    def __init__(self, jinja_env, context):
        """Initialize the component renderer and its shared email context."""
        RendererDefault.__init__(self, jinja_env)
        ContextManagment.__init__(self, context)

    # --------------------------------------------------------------------------
    def header(self, text, level, raw=None):
        """Render a heading pair after interpreting boolean instruction strings.

        Use <template_prefix>-header.j2. Local instructions override the email
        context for this heading and are cleared afterwards. The raw argument is
        unused.
        """
        self.instructions = read_instructions(text)
        text = strip_xml_comment(text)
        context = self.context

        context["level"] = level
        context["text"] = Markup(text)

        for inst in self.instructions:
            context[inst] = self.instructions[inst]
            if context[inst].lower() in ("y", "yes", "t", "true", "on", "1"):
                context[inst] = True
            elif context[inst].lower() in ("n", "no", "f", "false", "off", "0"):
                context[inst] = False

        (begin, end) = get_render_couple(
            self.jinja_env.get_template(self.template_prefix + "-header.j2"),
            context,
        )

        self.del_instructions()
        return (begin, end)

    # --------------------------------------------------------------------------
    def paragraph(self, text):
        """Render <template_prefix>-<p>.j2 with normal as the default paragraph
        style.

        Pass the mb instruction as a margin override and omit empty paragraphs.
        """
        inst = read_instructions(text)
        text = strip_xml_comment(text)
        context = self.context

        context["text"] = Markup(text).strip(" ")
        if len(context["text"]) == 0:
            return ""

        if "p" not in inst:
            inst["p"] = "normal"
        if "mb" in inst:
            context["mb"] = inst["mb"]

        return self.jinja_env.get_template(
            self.template_prefix + "-" + inst["p"] + ".j2"
        ).render(context)


class RendererUnfold(RendererApt):
    """Render UNFOLD components with shared colors and Outlook-compatible
    buttons.
    """

    template_prefix = "unfold"

    # --------------------------------------------------------------------------
    @staticmethod
    def generate(**kwargs):
        """Create an UNFOLD renderer from jinja_env and context keywords."""
        return RendererUnfold(
            jinja_env=kwargs["jinja_env"], context=kwargs["context"]
        )

    # --------------------------------------------------------------------------
    def paragraph(self, text):
        """Preserve UNFOLD button tables and their Outlook conditional comments.

        Other paragraphs use the APTITUDE-compatible paragraph logic with UNFOLD
        templates.
        """
        if re.match(
            r'^\s*<table\b[^>]*\bclass\s*=\s*["\'][^"\']*'
            r"\bunfold-button\b",
            text,
            flags=re.IGNORECASE | re.DOTALL,
        ):
            return text.strip()

        return super().paragraph(text)

    # --------------------------------------------------------------------------
    def autolink(self, link, is_email=False):
        """Render a bare URL or email address with the UNFOLD link template.

        Set is_email to prefix the destination with mailto:. This is a legacy
        component hook; the Mistune 3 dispatch path normally calls link for
        parsed autolinks.
        """
        href = ("mailto:" + link) if is_email else link
        context = self.context
        context["link"] = {
            "url": safe_link(href),
            "name": Markup(mistune.escape(link)),
        }

        return self.jinja_env.get_template("unfold-link-normal.j2").render(
            context
        )

    # --------------------------------------------------------------------------
    def link(self, link, title, text):
        """Render a link using shared UNFOLD context, overridden by inline
        instructions.

        Use unfold-link-normal.j2 by default, or the link-model component when
        provided.
        """
        instructions = read_instructions(text)
        text = strip_xml_comment(text)
        context = self.context

        for key in instructions:
            context[key] = instructions[key]

        context["link"] = {"url": safe_link(link), "name": Markup(text)}
        if title is not None:
            context["link"]["title"] = title

        if "link-model" not in context:
            return self.jinja_env.get_template("unfold-link-normal.j2").render(
                context
            )

        return self.jinja_env.get_template(
            context["link-model"] + ".j2"
        ).render(context)


# Register factories after class creation, when static methods are normal
# callables.
RendererGenerator.register("default", RendererDefault.generate)
RendererGenerator.register("model:fi", RendererFi.generate)
RendererGenerator.register("model-fi", RendererFi.generate)
RendererGenerator.register("model:apt", RendererApt.generate)
RendererGenerator.register("model-apt", RendererApt.generate)
RendererGenerator.register("model:unfold", RendererUnfold.generate)
RendererGenerator.register("model-unfold", RendererUnfold.generate)


# -----------------------------------------------------------------------------
def safe_link(url: str) -> Markup:
    """Return a Markup URL using Mistune's scheme policy and one HTML escaping
    pass.

    Decode existing HTML entities first so query-string ampersands are not
    escaped twice. Markup prevents Jinja from applying a second escaping pass.
    """
    return Markup(mistune.HTMLRenderer().safe_url(unescape(url)))


class RendererDispatch(mistune.ClosingHTMLRenderer):
    """Adapt component renderers to Mistune 3 and close nested heading sections.

    The active renderer is inherited from the nearest enclosing heading level.
    Each render resets parser-specific state, allowing sequential reuse.
    Instances carry mutable state and should not be shared across concurrent
    renders.
    """

    # --------------------------------------------------------------------------
    def __init__(self, *, jinja_env, context):
        """Create a dispatcher with a Jinja environment and the email variable
        context.

        Authored raw HTML is preserved. Renderer selection may raise ValueError
        when the initial context names multiple registered renderers.
        """
        super().__init__(escape=False)
        self._inline = mistune.create_markdown(
            renderer=None, plugins=["url"]
        ).inline
        self._kwargs = {"jinja_env": jinja_env, "context": context}
        self._reset()

    # --------------------------------------------------------------------------
    def _reset(self):
        """Reset heading state and select the initial renderer from the email
        context.
        """
        self._level = 0
        self._renderers = {
            0: RendererGenerator.create("default", **self._kwargs)
        }
        self._ends = {}
        self._change_renderer(self._kwargs["context"])

    # --------------------------------------------------------------------------
    def __call__(self, tokens, state):
        """Render Mistune tokens for a block state after resetting section
        state.
        """
        self._reset()
        self._state = state
        return super().__call__(tokens, state)

    # --------------------------------------------------------------------------
    @property
    def level(self):
        """Return the heading level, or zero before the first heading."""
        return self._level

    # --------------------------------------------------------------------------
    def get_renderer(self, level: int | None = None) -> RendererDefault:
        """Return the renderer at level, falling back to the nearest enclosing
        level.

        An omitted level uses the current heading level. Level zero always has a
        default renderer, possibly replaced by an initial model selection.
        """
        level = self.level if level is None else level
        while level not in self._renderers and level > 0:
            level -= 1
        return self._renderers[level]

    # --------------------------------------------------------------------------
    def get_renderer_method(self, method, level=None):
        """Return a named component attribute at level, or None when it is
        absent.
        """
        return getattr(self.get_renderer(level), method, None)

    # --------------------------------------------------------------------------
    def add_to_stack(self, level, content):
        """Store closing HTML for a level; reject an already open section at
        that level.
        """
        if level in self._ends:
            raise RuntimeError(
                "A section must be closed before opening another"
            )
        self._ends[level] = content

    # --------------------------------------------------------------------------
    def change_level(self, new_level):
        """Close sections down to new_level and return their accumulated closing
        HTML.

        The section at new_level is also closed before a replacement is opened.
        Negative levels are clamped to zero; renderer selections above level
        zero are discarded as their sections close.
        """
        new_level = max(new_level, 0)
        result = ""
        for level in range(self.level, new_level - 1, -1):
            result += self._ends.pop(level, "")
            if level > 0:
                self._renderers.pop(level, None)
        self._level = new_level
        return result

    # --------------------------------------------------------------------------
    def _change_renderer(self, instructions):
        """Select a renderer from instruction keys or key:value combinations.

        Recognized names are matched case-insensitively. Ignore unrecognized
        choices; raise ValueError if more than one registered selection appears
        in the mapping.
        """
        candidates = []
        for key, value in instructions.items():
            if isinstance(value, str):
                for name in (key, f"{key}:{value}"):
                    if RendererGenerator.is_renderer(name):
                        candidates.append(name)
        if len(candidates) > 1:
            raise ValueError("Multiple renderers selected for the same section")
        if candidates:
            self._renderers[self.level] = RendererGenerator.create(
                candidates[0], **self._kwargs
            )

    # --------------------------------------------------------------------------
    def change_renderer_on_instrcution(self, text):
        """Select a renderer from HTML comment instructions in text.

        The historical method spelling is retained for compatibility.
        """
        self._change_renderer(read_instructions(text))

    # --------------------------------------------------------------------------
    def close(self):
        """Return closing HTML for all remaining heading sections and reset
        the level.
        """
        return self.change_level(0)

    # --------------------------------------------------------------------------
    def heading(self, text, level, **attrs):
        """Close prior sections, select a local renderer, and open a heading
        section.
        """
        unstack = self.change_level(level)
        self.change_renderer_on_instrcution(text)
        begin, end = self.get_renderer().header(text, level)
        self.add_to_stack(level, end)
        return unstack + begin

    # --------------------------------------------------------------------------
    def paragraph(self, text):
        """Delegate paragraph HTML to the current component renderer."""
        return self.get_renderer().paragraph(text)

    # --------------------------------------------------------------------------
    def link(self, text, url, title=None):
        """Adapt Mistune's text/url/title order to the component renderer's
        link signature.
        """
        return self.get_renderer().link(url, title, text)

    # --------------------------------------------------------------------------
    def image(self, text, url, title=None):
        """Adapt Mistune's text/url/title order to the component renderer's
        image signature.
        """
        return self.get_renderer().image(url, title, text)

    # --------------------------------------------------------------------------
    def table(self, text):
        """Split Mistune table HTML into header/body fragments for the active
        renderer.

        Fall back to a basic table wrapper when the expected thead/tbody
        structure is absent.
        """
        parts = re.fullmatch(
            r"\s*<thead>(.*?)</thead>\s*<tbody>(.*?)</tbody>\s*",
            text,
            re.DOTALL,
        )
        if parts:
            return self.get_renderer().table(*parts.groups())
        return f'<table class="table">\n{text}</table>\n'

    # --------------------------------------------------------------------------
    def block_html(self, html):
        """Preserve raw HTML, parsing inline Markdown inside standalone p
        elements.

        This keeps authored Outlook tables, conditional comments, and VML intact
        while allowing Markdown and bare-URL links in legacy HTML paragraphs.
        """
        paragraph = re.fullmatch(
            r"(<p\b[^>]*>)(.*?)(</p>\s*)", html, flags=re.IGNORECASE | re.DOTALL
        )
        if paragraph:
            start, text, end = paragraph.groups()
            tokens = self._inline(text, self._state.env)
            return start + self.render_tokens(tokens, self._state) + end
        return super().block_html(html)


# -----------------------------------------------------------------------------
def create_markdown(jinja_env, context):
    """Build the application's Markdown-to-HTML parser with section-closing
    support.

    Args:
        jinja_env: Jinja Environment containing component templates and paths
            globals.
        context: Email variables, including an optional model selector.

    Returns:
        A callable Mistune parser configured with table, strikethrough,
        footnotes, and url plugins. Calling it returns HTML and closes all
        heading sections.

    The parser can be reused sequentially. Raw HTML is preserved, so only
    trusted author content should be passed to it.
    """
    return mistune.create_markdown_with_close(
        renderer=RendererDispatch(jinja_env=jinja_env, context=context),
        plugins=["table", "strikethrough", "footnotes", "url"],
    )
