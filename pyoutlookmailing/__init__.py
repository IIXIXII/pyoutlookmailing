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
from .version import __version_info__
from .version import __release_date__
from .core import load_conf
from .core import default_conf
from .core import compute_conf
from .core import send_email
from .renderer import html_img

__module_name__ = "pyoutlookmailing"
__package_name__ = "pyoutlookmailing"
__version__ = __version_info__
__author__ = "Florent Tournois"
__copyright__ = "Copyright 2023, Florent Tournois"

__credits__ = [""]
__license__ = "CC BY ND"
__maintainer__ = "Florent Tournois"
__email__ = "florent.tournois@gmail.fr"
__status__ = "Production"
__url__ = "https://github.com/IIXIXII/pyoutlookmailing"

__all__ = [
    'load_conf', 'default_conf', 'compute_conf','send_email','html_img',
]
