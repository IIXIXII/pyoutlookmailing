# Dependencies and trusted inputs

[Back to the README](../README.md) · [Development](DEVELOPMENT.md)

The runtime dependency snapshot was audited on **18 October 2026** after
migration to **pymdtools 3.0.0**. The scan reported **no known vulnerabilities**:

```powershell
python -m pip_audit -r constraints-windows-py314.txt --disable-pip --no-deps
```

The constraints list the complete resolved runtime dependency tree for the
recorded Windows/Python 3.14 environment. This result does not cover development
tools or another environment. CI audits its installed runtime environment with
`python -m pip_audit`, without advisory exceptions.

## Removal of the PDF dependency exception

At the **25 September 2026** audit, `pymdtools 2.0.47` required `pdfkit>=1.0,<2`.
The latest pdfkit release found was `1.0.0`, affected by
[CVE-2025-26240 / GHSA-9g3x-6x24-vf9f](https://github.com/advisories/GHSA-9g3x-6x24-vf9f)
in HTML-to-PDF conversion through `from_string`. The advisory listed no fix.

This project does not generate PDFs. **pymdtools 3.0.0** makes its PDF support
optional and no longer depends on pdfkit. Its PDF extra uses Playwright and
pypdf; this application installs only the core package. The obsolete pdfkit and
pypdf packages were removed from the project's virtual environment and runtime
constraints during migration.

The [CI workflow](../.github/workflows/ci.yml) no longer exempts
`CVE-2025-26240`. The installed-wheel check verifies that email preparation does
not import pdfkit, pypdf, or Playwright. The Markdown filter continues to use
`pymdtools.mistune_integration` directly.

The September audit exception is historical; it is no longer needed by the
runtime dependency tree. PDF generation would require a separate dependency
and integration review if introduced later.

## Changes recorded during the audit

- Locally updated pip to 26.2.1, setuptools to 84.0.0, soupsieve to 2.10, and
  Pillow to 12.3.0 to address findings with available fixes.
- Removed PyPDF2 3.0.1, left over from pymdtools 1, from the environment.
- Removed unused direct dependencies on ics, Pillow, and stringcase.
- Used safe YAML loading, validated delivery flags, checked recipient and
  attachment data before delivery, and rejected missing sender accounts.
- Enabled Jinja escaping, including in .j2 components, and Mistune's scheme
  checks for Markdown links.
- Removed recipient enumeration from ordinary delivery logs.

These recorded local package changes are not a substitute for checking the
dependencies installed in another environment.

## Input trust and data handling

Markdown, Jinja templates, and configuration files are **trusted author inputs**.
Raw HTML is retained for Outlook layouts; this application is not a rendering
service for untrusted third-party content. Template autoescaping does not
sanitize authored HTML or restrict the capabilities of a trusted Jinja template.

Adjacent `.local.conf` files are ignored by Git. Personal campaign sources and
recipient Excel workbooks are excluded from the wheel and source archive.
These packaging rules do not inspect arbitrary files for secrets.

Dependency scanning is not a secrets audit of Git history, a security
certification, or validation of rendering and delivery in a real Outlook client.
See the [migration audit](AUDIT.md) for the original scope and limitations.
