#!/usr/bin/env python
# -*- coding: utf-8 -*-
# =============================================================================
#                    Author: Florent TOURNOIS | License: MIT                   
# =============================================================================

# -----------------------------------------------------------------------------
# standard object to wrap the context of the generation
# -----------------------------------------------------------------------------
import jinja2

import pymdtools.mdtopdf as mdtopdf
import pymdtools.common as common


# -----------------------------------------------------------------------------
# small function for debug in jinja (it s a filter)
# -----------------------------------------------------------------------------
def print_to_console(txt):
    print(txt)
    return ''

# -----------------------------------------------------------------------------
# small function for debug in jinja (it s a filter)
# -----------------------------------------------------------------------------
def md_to_html(txt_md):
    convert = mdtopdf.get_md_to_html_converter('mistune')
    return convert(txt_md)

# -----------------------------------------------------------------------------
# Get the default jinja2 environment
#
# @return the default jinja env
# -----------------------------------------------------------------------------
def get_default_jinja_env(template_paths_conf):
    result = jinja2.Environment(
        loader=jinja2.FileSystemLoader(
            [template_paths_conf['jinja'], template_paths_conf['template']]),
        autoescape=jinja2.select_autoescape(['html', 'xml']))

    result.filters['debug'] = print_to_console
    result.filters['markdown'] = md_to_html
    result.globals['current_date'] = common.get_today
    result.globals['paths'] = template_paths_conf

    return result

# -----------------------------------------------------------------------------
# An object to manage the generation environment
# -----------------------------------------------------------------------------
class GenerationEnvironment:
    def __init__(self, configuration):
        self.__template_conf = configuration
        self.__jinja_env = get_default_jinja_env(configuration['paths'])

    ###########################################################################
    # the jinja2 environment
    # @return the value
    ###########################################################################
    @property
    def jinja_env(self):
        return self.__jinja_env

    ###########################################################################
    # the jinja2 environment
    # @return the value
    ###########################################################################
    @property
    def template_conf(self):
        return self.__template_conf

    ###########################################################################
    # the jinja2 environment
    # @param value The value to set
    ###########################################################################
    @jinja_env.setter
    def jinja_env(self, value):
        self.__jinja_env = value
