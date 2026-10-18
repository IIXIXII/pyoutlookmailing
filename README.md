# pyoutlookmailing

Prepare email from Markdown and Jinja templates, then save drafts or send messages
through **classic Outlook on Windows**. HTML previews and automated tests run
without Outlook, including on Linux.

Python **3.11 or later** is required. The rendering engine uses pymdtools 3 and
Mistune 3; common user preferences use Upref 2. Documentation and Python
docstrings are maintained in English.

## Install from source

Run these commands from the repository root. On Windows, use PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --config-settings editable_mode=compat -e ".[dev]"
```

On Linux or macOS, use a POSIX shell:

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --config-settings editable_mode=compat -e '.[dev]'
```

The commands below assume this environment is active. If PowerShell activation
is unavailable, replace `python` with `.\.venv\Scripts\python.exe` in each command.
The `dev` extra installs testing, formatting, type checking, and packaging tools;
omit it for runtime use only.

Dependencies are declared in [pyproject.toml](pyproject.toml).
[requirements.txt](requirements.txt) installs the same project, while
[requirements-dev.txt](requirements-dev.txt) includes development tools.
For the runtime versions recorded on Windows/Python 3.14, install with
`python -m pip install -c constraints-windows-py314.txt .`. These constraints are
specific to that environment; they are not a universal lock file.

## Try an HTML preview

```powershell
python -m pyoutlookmailing --conf examples/mail-with-config.md --preview preview.html
```

Open `preview.html` in a browser. Preview mode renders the message without opening
Outlook or creating a draft. The output must end in `.html` or `.htm`, and its
parent directory must already exist.

The [Markdown example](examples/mail-with-config.md) contains both configuration
and content:

```markdown
<!-- var(conf/really_send) = false -->
<!-- var(conf/to/list) = "[Recipient](mailto:recipient@example.org)" -->
<!-- var(conf/email/subject) = "Invitation" -->

Hello,

You are invited to our **next meeting**.
```

## Save drafts or send messages

On Windows with classic Outlook configured, adapt the recipient in the example
and run:

```powershell
python -m pyoutlookmailing --conf examples/mail-with-config.md --send-mail no
```

`--send-mail no` saves drafts. Delivery behavior is explicit:

| Option | Behavior |
| --- | --- |
| `--preview preview.html` | Write HTML only, regardless of `really_send`. |
| `--send-mail no` | Save Outlook drafts. |
| `--send-mail yes` | Send messages through Outlook. |
| `--send-mail conf`, or omitted | Use `really_send`: `true` sends; `false` or absent saves drafts. |

`--preview` cannot be combined with `--send-mail yes`. Delivery flags in
configuration must be booleans: write `false`, not `"false"`.
Use `python -m pyoutlookmailing --help` for all options. The installed
`pyoutlookmailing` command and `python scripts/mailing.py` use the same CLI.
Errors return a nonzero exit status; `--verbose` includes a traceback.

## Share common preferences

Adapt the example's sender, paths, and profiles, then import it once:

```powershell
python -m pyoutlookmailing.preferences --import examples/preferences.yaml
```

Campaigns automatically load these per-user settings through Upref. Select a
profile with `<!-- var(conf/profile) = "ebw" -->`; keep recipients and
`really_send` in the campaign. Campaign settings override shared values.
Use `--no-preferences` to ignore the store or `--preferences FILE` to select
a portable file. See [common preferences](docs/PREFERENCES.md) for setup and
merge rules.

## Use the Python API

```python
from pathlib import Path

from pyoutlookmailing import compute_conf, load_conf

configuration = load_conf("examples/mail-with-config.md")
prepared = compute_conf(configuration)
Path("preview.html").write_text(
    prepared["email"]["html_body"], encoding="utf-8"
)
```

`compute_conf` returns a copy and performs no delivery. The separate `send_email`
function saves or sends the prepared configuration according to `really_send`.
See the [Python API reference](docs/API.md) for arguments, side effects, and errors.

## Documentation

| Guide | Contents |
| --- | --- |
| [Configuration](docs/CONFIGURATION.md) | YAML and embedded Markdown, overrides, recipients, Excel, templates, attachments. |
| [Common preferences](docs/PREFERENCES.md) | Upref settings, profiles, initialization, priorities, and portable stores. |
| [Python API](docs/API.md) | Public functions, preparation helpers, rendering extensions, and CLI entry points. |
| [Windows launchers](docs/WINDOWS.md) | `.mailmd` double-click support, file associations, and batch launchers. |
| [Development](docs/DEVELOPMENT.md) | Pylance setup, quality checks, tests, packaging, and release commands. |
| [Security and dependencies](docs/SECURITY.md) | Trusted author content and dependency audit history. |
| [Migration audit](docs/AUDIT.md) | Findings, pymdtools migrations, verification, and limitations. |

Markdown, configuration files, and Jinja templates are trusted author inputs.
Raw HTML is retained for Outlook layouts. The package includes a basic email
template; branded templates and images live in the repository's `template/`
directory. Private campaigns and recipient workbooks are excluded from distributions.

## Run checks

```powershell
python -m ruff check .
python -m ruff format --check .
python -m pyright
python -m pytest --cov --cov-report=term-missing
```

Tests simulate Outlook: they do not create real drafts or send messages.
See [Development](docs/DEVELOPMENT.md) for packaging checks and CI details.
