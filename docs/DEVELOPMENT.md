# Development guide

[Back to the README](../README.md) · [Python API](API.md) · [Migration audit](AUDIT.md)

Install the project with the `dev` extra and activate its virtual environment as
described in the [installation instructions](../README.md#install-from-source).
Run the following commands from the repository root.

## Editor and type checking

In VS Code, select the project's `.venv` interpreter. On Windows,
`pyoutlookmailing.code-workspace` points to `.venv/Scripts/python.exe` by default.
For another platform, select that environment's Python executable explicitly.

Use the compatibility editable installation so the source directory is exposed
through a static path:

```powershell
python -m pip install --config-settings editable_mode=compat -e ".[dev]"
python -m pyright
```

This avoids relying on setuptools' dynamic editable import hooks for source
discovery. If VS Code retains old import diagnostics after installation, use
**Python: Restart Language Server** from the command palette and confirm the
selected interpreter. See the
[Pylance import troubleshooting guide](https://github.com/microsoft/pylance-release/blob/main/docs/howto/unresolved-imports.md).

The `[tool.pyright]` section in `pyproject.toml` checks the package, scripts,
tests, and `setup.py` in `standard` mode against Python 3.11. The development
extra includes Pyright and its Node runtime; a separate Node installation is
not required for `python -m pyright`.

Pylance, Pyright, and Pylint report different categories of diagnostics. Pylint
docstring and import-style messages are not missing-import errors from Pylance.
Module, class, and function docstrings are written in English. Keep arguments,
return values, mutation, external operations, and significant errors documented
when changing an API. Intentional lazy imports keep metadata and HTML preparation
independent of Outlook.

Start every project Python file with this header, followed by a blank line and
the module docstring (when present). Keep any `from __future__` imports after
the docstring:

```python
#!/usr/bin/env python
# -*- coding: utf-8 -*-
# =============================================================================
# Author: Florent TOURNOIS | License: MIT
# =============================================================================
```

The version generator preserves this header when rewriting `version.py`.
Ruff's `UP009` rule is disabled to retain the explicit UTF-8 declaration.

Add the following separator before every function or method, including nested
functions. Use the same indentation as the definition and place the separator
before any decorators. Shorten indented separators so the complete line,
including indentation, stays within 80 characters:

```python
# -----------------------------------------------------------------------------
```

Keep all Python source lines within **80 characters**, including comments,
docstrings, and strings. Ruff uses `line-length = 80` and checks rule `E501`.
Use implicit string concatenation inside parentheses when splitting a long
message or pattern so that its runtime value remains unchanged.

## Quality checks

```powershell
python -m ruff check .
python -m ruff format --check .
python -m pyright
python -m pytest --cov --cov-report=term-missing --cov-fail-under=80
python -m pip check
```

Ruff checks imports and common code issues, and enforces formatting. To apply
formatting intentionally, use `python -m ruff format` on the changed Python files.
Tests cover configuration, embedded lists, Markdown rendering, CLI behavior,
Outlook delivery with fakes, and Windows launchers and registry operations with
test doubles. The test setup blocks real Outlook dispatch, so tests do not send
messages or create real drafts.

Two regression cases use a local campaign and skip when its private files are
absent from the source archive. Synthetic tests remain available in distributions.
When an existing pytest temporary directory is inaccessible, select a fresh
directory outside the repository:

```powershell
$testTemp = Join-Path $env:TEMP ('pyoutlookmailing-tests-' + [guid]::NewGuid().ToString('N'))
python -m pytest --basetemp $testTemp
```

The [CI workflow](../.github/workflows/ci.yml) defines Windows and Linux jobs
for Python 3.11 and 3.14. It checks formatting, types, tests and coverage,
distributions, and installed-wheel behavior. Dependency auditing runs without
advisory exceptions; see [Security](SECURITY.md).

## Package verification

```powershell
python -m build
python -m twine check dist/*
python scripts/check_wheel.py
```

`check_wheel.py` selects the newest wheel in `dist/`, installs it into an isolated
temporary target without resolving dependencies, and renders its packaged sample.
It checks bundled templates and configuration, private-file exclusions, and the
absence of COM/PDF backend imports during preparation. Dependencies must already
be available in the Python environment running the check.

Package metadata and dependencies live in `pyproject.toml`; `setup.py` is a
compatibility entry point. `MANIFEST.in` includes documentation, examples,
scripts, and synthetic tests in the source archive. Private campaign files and
recipient workbooks are excluded. The wheel contains the generic templates;
branded layouts and images are repository resources.

## Version operations

These are explicit release steps, separate from ordinary checks:

```powershell
python scripts/release.py bump
```

`bump` increments the patch version, sets the release date to today, and updates
`pyoutlookmailing/version.py` and `pyoutlookmailing/version.bat`. Review and commit
the intended release changes before tagging:

```powershell
python scripts/release.py tag
```

`tag` requires a clean checkout, including untracked files, and creates a local
annotated `vX.Y.Z` tag. These commands do not publish packages or push tags.
Builds do not change the version automatically. The Windows build/version
shortcuts invoke these same operations.
