# Python audit and pymdtools migration

## Migration to pymdtools 3.0.0, 18 October 2026

The latest stable release was verified through the live PyPI package index;
the cached project web page still showed an older release. The published 3.0.0
wheel metadata and sources were inspected before upgrading from 2.0.47.

- Require Python **3.11+**, matching pymdtools 3. Update package classifiers,
  Ruff, Pyright, and the Windows/Linux CI matrix accordingly.
- Require `pymdtools>=3.0.0,<4` and `mistune>=3.3.4,<4`. Regenerate the Windows
  runtime constraints, including chardet 7.7.0 and the Markdown-it dependencies.
- Keep the public `common`, `instruction`, and `mistune_integration` entry points.
  These remain compatible; no application rendering API changes were needed.
- Install only pymdtools' core package. Remove the obsolete pdfkit and pypdf
  packages and their runtime pins, and remove the former CVE audit exception.
  PDF output is now an optional upstream extra, unused by this application.

Local verification on Windows x64 / Python 3.14.2:

- **241 tests pass**, with **87.63% coverage**, including configuration comments,
  Upref profiles, Excel lists, simulated Outlook delivery, and Windows launchers.
- HTML is byte-for-byte identical for the embedded-config example and the EBW
  invitation, BB Milano agenda, and UNFOLD invitation prepared before and after
  the upgrade. Configuration, recipient selection, and send flags are unchanged.
- Ruff, formatting, Pyright, and `pip check` pass.
- The complete pinned runtime dependency tree reports **no known vulnerabilities**
  through `pip-audit`, without advisory exceptions. This scan excludes dev tools.
- Wheel and source distributions build and pass Twine checks. The installed-wheel
  check renders the packaged sample and an Upref profile with pymdtools 3, without
  importing COM or a PDF backend.

Reports and comparison HTML remain in the Git-ignored
`audit-artifacts/pymdtools-migration/` directory. No real Outlook messages or drafts
were created. The updated remote CI matrix has not been run locally.

## Original migration audit

Date: **25 September 2026**. Scope: Python code, configuration, Markdown/Jinja
rendering, Outlook delivery, installation, scripts, tests, and dependencies.
Local environment: Windows x64, CPython 3.14.2.

The following sections record the original migration audit. Their test counts,
dependency versions, and scan results are a historical snapshot, not a report of every
subsequent change. Use the [development commands](DEVELOPMENT.md) to check the
current checkout.

## Outcome

The identified preparation and delivery defects were corrected. The project
gained declarative packaging, an installable CLI, tests isolated from Outlook,
and CI. The migration from **pymdtools 1.0.21 to 2.0.47** used **Mistune 3.3.4**.

Local checks established the migration baseline; they did not certify security
or validate appearance in every Outlook version. One unresolved indirect
dependency advisory was recorded for pdfkit, required by pymdtools but unused
by this application's rendering path. See [Security](SECURITY.md).

## Findings and implemented changes

| Priority | Original finding | Implemented change |
| --- | --- | --- |
| P0 | `send_email` accessed a missing `not_to` key and ignored existing exclusions. | Apply normalized exclusions to To, Cc, and Bcc, with regression coverage. |
| P0 | Confusion between `Bcc`, `bcc`, and `cc`; blind-copy recipients assigned to Cc. | Assign blind copies to `mail.Bcc`; retain the legacy `Bcc` configuration key. |
| P0 | Collected tests could open Outlook and send messages; an indentation error blocked collection. | Use simulated COM and globally block real Dispatch; archive the unfinished experiment as text. |
| P1 | Sender selected by substring, with silent fallback to the default account. | Require an exact, case-insensitive SMTP match and fail before creating an item if absent. |
| P1 | Unvalidated delivery flags, unusable sample configuration, and sending enabled by default. | Supply a renderable sample, default to drafts, validate booleans, addresses, subject, and attachments before delivery. |
| P1 | Individual delivery mutated recipient lists and could leave configuration changed after failure. | Work on a copy and independent recipient groups; stop on failure without automatic retry. |
| P1 | Excel import discarded manual recipients because it checked the wrong variable. | Preserve and deduplicate both sources; report missing columns. |
| P1 | Obsolete `collections.Mapping`, unconditional CLI-argument access, and removed pymdtools helpers. | Use current Python APIs, infer Markdown paths from configuration, use pathlib and pymdtools 2 APIs. |
| P1 | Missing runtime dependencies, inconsistent minimum Python version, and unreliable wheel resources. | Declare metadata in pyproject.toml, require Python 3.10+, bound major dependency versions, mark pywin32 as Windows-only, and verify installed resources. |
| P1 | `pymdtools.mistunege` removed upstream. | Adapt to Mistune 3 with ClosingHTMLRenderer, explicit plugins, legacy components, and heading-section closure. |
| P2 | Rendering always wrote essai.html, eagerly imported COM, and swallowed CLI errors. | Keep preparation free of writes, load COM at delivery, add explicit preview and nonzero error statuses. |
| P2 | Unescaped Jinja components, double-escaped URLs, assumed PNG MIME types, and unclosed file handles. | Enable component autoescaping, distinguish trusted HTML, apply Mistune URL policy, infer MIME types, and use Path.read_bytes. |
| P2 | Missing quality checks and installation docs; outdated dependencies. | Add Ruff, coverage tests, Windows/Linux CI, Dependabot, dependency scans, README, and platform-specific constraints. |
| P2 | Custom setup commands mixed building, publishing, and pushing all tags. | Separate build/version steps, create local tags only, and require a clean checkout before tagging. |

## API migration

| Previous use | Replacement |
| --- | --- |
| `pymdtools.mistunege.Renderer` | `pymdtools.mistune_integration.ClosingHTMLRenderer` |
| `mistune.Markdown(renderer=...)` | `create_markdown_with_close(...)` with table, strikethrough, footnotes, and url plugins |
| Mistune entry point `header(text, level, raw)` | `heading(text, level, **attrs)`, adapting the existing components |
| Mistune entry points `link(url, title, text)` and `image(src, title, text)` | `link(text, url, title=None)` and `image(text, url, title=None)` |
| `escape_link` | `HTMLRenderer.safe_url` with one escaping pass at the Jinja boundary |
| `check_is_file_and_correct_path` | `pymdtools.common.check_file` |
| `search_for_file` and `filename_ext_to_md` | Explicit search roots and `Path.with_suffix` |
| `get_today` | `pymdtools.common.today_utc` |
| Markdown filter through `mdtopdf` | Direct mistune_integration conversion without importing pdfkit |

Two additional differences were checked against existing content:

- Mistune 3 URL-encodes accented image filenames. Local lookup decodes those
  names while retaining valid HTML URLs.
- pymdtools encoding detection could classify UTF-8 Markdown containing emoji
  as binary. Explicit UTF-8-with-optional-BOM reading fixed this without disabling
  binary checks; regression coverage includes accents, emoji, and a BOM.

Bare URLs inside legacy HTML paragraphs remain links, as required by the
existing UNFOLD campaign. Outlook conditional comments and button VML are preserved.

## Behavior changes for callers

- The CLI and batch launchers respect `really_send`: true sends, false or absent
  saves drafts. Explicit `--send-mail yes/no` overrides it. Preview writes HTML
  only. The Python delivery API also respects an explicit boolean.
- `compute_conf` returns a copy; callers must use its return value.
- No automatic `essai.html` output is produced. Use `--preview filename.html`.
- Text sources must be UTF-8. Invalid addresses and missing Excel columns raise
  errors instead of being ignored.
- File lookup uses configuration directories and declared search roots without
  implicit recursion.
- Branded templates and images remain repository resources. The wheel provides
  a generic template; configure resource paths to use campaign layouts.
- The minimum Python version changed from 3.5 to 3.10. Delivery requires classic
  Outlook on Windows; HTML preparation remains independent.

## Verification recorded at the migration baseline

- **69 tests passed**, with **89% coverage**, including branches. All five
  preexisting UNFOLD regression cases passed.
- All **42 Markdown files in mails/** converted successfully. This checked
  conversion, not the appearance of every campaign.
- The current-at-audit UNFOLD configuration was prepared and written to
  `audit-artifacts/unfold-preview.html` without starting Outlook.
- Ruff linting and formatting passed; `pip check` reported no conflicts.
- Source and wheel distributions built and passed Twine checks. An isolated
  installed-wheel check loaded packaged configuration and templates and rendered
  Markdown without importing COM or pdfkit.
- Dependency scanning recorded one distinct remaining pdfkit advisory; the scan
  passed with the documented targeted exception. The local pyoutlookmailing
  package was not available in the queried PyPI advisory database.

Detailed local artifacts were stored in the Git-ignored `audit-artifacts/`
directory. CI was configured for Windows/Linux and Python 3.10/3.14; remote CI
was not triggered as part of that audit.

## Limitations and follow-up

1. Address pdfkit upstream in pymdtools. No installable fixed version was
   identified at the audit date; see the dated [security record](SECURITY.md).
   This follow-up was completed by the pymdtools 3 migration described above.
2. Validate rendering visually in the Outlook client used in production.
   Automated delivery tests use simulated COM; the audit created no real
   messages or drafts.
3. Individual deliveries are not transactional. An Outlook error after several
   successful items cannot undo those items; automatic retry is avoided.
4. The supplied version constraints target the tested Windows/Python 3.14
   environment and do not form a universal lock file with archive hashes.
   Full strict typing of legacy components remained future work. Standard
   Pyright checking was added subsequently; see [Development](DEVELOPMENT.md).

## References used in the original audit

- [PyPA pyproject.toml guide](https://packaging.python.org/en/latest/guides/writing-pyproject-toml/).
- [Mistune 3 migration guide](https://mistune.lepture.com/en/latest/upgrade.html).
- [pymdtools distribution](https://pypi.org/project/pymdtools/): version 2.0.47
  was confirmed through `pip index versions pymdtools` and installed-wheel
  metadata. The web page cache consulted during the audit still showed 1.0.21.
- The installed distribution and local pymdtools sources were inspected to
  verify mistune_integration and common APIs.
- [pdfkit advisory](https://github.com/advisories/GHSA-9g3x-6x24-vf9f).
