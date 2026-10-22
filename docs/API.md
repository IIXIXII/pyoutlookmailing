# Python API reference

[Back to the README](../README.md) · [Configuration guide](CONFIGURATION.md)

The package-level API exports `load_conf`, `default_conf`, `compute_conf`,
`send_email`, and `html_img`, together with `__version__` and `__release_date__`.
These functions are loaded lazily. Importing package metadata does not import
the rendering pipeline or start Outlook.

Configuration values are ordinary nested dictionaries. The `Configuration`
alias in `pyoutlookmailing.core` is `dict[str, Any]`. Refer to the
[configuration guide](CONFIGURATION.md) for fields and merge rules. Function
docstrings provide additional detail directly in the editor and through `help()`.

## Prepare an email without Outlook

Run this example from the repository root:

```python
from copy import deepcopy
from pathlib import Path

from pyoutlookmailing import compute_conf, load_conf

configuration = load_conf("examples/mail-with-config.md")
original = deepcopy(configuration)
prepared = compute_conf(configuration)

assert configuration == original
assert prepared["really_send"] is False
Path("preview.html").write_text(
    prepared["email"]["html_body"], encoding="utf-8"
)
```

The preparation pipeline reads Excel lists and Markdown content, applies content
variables, renders Markdown components, and wraps the fragment in the outer email
template. It writes no files itself and performs no Outlook operations.

## Public functions

### `load_conf(filename, folder=".", *, preferences=None, use_preferences=True, profile=None) -> Configuration`

Load a YAML configuration or a Markdown file with embedded configuration.
`filename` and `folder` accept strings or path-like objects. A relative filename
is searched under the current directory and then `folder`, checking the root,
`conf`, and `mails` in each location. An absolute filename is checked directly.

Returns a new dictionary with common user preferences, the selected profile,
includes, the adjacent local override, resolved paths, and source metadata.
It does not render content or import Excel addresses.
Missing files raise `FileNotFoundError`; invalid structure or include cycles
raise `ValueError`. YAML parsing and file-reading errors propagate.

`preferences` selects an explicit Upref YAML file. Otherwise lookup uses the
absolute `PYOUTLOOKMAILING_PREFERENCES` environment override, then Upref's platform
user directory. `profile` overrides the campaign's top-level profile selector.
`use_preferences=False` bypasses the store and the campaign selector; it cannot
be combined with an explicit `preferences` or `profile`.
Preference storage failures raise `upref.UprefError`; invalid common settings or
unknown profiles raise `ValueError`. See [common preferences](PREFERENCES.md).

The returned configuration includes any inherited `really_send` and
`to.individual_email` defaults. Explicit campaign values override those defaults;
`compute_conf` applies explicit `--send-mail` options afterwards. Shared delivery
addresses remain disallowed; empty `cc`/`bcc` defaults do not add recipients.

### `default_conf() -> Configuration`

Return a fresh configuration loaded from the packaged `default.conf`. It contains
sample content, empty recipient lists, and draft mode. It can be passed directly
to `compute_conf` for rendering. Add recipients before delivery.

This function does not load user preferences or select a profile.

This sample is not automatically merged into `load_conf` results. You can also
replace its subject and content before preparation:

```python
from pyoutlookmailing import compute_conf, default_conf

configuration = default_conf()
configuration["email"]["subject"] = "Example"
configuration["email"]["content"] = {"txt": "Hello **everyone**."}
prepared = compute_conf(configuration)
assert "<strong>everyone</strong>" in prepared["email"]["html_body"]
```

### `compute_conf(conf, cmd_line_args=None) -> Configuration`

Prepare and return a **deep copy** of `conf`; always use the returned value.
The result contains rendered `email.content` and complete `email.html_body`
strings. Missing `really_send` defaults to `False`, and the default outer
template is `email.html`.

`cmd_line_args`, when supplied, is an object with optional `conf_filename` and
`send_mail` attributes. Use the CLI values `"yes"`, `"no"`, or `"conf"` for
`send_mail`; `"yes"` and `"no"` override the configuration flag. For example:

```python
from types import SimpleNamespace

from pyoutlookmailing import compute_conf, load_conf

configuration = load_conf("examples/mail-with-config.md")
prepared = compute_conf(configuration, SimpleNamespace(send_mail="no"))
assert prepared["really_send"] is False
```

Missing or invalid email fields raise `ValueError`. File, YAML, Excel, and Jinja
errors propagate. Preparation is not a complete delivery check: recipient
exclusions, attachment existence, and Outlook account selection are handled at
delivery time. Recompute from the original configuration when changing content.

### `send_email(conf) -> Configuration`

Deliver a **prepared** configuration, normally the result of `compute_conf`.
Returns the original dictionary unchanged. `really_send=False`, or its absence,
saves drafts; `True` sends messages. The flag must be a boolean.

This function accesses Outlook. It validates recipients, exclusions, subject,
HTML body, and attachment paths before creating the first item. Individual mode
creates one item per To address and repeats Cc/Bcc on each item. Missing files
raise `FileNotFoundError`; invalid delivery fields raise `ValueError`.
Unavailable COM support raises `RuntimeError`, and Outlook errors propagate.
Messages already saved or sent are not rolled back if a later item fails.
Unloaded Excel blacklist settings raise `ValueError`: call `compute_conf` first.
Delivery logs include recipient addresses and the addresses removed by `not_to`.

To create drafts explicitly, the delivery call is:

```python
from pyoutlookmailing import compute_conf, load_conf, send_email

configuration = load_conf("examples/mail-with-config.md")
configuration["really_send"] = False
send_email(
    compute_conf(configuration)
)  # Creates real Outlook drafts on Windows.
```

Use preview or preparation alone when no Outlook operation is intended.

### `html_img(filename) -> str`

Read a local file and return an HTML `<img>` tag containing a Base64 data URL.
`filename` accepts a string or path-like object. The MIME type is inferred from
the filename, with `application/octet-stream` as the fallback. File validation
and reading errors propagate. This embeds image data directly and does not use
Outlook `cid:` attachments.

## Preparation helpers

Import these helpers from `pyoutlookmailing.core`. Most applications only need
the package-level functions above.

| Function | Result and side effects |
| --- | --- |
| `read_yaml(filename)` | Read an exact file, includes, and local override; no initial directory search. Supports embedded Markdown as well as YAML. |
| `path(*paths)` | Return a normalized path using legacy **leaf-first** order. An absolute component stops further joining. No existence check. |
| `expand_paths(data, root)` | Return a copy of a paths mapping with absolute values. Nested mappings may define their own roots. |
| `email_excel_list(xl_filename, xl_column, folders=None)` | Return normalized unique addresses from one or more columns on the first worksheet. Blank and non-string cells are skipped. |
| `read_excel_list(conf)` | Merge imported recipients with manual lists **in place**; return the same object. Successful imports consume the Excel keys. |
| `read_content_filename(conf)` | Read content files, strip embedded configuration, and apply ordinary content variables **in place**. |
| `md2html(md_content, env, context)` | Return the Markdown body fragment using a `GenerationEnvironment` and email context; no outer template. |
| `txt2html(conf, env)` | Replace `content.txt` mappings with HTML strings **in place**. |
| `htmlbody(conf, env)` | Render the outer template into `email.html_body` **in place**. |
| `new_email(conf)` | Compatibility wrapper around the Outlook mail-item factory described below. |

The mutating helpers may leave earlier sections updated if a later section
fails. `compute_conf` protects callers by copying before invoking them.

`pyoutlookmailing.files.find_file(filename, folders=(), subfolders=("",))`
returns the resolved `Path` of the first matching file. It checks roots and
subfolders in the given order, without recursion. Relative filenames require
search roots; the helper itself does not add the working directory.

`pyoutlookmailing.embedded.split_configuration(text, *, required=False)` returns
`(configuration, body)`. If no header exists, configuration is `None`, unless
`required=True`, which raises `ValueError`. Invalid declarations also raise
`ValueError`. This parses text only; it does not resolve paths or load includes.

## Rendering extensions

`GenerationEnvironment(configuration)` in `pyoutlookmailing.genenv` stores the
configuration by reference and builds a Jinja environment from its required
`paths` mapping. Its `template_conf` property returns that same configuration;
its `jinja_env` property can be replaced with a custom Jinja environment.

`get_default_jinja_env(template_paths_conf)` searches configured `jinja` and
`template` directories before packaged templates. It enables autoescaping for
`.html`, `.xml`, and `.j2` files and exposes:

| Name | Template use |
| --- | --- |
| `paths` global | The supplied paths mapping, held by reference. |
| `current_date` global | Callable `pymdtools.common.today_utc`. |
| `markdown` filter | Render with the default pymdtools parser, escaping authored HTML; does not select branded renderers. |
| `debug` filter | Print a value to the console and return an empty string. |

`pyoutlookmailing.renderer.create_markdown(jinja_env, context)` returns a callable
Mistune parser with tables, strikethrough, footnotes, and bare-URL links. It uses
`RendererDispatch` to close heading sections and select component renderers.
It can be reused sequentially; its mutable state is not intended for concurrent
rendering. Raw HTML, Outlook conditional comments, and VML are preserved.

The built-in renderer registry contains `default`, `model:fi`, `model:apt`, and
`model:unfold`, plus the aliases `model-fi`, `model-apt`, and `model-unfold`.
Names are case-insensitive. An email context such as `{"model": "unfold"}` selects
the corresponding renderer. Heading comments such as `<!-- model:unfold -->`
select a renderer for that section and nested headings. Unknown selections are
ignored; selecting multiple registered renderers at once raises `ValueError`.

`RendererGenerator.register(name, creator)` registers or replaces a factory
globally. The factory accepts `jinja_env` and `context` keyword arguments and
returns a `RendererDefault`-compatible object. For example:

```python
from pyoutlookmailing import compute_conf, default_conf
from pyoutlookmailing.renderer import RendererDefault, RendererGenerator


class CompactRenderer(RendererDefault):
    """Use compact paragraphs with the standard heading and link components."""

    # --------------------------------------------------------------------------
    def paragraph(self, text):
        """Wrap already rendered inline HTML in a compact paragraph."""
        return f'<p style="margin:0">{text}</p>\n'


# -----------------------------------------------------------------------------
def create_compact(*, jinja_env, context):
    """Create a compact renderer; this implementation needs no email context."""
    return CompactRenderer(jinja_env)


RendererGenerator.register("model:compact", create_compact)
configuration = default_conf()
configuration["email"].update(
    model="compact", content={"txt": "Hello **everyone**."}
)
prepared = compute_conf(configuration)
assert '<p style="margin:0">' in prepared["email"]["content"]
```

Component signatures retain the legacy argument order:
`header(text, level, raw=None)` returns an opening/closing pair;
`paragraph(text)`, `table(header, body)`, `link(link, title, text)`, and
`image(src, title, text)` return HTML strings. Text arguments already contain
rendered inline HTML. `RendererDispatch` adapts these signatures to Mistune 3.
The historical names `ContextManagment`, `JinjaEnvManagment`, and
`change_renderer_on_instrcution` are retained for compatibility.

## Outlook integration and command entry points

`pyoutlookmailing.outlook.new_email(conf)` dispatches Outlook and returns an
unsaved mail item. Optional `conf["from"]` selects an exact, case-insensitive
SMTP account match; it raises `ValueError` if that account is absent. This helper
does not fill message content, save, or send.

`pyoutlookmailing.outlook.deliver(conf, *, mail_factory=new_email)` implements
delivery and returns the original configuration unchanged. Tests can inject a
factory receiving a configuration copy and returning an Outlook-compatible fake
with recipient, subject, HTML, attachment, `Save`, and `Send` members. Importing
the module alone does not start Outlook.

For `cid:` image references, delivery resolves and deduplicates local files
before creating any message. It then generates unique ASCII Content-IDs per
message, rewrites the matching HTML references, and sets the attachment's
Content-ID, MIME type, rendered-in-body flag, and hidden flag. Image references
and metadata are in place before assigning `HTMLBody`. The input configuration
and preview HTML keep their original filename-based references. Tests verify
the matching IDs through MIME serialization without accessing a real Outlook
session; received-message rendering still depends on Outlook's MIME export and
the recipient's client.

Rendered-in-body and hidden flags are optional refinements. If Outlook rejects
one with `E_ACCESSDENIED`/`MAPI_E_NO_ACCESS` or `MAPI_E_NO_SUPPORT`, delivery logs
the property and filename and skips that flag for the remaining messages in
that call. The nested COM `excepinfo` SCODE is inspected when present. A later
delivery call retries capability detection. Required Content-ID/MIME failures
and unrelated exceptions still propagate, without retrying a message's send.

`pyoutlookmailing.cli.get_parser_for_command_line()` builds the argument parser.
`pyoutlookmailing.cli.main(argv=None)` accepts arguments without the executable
name, or reads `sys.argv` when omitted. It returns `0` on success and `1` on
processing failure. Argparse raises `SystemExit(0)` for help/version and
`SystemExit(2)` for invalid arguments. Preview writes UTF-8 HTML; other normal
invocations perform Outlook delivery.

For Windows integration, `windows_association.registration(pythonw, editor, launcher=None)`
builds registry entries without writing them. `install(reg, entries)` and
`uninstall(reg, entries)` apply per-user changes with ownership checks.
`windows_launcher.launch(batch, source)` starts the batch script and waits for
its exit code. Use the documented [Windows commands](WINDOWS.md) for setup;
these helpers' docstrings describe registry behavior and error handling.
