#!/usr/bin/env python
# -*- coding: utf-8 -*-
# =============================================================================
# Author: Florent TOURNOIS | License: MIT
# =============================================================================

"""Create Jinja environments and expose template filters for email rendering."""

import jinja2
import pymdtools.common as common
from markupsafe import Markup
from pymdtools.mistune_integration import create_markdown_with_close


# -----------------------------------------------------------------------------
def print_to_console(txt):
    """Print a Jinja debug-filter value and return an empty output string."""
    print(txt)
    return ""


# -----------------------------------------------------------------------------
def md_to_html(txt_md):
    """Render Markdown with the default pymdtools parser and mark the HTML safe.

    Used by the Jinja markdown filter. It does not select the application's
    branded renderers. The default parser escapes authored HTML before the
    generated result is marked safe for insertion into a Jinja template.
    """
    return Markup(create_markdown_with_close()(txt_md))


# -----------------------------------------------------------------------------
def get_default_jinja_env(template_paths_conf):
    """Create a Jinja environment with project templates and packaged fallbacks.

    Args:
        template_paths_conf: Paths mapping. Optional jinja and template
            directories are searched in that order before pyoutlookmailing's
            bundled templates.

    Returns:
        An Environment that autoescapes html, xml, and j2 files. It exposes the
        debug/markdown filters and the current_date/paths globals.

    The supplied paths mapping is stored as a global by reference.
    """
    result = jinja2.Environment(
        loader=jinja2.ChoiceLoader(
            [
                jinja2.FileSystemLoader(
                    [
                        template_paths_conf[key]
                        for key in ("jinja", "template")
                        if key in template_paths_conf
                    ]
                ),
                jinja2.PackageLoader("pyoutlookmailing", "templates"),
            ]
        ),
        autoescape=jinja2.select_autoescape(["html", "xml", "j2"]),
    )

    result.filters["debug"] = print_to_console
    result.filters["markdown"] = md_to_html
    result.globals["current_date"] = common.today_utc
    result.globals["paths"] = template_paths_conf

    return result


class GenerationEnvironment:
    """Keep a configuration and its Jinja environment together for rendering.

    The configuration is held by reference. compute_conf supplies its own deep
    copy when using this class as part of the normal preparation pipeline.
    """

    # --------------------------------------------------------------------------
    def __init__(self, configuration):
        """Create a Jinja environment from the configuration's required paths
        mapping.
        """
        self.__template_conf = configuration
        self.__jinja_env = get_default_jinja_env(configuration["paths"])

    # --------------------------------------------------------------------------
    @property
    def jinja_env(self):
        """Return the Jinja environment used for component and outer-template
        rendering.
        """
        return self.__jinja_env

    # --------------------------------------------------------------------------
    @property
    def template_conf(self):
        """Return the stored configuration object without making a copy."""
        return self.__template_conf

    # --------------------------------------------------------------------------
    @jinja_env.setter
    def jinja_env(self, value):
        """Replace the Jinja environment, for example with a custom loader in
        tests.
        """
        self.__jinja_env = value
