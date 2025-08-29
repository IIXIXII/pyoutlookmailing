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

import logging
import sys
import io
import os
import os.path
import time
from shutil import rmtree
from setuptools import setup, Command
import setuptools.command.build_py

import pyoutlookmailing as mymodule

__root__ = os.path.abspath(os.path.join(os.path.dirname(__file__)))

# Import the README and use it as the long-description.
# Note: this will only work if 'README.md' is present in your MANIFEST.in file!
try:
    with io.open(os.path.join(__root__, 'README.md'), encoding='utf-8') as f:
        __long_description__ = '\n' + f.read()
except FileNotFoundError:
    __long_description__ = mymodule.__doc__


# -----------------------------------------------------------------------------
# Set up the logging system
# -----------------------------------------------------------------------------
def __set_logging_system():
    log_filename = os.path.splitext(os.path.abspath(
        os.path.realpath(__file__)))[0] + '.log'
    logging.basicConfig(filename=log_filename, level=logging.DEBUG,
                        format='%(asctime)s: %(message)s',
                        datefmt='%m/%d/%Y %I:%M:%S %p')
    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    # set a format which is simpler for console use
    formatter = logging.Formatter('%(asctime)s: %(levelname)-8s %(message)s')
    # tell the handler to use this format
    console.setFormatter(formatter)
    # add the handler to the root logger
    logging.getLogger('').addHandler(console)


__set_logging_system()

# -------------------------------------------------------------------------------
# Increase the version number
# -------------------------------------------------------------------------------


def print_status(msg):
    print('>> {0}'.format(msg))

# -------------------------------------------------------------------------------
# Increase the version number
# -------------------------------------------------------------------------------


def increase_version():
    about = {}
    with open(os.path.join(__root__, mymodule.__module_name__,
                           'version.py'), "r") as ver:
        exec(ver.read(), about)

    current_version = about['__version_info__']
    print_status("Previous version = %s" % current_version)

    new_version = time.strftime("%Y.%m.%d", time.gmtime())
    if new_version[:10] == current_version[:10]:
        release = 0
        if len(current_version) > 10:
            release = int(current_version[11:])
        release += 1
        new_version = "%s-%03d" % (new_version, release)

    print_status("New version = %s" % new_version)
    about['version'] = new_version

    print_status("Write version for python")
    with open(os.path.join(__root__, mymodule.__module_name__,
                           'version.py'), "w") as ver:
        ver.write("#!/usr/bin/env python\n")
        ver.write("# -*- coding: utf-8 -*-\n\n")
        ver.write("__version_info__ = %s\n" % repr(new_version))
        ver.write("__release_date__ = '%s'\n" %
                  time.strftime("%Y-%m-%d", time.gmtime()))

    bat_filename = os.path.join(__root__, mymodule.__module_name__,
                                'version.bat')

    print_status("Write version for windows bat")
    if os.path.isfile(bat_filename):
        with open(bat_filename, "w") as ver:
            ver.write('SET VERSION=%s\n' % new_version)


# -------------------------------------------------------------------------------
# My command class
# -------------------------------------------------------------------------------
class CustomCommand(Command):
    @staticmethod
    def status(msg):
        print_status(msg)

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass


# -------------------------------------------------------------------------------
# Upload
# -------------------------------------------------------------------------------
class UploadPyCommand(CustomCommand):
    """Support setup.py upload."""

    description = 'Build and publish the package.'
    user_options = []

    def run(self):
        try:
            self.status('Removing previous builds - remove the folder build')
            rmtree(os.path.join(__root__, 'dist'))
        except OSError:
            pass

        self.status('Building Source and Wheel (universal) distribution…')
        os.system('{0} setup.py sdist bdist_wheel '
                  '--universal'.format(sys.executable))

        self.status('Uploading the package to PyPI via Twine…')
        os.system('twine upload --verbose dist/*.whl')

# -------------------------------------------------------------------------------
# Upload
# -------------------------------------------------------------------------------


class IncreaseVersionCommand(CustomCommand):
    """Support setup.py increaseversion."""

    description = 'Increase the package version.'
    user_options = []

    def run(self):
        self.status('Change version number…')
        increase_version()

# -------------------------------------------------------------------------------
# Upload
# -------------------------------------------------------------------------------


class TagVersionCommand(CustomCommand):
    """Support setup.py increaseversion."""

    description = 'Increase the package version.'
    user_options = []

    def run(self):
        self.status('Tag the version number {0}'.format(mymodule.__version__))
        self.status('Pushing git tags…')
        os.system('git tag v{0}'.format(mymodule.__version__))
        os.system('git push --tags')


# -------------------------------------------------------------------------------
# Upload
# -------------------------------------------------------------------------------
class UploadRefCommand(CustomCommand):
    """Support setup.py upload_ref."""

    description = 'build and upload to gitlab'
    user_options = []

    def run(self):
        self.status('Build and upload to gitlab the package')
        from pygereference import release
        release.gitlab_make_release(os.path.join(__root__, "build"),
                                    os.path.join(__root__, "dist"),
                                    generate_pdf=True,
                                    make_build=False)

# -------------------------------------------------------------------------------
# Upload
# -------------------------------------------------------------------------------


class BuildRefCommand(CustomCommand):
    """Support setup.py build_ref."""

    description = 'Create the folder with all references'
    user_options = []

    def run(self):
        self.status('Build the package')
        from pygereference import release
        release.build(os.path.join(__root__,
                                   "build", mymodule.__package_name__))

# -------------------------------------------------------------------------------
# Upload
# -------------------------------------------------------------------------------


class BuildRefPdfCommand(CustomCommand):
    """Support setup.py build_ref."""

    description = 'Create the folder with all references'
    user_options = []

    def run(self):
        self.status('Build the package')
        from pygereference import release
        release.build(os.path.join(__root__,
                                   "build", mymodule.__package_name__),
                      generate_pdf=True)

# -------------------------------------------------------------------------------
# Merge request
# -------------------------------------------------------------------------------


class MergeRequestCommand(CustomCommand):
    """Support setup.py uploadrelease."""

    description = 'Zip template and upload to gitlab'
    user_options = []

    def run(self):
        self.status('Merge request for {0}'.format(mymodule.__version__))
        from pygereference import release
        release.create_merge_request()

# -------------------------------------------------------------------------------
# Join command
# -------------------------------------------------------------------------------


class BuildPyCommand(setuptools.command.build_py.build_py):
    """Custom build command."""

    def run(self):
        setuptools.command.build_py.build_py.run(self)


# -------------------------------------------------------------------------------
# All setup parameter
# -------------------------------------------------------------------------------
setup(
    name=mymodule.__module_name__,  # pypi name
    version=mymodule.__version__,
    author=mymodule.__author__,
    author_email=mymodule.__email__,
    description=mymodule.__doc__,
    license=mymodule.__license__,
    long_description=__long_description__,
    long_description_content_type='text/markdown',

    url=mymodule.__url__,

    # https://pypi.python.org/pypi?%3Aaction=list_classifiers.
    classifiers=[
        "Programming Language :: Python",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.5",
    ],

    packages=[mymodule.__module_name__],
    package_dir={mymodule.__module_name__: mymodule.__module_name__},

    cmdclass={
        'version_increase': IncreaseVersionCommand,
        'version_tag': TagVersionCommand,
        'merge_request': MergeRequestCommand,
        'build_ref': BuildRefCommand,
        'build_ref_pdf': BuildRefPdfCommand,
        'upload_ref': UploadRefCommand,
        'build_py': BuildPyCommand,
        'upload_pypi': UploadPyCommand,
    },

)
