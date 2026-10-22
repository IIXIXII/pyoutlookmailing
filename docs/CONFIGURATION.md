# Configuration guide

[Back to the README](../README.md) · [Python API](API.md) · [Windows launchers](WINDOWS.md)

Configuration can be a YAML file, normally named `campaign.conf`, or leading
comments in a `.md`, `.markdown`, or `.mailmd` file. Text files must use UTF-8;
a byte order mark (BOM) is accepted.

## YAML configuration

This complete example can be previewed without Outlook:

```yaml
really_send: false
to:
  list: [recipient@example.org]
email:
  subject: Example
  content:
    txt: "Hello **everyone**."
```

Save it as `campaign.conf` and run:

```powershell
python -m pyoutlookmailing --conf campaign.conf --preview preview.html
```

To read a separate Markdown body, use `email.content.filename: campaign.md`.
If `email.content` is absent or an empty mapping, a YAML configuration uses the
Markdown file with the same stem. A configuration loaded from Markdown uses its
own body instead. The default outer template is the packaged `email.html`.
`email.subject` must be a nonempty string after content variables are applied.

## Configuration inside Markdown

Place configuration comments before the message body:

```markdown
<!-- var(conf/really_send) = false -->
<!-- var(conf/to/list) = "[Recipient](mailto:recipient@example.org)" -->
<!-- var(conf/to/list) = "another@example.org" -->
<!-- var(conf/email/subject) = "Invitation" -->

Hello,

You are invited to our **next meeting**.
```

The slash separates nested configuration keys. Every YAML section can be
represented this way, including `from`, `paths`, recipients, and `email`.
Configuration comments are removed before rendering and do not appear in the
resulting message. Blank lines and other leading comments may separate them.
Comments after the body begins, including examples inside fenced code blocks,
are not configuration declarations.

### Values and lists

Quote strings with single or double quotes. Quoted strings use pymdtools escapes,
including `\n`, `\t`, `\\`, `\"`, and `\'`. For Windows paths, prefer forward
slashes (`"C:/dev/images"`) or doubled backslashes (`"C:\\dev\\images"`).
Write JSON booleans `true` and `false`, numbers, `null`, `[]`, and `{}` without
quotes. A quoted `"false"` remains a string and is invalid for `really_send`.

These paths append one item per declaration, preserving document order:

| Repeated path | Item |
| --- | --- |
| `to/list`, `cc/list`, `bcc/list`, `not_to/list` | Email address or Markdown `mailto:` link. |
| Recipient section's `excel_column_name` | Excel column name. |
| `email/attachments` | Attachment filename. |
| `paths/includes` | Configuration filename. |
| `paths/base_search` | Resource search directory. |

For example:

```markdown
<!-- var(conf/to/excel_file) = "contacts.xlsx" -->
<!-- var(conf/to/excel_column_name) = "Email" -->
<!-- var(conf/to/excel_column_name) = "Other email" -->
<!-- var(conf/email/attachments) = "agenda.pdf" -->
<!-- var(conf/email/attachments) = "map.pdf" -->
<!-- var(conf/paths/img) = "../template/img" -->
```

A recipient declaration contains one address. For `[Name](mailto:address@example.org)`,
only the target address is used; the label is ignored. Query parameters such as
`?cc=...` and URL fragments are rejected. Duplicate addresses are removed during
recipient preparation. An append declaration with `[]` adds nothing and does
not clear earlier items.

Single-value fields such as `email/subject` must be unique. Numeric list paths
such as `conf/custom/0/name` remain available for custom lists and objects;
indices must be consecutive from zero. A list cannot mix numeric indices and
append declarations. Conflicting parent and child paths are also rejected.

The legacy `var(conf)` comment containing a YAML mapping is supported, but cannot
be mixed with `var(conf/...)` declarations in the same header.

See [mail-with-config.md](../examples/mail-with-config.md) and
[mail-with-config.mailmd](../examples/mail-with-config.mailmd) for runnable examples.

## Includes, local overrides, and content variables

Configuration is merged in this order, with later scalar values taking precedence:

1. Common Upref settings and the optional selected profile; see
   [common preferences](PREFERENCES.md).
2. Files in `paths.includes`, in list order, including their own recursive includes.
3. The main configuration file.
4. The adjacent local override: `campaign.local.conf` for `campaign.conf`,
   `campaign.md`, or `campaign.mailmd`. Other YAML suffixes use `.local` followed
   by that suffix, such as `campaign.local.yaml`.
5. Ordinary Markdown variables, such as `<!-- var(subject) = "New subject" -->`,
   applied to the corresponding content section, normally `email`.

Nested mappings merge recursively. Lists concatenate between campaign files;
an empty override list does not erase an inherited campaign list. Campaign lists
replace common preference lists, including when empty. Include cycles raise an
error. Only the main
file's adjacent local override is loaded automatically; included files do not
automatically load their own local overrides.

Content variables such as `var(subject)` and `var(model)` retain the pymdtools
syntax and must have unique names. They cannot replace `content`, `html_body`, or
`attachments`. Explicit `--send-mail yes` or `--send-mail no` overrides the final
top-level `really_send` value. Upref may supply `really_send` and
`to.individual_email` defaults; campaign values override them. If no layer
defines `really_send`, it defaults to `false`.

Passing `--conf campaign.md` selects that file's embedded configuration even if
`campaign.conf` also exists. When a selected `.conf` reads a Markdown body,
embedded `conf/...` comments are stripped from the body but do not replace the
selected configuration. Malformed embedded headers still produce parsing errors.

## Paths and file lookup

`paths.root` is relative to the file that defines it. Other entries in that
file's `paths` mapping are relative to its root. Include filenames are always
relative to the including file's directory, independently of `paths.root`.

After loading, `paths.conf_filename` and `paths.conf_folder` identify the main
source. Unless explicitly configured, `paths.base_search` contains the main
file's directory followed by the resolved root, and `paths.img` is the main
file's directory.

Lookup tries each search root in order, then the following subdirectories within
that root. It stops at the first existing file and never searches recursively.
Absolute filenames are checked directly.

| Resource | Search roots | Subdirectories, in order |
| --- | --- | --- |
| Configuration passed to `load_conf` | Working directory, then optional `folder` | Root itself, `conf`, `mails` |
| Markdown body | `paths.base_search` | Root itself, `conf`, `files` |
| Excel workbook | `paths.base_search` | Root itself, `excel`, `xl` |
| Attachment | `paths.base_search` | Root itself, `conf`, `files` |
| `cid:` image | `paths.img`, then `paths.base_search` | Root itself, `img`, `conf`, `files` |

Jinja searches `paths.jinja`, then `paths.template`, then packaged templates.
These are template directories, separate from `paths.base_search`.

## Recipients, sender, and delivery

Use `to`, `cc`, `bcc`, and `not_to` sections. Each can contain a `list`, Excel
settings, or both:

```yaml
really_send: false
from: sender@example.org
to:
  list: [recipient@example.org]
  excel_file: contacts.xlsx
  excel_column_name: [Email, Other email]
  individual_email: true
cc:
  list: [copy@example.org]
bcc:
  list: [archive@example.org]
not_to:
  list: [excluded@example.org]
```

Excel import reads the first worksheet. It ignores blank and non-string cells,
checks column names, then trims, lowercases, validates, and deduplicates addresses.
Manual addresses come before imported addresses. If `excel_column_name` is
absent, a nonempty manual `list` is used alone even when `excel_file` remains
configured; an empty manual list without a column selector is an error.
For `not_to`, both Excel settings are required: an incomplete Excel blacklist
raises an error even when manual exclusions exist. Workbooks are read once per
preparation, shared by recipient and exclusion imports, then reread on the next run.

Exclusions apply to To, Cc, and Bcc. Deduplication occurs within each category.
Comparison uses complete addresses, ignoring case and surrounding whitespace;
it does not infer aliases, expand Outlook distribution lists, or match domains.
Manual exclusions and Excel blacklist sources accumulate across Upref defaults,
the selected profile, includes, the main file, and its local override. An empty
local list or `null` cannot clear inherited exclusions. Each source's workbook
and columns are retained, even when another layer names a different workbook.
Relative source lookup first uses that layer's folders, then campaign search roots.

Before delivery, logs show the resolved Excel filename, selected columns and
address count, followed by the blacklist size and removal counts for To/Cc/Bcc.
Each removed address is logged as `Exclu (not_to) : address [category]`.
The success log places the destination immediately after `envoyé` or
`brouillon enregistré`, including Cc/Bcc labels where present. For example:

```text
INFO: Blacklist not_to : 1 adresses ; exclusions To=1, Cc=0, Cci=0
INFO: Exclu (not_to) : blocked@example.org [to]
INFO: Message 1/1 : envoyé allowed@example.org
```

The legacy uppercase `Bcc` section is accepted when lowercase `bcc` is absent
or `null`.
At least one recipient must remain after exclusions. With
`to.individual_email: true`, each remaining To address gets a separate message;
Cc and Bcc are repeated on every message, and at least one To address is required.

An optional `from` address must match a configured Outlook account's SMTP
address exactly, ignoring case. A missing match raises an error before a message
is created. Omitting `from` uses Outlook's default account.

Recipient and attachment checks happen before the first message is created.
Messages are saved or sent sequentially. A later Outlook failure does not undo
earlier deliveries; the application stops and does not retry automatically.

## Templates, images, and attachments

The wheel includes a basic standalone template. FI, APTITUDE, and UNFOLD templates
and their images remain in the repository. For a configuration in `mails/`:

```yaml
paths:
  root: ../
  jinja: template/jinja
  template: template/html
  img: template/img
email:
  model: unfold
  template: unfold v2.html
```

The outer template receives the prepared `email` fields as its context. `content`
contains the rendered HTML fragment. Renderer models are `fi`, `apt`, and
`unfold`; omitting `model` uses the default components. Heading-level renderer
instructions can also select a model, for example `# Heading <!-- model:unfold -->`.
See [Rendering extensions](API.md#rendering-extensions) for component details.

For a configurable registration button, use
`[<!-- link-model=button2 -->Register](https://example.org/register)` in its own
paragraph. See [button parameters and examples](BUTTONS.md) for colors, sizes,
alignment, spacing, typography, and Outlook rendering.

`email.attachments` is a list of filenames. Refer to inline attachments in
Markdown as `![Logo <!-- cid=True -->](logo.png)`. URL-encoded filenames are
decoded for local file lookup. Each resolved image file is attached once per
message, even when referenced through both plain and encoded filenames.

At delivery, the adapter replaces filename-based references with unique ASCII
Content-IDs and sets the matching attachment IDs and MIME types. It also sets
inline/hidden flags when Outlook permits them.
This avoids mismatches caused by spaces, accents, or URL encoding when another
client, such as Gmail, resolves the images. The Markdown filenames and rendering
options do not need to change. Outlook performs the final MIME serialization.
See Microsoft's [inline attachment requirements](https://learn.microsoft.com/en-us/openspecs/exchange_server_protocols/ms-oxcmail/96ee0694-0902-43d2-97d3-40f1fad626e7).

Some Outlook stores refuse changes to `PR_ATTACH_FLAGS` (`0x37140003`) or the
hidden flag. In that case, the console reports a warning and retains the
matching Content-ID and MIME type; it does not stop solely for those optional
flags. Required-property errors and other failures still stop delivery.

HTML previews retain filename-based `cid:` references, so these images may not
display in a browser. The `inline=true` rendering instruction instead embeds a
`data:` URL; it does not create an inline MIME attachment. Use `cid=True` for
the attached-image delivery path described here.

Set an image's width as a percentage of its containing element with a `width`
instruction inside the alternative text:

```markdown
![Agenda <!-- cid=True --><!-- width=80% -->](<agenda with spaces.png>)
```

The image keeps its aspect ratio and its CSS width is capped at 100% of the
container. This works with CID, remote, and Base64 images, using either the
repository's `image.j2` or the packaged fallback. Without `width`, the existing
image sizing is preserved. Standalone images are centered by default in both
templates, with or without `width`. Their containing table cell has an explicit
HTML alignment, so centering does not rely only on CSS image margins. The image
is not wrapped in a justified paragraph. This also applies to clickable images.
Use `<!-- align=left -->` or `<!-- align=right -->` to override the default;
`<!-- align=center -->` explicitly selects centering. Images within a paragraph
of text keep their surrounding text rather than creating a separate image block.

Jinja autoescapes ordinary variables in `.html`, `.xml`, and `.j2` templates;
generated HTML fragments are marked as trusted. Authored raw HTML is preserved
for Outlook layouts. See [Security](SECURITY.md) for the input trust assumptions.
