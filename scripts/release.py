#!/usr/bin/env python
# -*- coding: utf-8 -*-
# =============================================================================
# Author: Florent TOURNOIS | License: MIT
# =============================================================================

"""Explicit local version operations, separate from package builds."""

import argparse
import ast
import subprocess
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


# -----------------------------------------------------------------------------
def read_version(root=ROOT):
    """Read the version tuple from root/pyoutlookmailing/version.py using its
    AST.

    No package code is imported. Raise ValueError when __version_info__ is
    absent; file-reading and syntax errors propagate.
    """
    tree = ast.parse(
        (root / "pyoutlookmailing/version.py").read_text(encoding="utf-8")
    )
    for statement in tree.body:
        if isinstance(statement, ast.Assign):
            if any(
                isinstance(target, ast.Name) and target.id == "__version_info__"
                for target in statement.targets
            ):
                return ast.literal_eval(statement.value)
    raise ValueError("Version tuple not found")


# -----------------------------------------------------------------------------
def bump(root=ROOT):
    """Increment the patch version and write version.py and version.bat under
    root.

    Set the release date to today and print the new version. This changes files
    but does not commit, create a tag, build, publish, or push anything.
    """
    major, minor, patch = read_version(root)
    version = (major, minor, patch + 1)
    number = ".".join(map(str, version))
    content = (
        "#!/usr/bin/env python\n"
        "# -*- coding: utf-8 -*-\n"
        "# ======================================="
        "======================================\n"
        "# Author: Florent TOURNOIS | License: MIT\n"
        "# ======================================="
        "======================================\n\n"
        f'"""Package version; managed by scripts/release.py."""\n\n'
        f"__version_info__ = {version!r}\n"
        '__version__ = ".".join(map(str, __version_info__))\n'
        f'__release_date__ = "{date.today().isoformat()}"\n'
    )
    (root / "pyoutlookmailing/version.py").write_text(content, encoding="utf-8")
    (root / "pyoutlookmailing/version.bat").write_text(
        f"@ECHO OFF\nSET VERSION={number}\n", encoding="utf-8"
    )
    print(number)


# -----------------------------------------------------------------------------
def tag(root=ROOT):
    """Create a local annotated version tag in a clean Git checkout.

    Raise SystemExit if tracked or untracked changes exist. Git errors propagate
    as CalledProcessError. The tag is printed but never pushed to a remote.
    """
    status = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    if status.strip():
        raise SystemExit(
            "Commit the release changes before creating a version tag"
        )
    version = ".".join(map(str, read_version(root)))
    subprocess.run(
        ["git", "tag", "-a", f"v{version}", "-m", f"Release {version}"],
        cwd=root,
        check=True,
    )
    print(f"Created local tag v{version}. Inspect it before pushing.")


# -----------------------------------------------------------------------------
def main():
    """Dispatch the requested bump or tag command from sys.argv."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["bump", "tag"])
    args = parser.parse_args()
    {"bump": bump, "tag": tag}[args.action]()


if __name__ == "__main__":
    main()
