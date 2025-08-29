#!/usr/bin/env python
# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# Copyright (c) 2018 Florent TOURNOIS
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
# -----------------------------------------------------------------------------

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
