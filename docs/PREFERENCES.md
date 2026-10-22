# Common user preferences with Upref

[Back to the README](../README.md) · [Configuration](CONFIGURATION.md) · [Windows](WINDOWS.md)

Upref 2 stores settings shared by your campaigns in a per-user YAML file.
The application loads it automatically for the CLI, Python `load_conf`, and
`.mailmd` double clicks. It reads the file again on each run without prompting
or writing anything. A missing or empty preference file changes no campaign
behavior. Invalid preferences stop processing with an error.

At the normal INFO log level, each preference load prints its absolute filename
before reading it. This also appears in the Windows batch console:

```text
INFO: Fichier upref (valeurs par défaut) : C:\Users\name\AppData\Local\pyoutlookmailing\preferences.yaml
```

The location remains visible if the file is missing, empty, or invalid. A missing
or empty file gets an additional status message; loading never creates it.
`--preferences FILE` and the environment override are reflected in the logged
location. `--no-preferences` instead logs that Upref preferences are disabled.
Open the displayed file in a text editor to change common defaults, then rerun
the campaign. Explicit campaign values continue to take priority.

## Initialize preferences

From an installed checkout, print the location:

```powershell
python -m pyoutlookmailing.preferences --path
```

On Windows, the usual location is
`%LOCALAPPDATA%\pyoutlookmailing\preferences.yaml`. Upref selects the appropriate
user configuration directory on other platforms.

Adapt [examples/preferences.yaml](../examples/preferences.yaml), optionally
setting `from` to your Outlook account, then import it:

```powershell
python -m pyoutlookmailing.preferences --import examples/preferences.yaml
```

Import validates the whole document before saving it atomically through Upref.
It converts relative resource paths to absolute paths based on the source file,
so moving the settings into your user directory retains their original meaning.
It preserves the source. Existing preferences require explicit `--replace`:

```powershell
python -m pyoutlookmailing.preferences --import examples/preferences.yaml --replace
```

You can subsequently edit the stored YAML file directly. A programmatic update
uses Upref's public API and the same store selection as the application:

```python
from pyoutlookmailing.preferences import get_preferences_store

store = get_preferences_store()
store.update({"from": "sender@example.org"})
```

Stored preferences stay local to the current user. Installing the application
on another computer does not copy them; import the adapted example there too.
Reimport or edit absolute paths after moving the resources.

## Allowed common settings

The document uses the campaign's familiar nested structure:

```yaml
from: sender@example.org
really_send: false
to:
  individual_email: true
cc: null
bcc: null
paths:
  root: C:/dev/pyoutlookmailing
  jinja: template/jinja
  template: template/html
  img: template/img
email:
  template: email.html
profiles:
  ebw:
    email:
      template: std3.html
  aptitude:
    email:
      template: aptitude vff.html
      model: apt
```

Common settings accept `from`, `not_to`, resource `paths`, and presentation fields
under `email`, including `template`, `model`, and custom template variables. They
also accept boolean delivery defaults `really_send` and `to.individual_email`.
`cc` and `bcc` can be `null` or empty mappings, without shared addresses. An optional
`profiles` mapping contains named overrides of these same common fields.
Profile names are nonempty and case-sensitive. There is no implicit active profile.

Recipient addresses, subject, summary, content,
generated HTML, and attachments belong to the campaign and are rejected in
preferences, including profiles. Includes and computed source metadata also
belong to the campaign.

If common settings specify `really_send: true`, a campaign without its own value
sends messages. A campaign's explicit `really_send: false` overrides that default;
`--send-mail no` has the highest priority and saves drafts. If no configuration
layer defines `really_send`, the effective value remains `false`. Preview mode
never delivers, including when the inherited setting is `true`.

The same override rule applies to `to.individual_email`: an inherited `true`
creates one message per allowed To address; a campaign can explicitly set it
to `false`. Disabling preferences with `--no-preferences` ignores these common
delivery defaults too.

Shared `not_to` settings are exclusions only; they cannot add delivery targets.
They accept manual `list` entries, `excel_file`, and `excel_column_name`, using
the [same format as campaign exclusions](CONFIGURATION.md#recipients-sender-and-delivery).
All manual and Excel exclusions accumulate across common settings, profiles,
includes, the campaign, and local overrides. Empty campaign values cannot clear
shared exclusions, and a later workbook does not replace an earlier source.

Global paths are resolved from the preference file's directory and its optional
`paths.root`. Profile paths inherit that global root unless they specify their
own root, which is relative to the preference file. A profile root does not
relocate global paths that have already been resolved. Campaign paths keep
their own defining file's origin.

## Select a profile in Markdown

Keep the existing comment syntax:

```markdown
<!-- var(conf/profile) = "ebw" -->
<!-- var(conf/really_send) = false -->
<!-- var(conf/to/list) = "[Recipient](mailto:recipient@example.org)" -->
<!-- var(subject) = "Invitation | European Business Wallet" -->
<!-- var(summary) = "EBW working session" -->

Hello,

You are invited to our **next meeting**.
```

The profile supplies the shared template, paths, and sender. Campaign declarations
can override them. Ordinary variables such as `subject` and `summary` still go
into `email`. An unknown profile raises an error before rendering or delivery.

For a YAML campaign, use the top-level field `profile: ebw`. Its adjacent
`.local.conf` can override that selection. An explicit `--profile NAME` takes
priority over the campaign's selector.

Try the [profile example](../examples/mail-with-profile.mailmd) without saving
preferences or accessing Outlook:

```powershell
python -m pyoutlookmailing --conf examples/mail-with-profile.mailmd --preferences examples/preferences.yaml --preview preview.html
```

## Merge priorities

Later scalar values take precedence:

1. Common global Upref settings.
2. Selected Upref profile.
3. Campaign includes, in their declared order.
4. Main campaign configuration.
5. Adjacent local override.
6. Ordinary Markdown content variables, applied to the email section.
7. Explicit command options, such as `--send-mail yes` or `--send-mail no`.

Mappings merge recursively. Apart from the additive `not_to` exclusions, lists
in a profile replace global lists. Campaign
lists replace common lists, including when a campaign list is empty. The existing
concatenation rule remains in effect between campaign includes, the main file,
and its local override. Repeated `var(conf/to/list)` declarations still append
one item within that document.

Preferences are applied before generated campaign path defaults. If a campaign
defines a resource path, its value wins over the corresponding common path.
`default_conf()` remains a standalone packaged sample and never loads preferences.
`compute_conf()` only prepares the configuration it receives; it does not load
preferences itself.

## Override or disable the store

Select a portable file for one command:

```powershell
python -m pyoutlookmailing --conf invitation.mailmd --preferences C:/settings/mailing.yaml --preview preview.html
```

For repeated commands or double clicks, set the absolute filename in the
`PYOUTLOOKMAILING_PREFERENCES` environment variable. Relative environment paths
are rejected because the double-click working directory can vary.
`--preferences` takes priority over that variable, which takes priority over
the platform user store. A relative CLI path uses the working directory.

Ignore preferences and the campaign's profile selector for one command:

```powershell
python -m pyoutlookmailing --conf invitation.mailmd --no-preferences --preview preview.html
```

`--no-preferences` bypasses malformed or missing preference files too. It cannot
be combined with an explicit `--preferences` or `--profile`.

The same controls are available through the Python API:

```python
from pyoutlookmailing import load_conf

conf = load_conf("invitation.mailmd", profile="ebw")
portable = load_conf("invitation.mailmd", preferences="settings.yaml")
standalone = load_conf("invitation.mailmd", use_preferences=False)
```
