# Windows launchers and file associations

[Back to the README](../README.md) · [Configuration guide](CONFIGURATION.md)

The `.mailmd` format uses the same Markdown and leading configuration comments as
`.md`. Its distinct extension allows double-click processing while keeping the
normal Markdown editor association. `Invitation.mail.md` still has the `.md`
extension; use `Invitation.mailmd` for the association described here.

## Install or remove double-click support

First [install the project](../README.md#install-from-source) in its Python
environment. From the repository, run or double-click:

| Script | Action |
| --- | --- |
| `scripts\install_mailmd.bat` | Install or update the current user's `.mailmd` association. |
| `scripts\uninstall_mailmd.bat` | Remove this project's association. |
| `scripts\run_mailmd.bat` | Process the source file supplied as its first argument. |

The scripts resolve paths from their own directory. They use the repository's
`.venv\Scripts\python.exe`, with support for the older sibling environment
`pyoutlookmailing.venv`. On another computer, install Python and project
dependencies first, then run the installer from that checkout.

The equivalent Python commands, run from the repository root, are:

```powershell
.\.venv\Scripts\python.exe -m pyoutlookmailing.windows_association install --launcher scripts/run_mailmd.bat
.\.venv\Scripts\python.exe -m pyoutlookmailing.windows_association uninstall
```

Installation applies to the current Windows account and needs no administrator
rights. An existing `.mailmd` association owned by another application is
reported and preserved. The installer does not change Windows' protected
`UserChoice` setting. Uninstallation removes only entries belonging to this
project; it retains `.mailmd` documents and unrelated registry values.

Python and launcher paths are stored at installation time. Run the installer
again after moving the project or replacing its environment. To inspect the
planned entries without changing the registry:

```powershell
scripts\install_mailmd.bat --dry-run
```

The legacy `scripts\mailmd_association.bat` remains a compatible installation
shortcut. The Python association command also supports installation without
`--launcher`; that form launches the Python CLI directly rather than the
interactive batch console.

## Process a `.mailmd` file

Double-clicking a registered file opens the batch console. It respects the
configuration's `really_send`: `true` sends, while `false` or absent saves
drafts. An adjacent `.local.conf` override is also loaded.

Common [Upref preferences](PREFERENCES.md) load automatically for the Windows
account, including a profile selected with `var(conf/profile)`. The console logs
the preference file when it applies settings. No association reinstall is needed.

The console displays the file, command, and result, then offers another run after
either success or failure. The existing Windows prompts are in French:
press **O** (`Oui`, yes) to run again or **N** (`Non`, no) to close the console.
Each run rereads the source, configuration, and common preferences, so you can edit them before
retrying. Command-line options are retained. With `really_send: true`, choosing
**O** performs another send.

The right-click action **Modifier le Markdown** (Edit Markdown) opens the source
in Notepad. Windows 11 may place it under **Show more options**.

The launcher also accepts normal CLI options:

```powershell
scripts\run_mailmd.bat "examples\mail-with-config.mailmd" --preview "preview.html"
```

For a preview without the interactive batch loop:

```powershell
.\.venv\Scripts\python.exe -m pyoutlookmailing --conf examples/mail-with-config.mailmd --preview preview.html
```

The [example file](../examples/mail-with-config.mailmd) uses `really_send: false`.
Preview generates HTML only, independently of that flag.

## Campaign launchers

The generated campaign `.bat` files select the matching `.conf` if it exists;
otherwise they select the matching `.md`. Passing `--conf` directly to Python
always selects the named source. See [configuration selection](CONFIGURATION.md#includes-local-overrides-and-content-variables).

From the repository root, generate missing launchers with:

```powershell
scripts\generate_launchers.bat --once
```

The generator scans `mails/*.md` and creates a launcher when a matching `.conf`
exists or the Markdown contains embedded `var(conf/...)` or legacy `var(conf)`
configuration. Existing launchers are preserved. `--once` performs a single pass.

For background on Windows behavior, see Microsoft's documentation on
[filename extensions](https://learn.microsoft.com/en-us/dotnet/api/system.io.path.getextension)
and [per-user file type registration](https://learn.microsoft.com/en-us/windows/win32/shell/fa-file-types).
