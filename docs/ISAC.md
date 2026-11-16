# ISAC email template

[Back to configuration](CONFIGURATION.md#templates-images-and-attachments)

The ISAC design follows the HTML proposal supplied in the message
`_INTERNET_ Mail ISAC pour PACT.msg`: a navy header, blue section headings,
a white reading area, pale benefit cards, and a contact panel. Matching thin
blue rules appear below the header and at the bottom of the email.
The forwarding note is not part of the example. The original message is not
required at runtime or included in the project.

The outer template is [isac.html](../template/html/isac.html). The `isac`
Markdown renderer supplies inline typography and link styles. Select both in
a `.mailmd` file:

```markdown
<!-- var(conf/paths/root) = ".." -->
<!-- var(conf/paths/jinja) = "template/jinja" -->
<!-- var(conf/paths/template) = "template/html" -->
<!-- var(conf/paths/img) = "template/img" -->
<!-- var(model) = "isac" -->
<!-- var(template) = "isac.html" -->
<!-- var(subject) = "Your email subject" -->
<!-- var(summary) = "Short preview text for the inbox" -->
<!-- var(author) = "Florent Tournois" -->

Dear colleagues,

## 1 · Context

Write the message in **Markdown**, with ordinary lists and links.
```

The paths above assume the mail is in `mails/` or `examples/`. Existing Upref
defaults can supply the same paths. As with the other branded designs, the
HTML and Jinja templates ship in the repository and source archive, rather
than the standalone wheel's minimal template set. No Upref profile is added
or changed automatically.

## Variables

Ordinary `var(name)` comments populate `email.name` as usual. Configuration
values may also be supplied through Upref or `conf/email/...` comments.

| Variable | Default / purpose |
| --- | --- |
| `brand` | `ISAC 4 Identity & Trust Services`; default large header title. |
| `headline` | Brand name; optional override of the large header title. |
| `eyebrow` | `Information Sharing & Analysis Centre`; empty hides the small header line. |
| `subject`, `summary` | Email subject and hidden preheader text. |
| `lang` | `en`; document language. |
| `author` | Empty; an author enables the signature block. |
| `role`, `signoff` | Optional role; closing defaults to `Yours sincerely,`. |
| `contact_email`, `contact_label` | `contact@isac4id.eu` and `Contact`. Empty email hides that line. |
| `website_url`, `website_label` | `https://isac4id.eu` and `isac4id.eu`. Only HTTP(S) URLs produce links; empty hides the website. |
| `website_cta_label` | `More information`; label in the contact panel. |
| `isac_width` | `640` pixels, bounded between 480 and 800. The modern-client layout remains fluid. |
| `isac_navy`, `isac_accent` | `#16254D`, `#3F7FD4`; dark panels and decorative rules. |
| `isac_link`, `isac_text` | `#2A68BD`, `#1A1F2B`; links/section headings and body text. |
| `isac_background`, `isac_panel` | `#F2F4F8`, `#F3F7FD`; page background and light panels. |

The body remains reusable: section titles and numbering belong in Markdown,
not in the outer HTML. The signature and contact panel are generated after
the body; do not duplicate them there unless those template fields are empty.

## Header and footer

The initial text-only header is used: a small uppercase eyebrow above the
large white title on a navy background. Its default title is
`ISAC 4 Identity & Trust Services`; `headline` can override it.

The footer is a 4-pixel blue rule matching the line below the header. It has
no text or website link; contact details and the signature remain above it.

## Benefit cards

Add `layout=cards` inside the first header of a Markdown table to produce one
to three cards. Use exactly one body row. Ordinary tables remain data tables.

```markdown
| <!-- layout=cards -->Threat intelligence | Trusted network | Collective voice |
| --- | --- | --- |
| Shared knowledge of threats. | A trusted community of peers. | A common European voice. |
```

Each header becomes a card title and each body cell its description. Inline
Markdown and links work in both. Cards use presentation tables, with no image,
VML shape, JavaScript, or external font. A mobile media rule stacks the cards
in supporting clients; without it they retain their three-column table layout.
Section headings use the darker link blue for legibility on white.

## Preview and validation

The [complete example](../examples/isac.mailmd) reproduces the proposed email
content and explicitly disables real sending. It selects the `isac` profile
when preferences are enabled. Its resource paths include `examples/`, the
project root, and `mails/`, so a shared blacklist named `mail_list.xlsx` can
also be found under `mails/` when the example runs from `examples/`.

The sample [preferences file](../examples/preferences.yaml) includes an `isac`
profile with an 800-pixel width. Once this profile is in your own Upref file,
preview with your common settings:

```powershell
python -m pyoutlookmailing --conf examples/isac.mailmd --preview audit-artifacts/isac/isac-preview.html
```

The example keeps explicit presentation variables to support a standalone
preview as well. Profile fields not specified in the example, such as
`isac_width`, are inherited. A campaign can inherit all presentation variables
by keeping those settings in its profile and supplying its subject, summary,
recipients, and content locally.

Preview independently of personal settings (the profile selector is ignored):

```powershell
python -m pyoutlookmailing --conf examples/isac.mailmd --no-preferences --preview audit-artifacts/isac/isac-preview.html
```

The example's `really_send: false` also overrides a global `true`: double-click
execution creates a draft. The explicit preview commands above create HTML
only and never access Outlook.

The design uses a fluid 640-pixel container, an Outlook-only fixed-width table,
inline styles, table-cell padding, and explicit background colors. This follows
the [hybrid email layout technique described by Litmus](https://www.litmus.com/blog/understanding-responsive-and-hybrid-email-design).
Essential content and links remain text, including when images are blocked.

Automated checks cover configuration, Markdown rendering, cards, metadata
escaping, links, and preview without delivery. They do not certify the visual
rendering of Outlook, Gmail, or Apple Mail. Outlook can rewrite the HTML during
sending, and some clients adjust colors in dark mode or ignore media queries.
Check the received message in the intended clients before a full campaign.
