#!/usr/bin/env python
# -*- coding: utf-8 -*-
# =============================================================================
# Author: Florent TOURNOIS | License: MIT
# =============================================================================

"""Install the wheel into a temporary target and smoke-test outside the
checkout.
"""

import subprocess
import sys
import tempfile
from pathlib import Path
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]


# -----------------------------------------------------------------------------
def main():
    """Install and smoke-test the newest local wheel in an isolated temporary
    target.

    Require a wheel in dist, check bundled resources and excluded private data,
    then render the packaged default email outside the checkout using pymdtools
    3.
    No Outlook or PDF backend import is allowed. Installation and other failures
    propagate; the temporary target is removed on exit.
    """
    wheels = sorted(
        (ROOT / "dist").glob("pyoutlookmailing-*.whl"),
        key=lambda p: p.stat().st_mtime,
    )
    if not wheels:
        raise SystemExit("Build a wheel first: python -m build")
    wheel = wheels[-1]
    with ZipFile(wheel) as archive:
        files = archive.namelist()
        assert "pyoutlookmailing/default.conf" in files
        assert "pyoutlookmailing/templates/email.html" in files
        assert "pyoutlookmailing/preferences.py" in files
        assert not any(name.startswith(("mails/", "tests/")) for name in files)
    temporary_root = ROOT / "audit-artifacts"
    temporary_root.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix="wheel-", dir=temporary_root
    ) as temp:
        target = Path(temp) / "installed"
        subprocess.run(
            [
                sys.executable,
                "-m",
                "pip",
                "install",
                "--no-deps",
                "--no-index",
                "--target",
                str(target),
                str(wheel),
            ],
            check=True,
        )
        code = """import sys
from importlib.metadata import version
from pathlib import Path
sys.path.insert(0, sys.argv[1])
import pyoutlookmailing as package
from pyoutlookmailing.preferences import get_preferences_store
assert Path(package.__file__).resolve().is_relative_to(
    Path(sys.argv[1]).resolve()
)
assert version('pymdtools').split('.')[0] == '3'
conf = package.compute_conf(package.default_conf())
assert '<strong>tout le monde</strong>' in conf['email']['html_body']
store = get_preferences_store(Path.cwd() / 'preferences.yaml')
store.save({'profiles': {'test': {'from': 'sender@example.org'}}})
source = Path.cwd() / 'campaign.mailmd'
source.write_text(
    '<!-- var(conf/profile) = "test" -->\\n'
    '<!-- var(subject) = "Installed profile" -->\\n\\nHello **everyone**.',
    encoding='utf-8',
)
conf = package.compute_conf(package.load_conf(source, preferences=store.path))
assert conf['from'] == 'sender@example.org'
assert conf['really_send'] is False
assert '<strong>everyone</strong>' in conf['email']['html_body']
assert 'win32com.client' not in sys.modules
pdf_backends = ('pdfkit', 'pypdf', 'playwright')
assert all(name not in sys.modules for name in pdf_backends)
assert 'wx' not in sys.modules
assert not Path('essai.html').exists()
print(
    'Installed wheel: configuration, templates, '
    'Markdown, Upref profiles and import isolation OK'
)
"""
        subprocess.run(
            [sys.executable, "-I", "-c", code, str(target)],
            cwd=temp,
            check=True,
        )


if __name__ == "__main__":
    main()
