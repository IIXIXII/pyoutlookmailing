# Configurable link buttons

[Back to configuration](CONFIGURATION.md#templates-images-and-attachments)

`template/jinja/button2.j2` turns a Markdown link into a registration button.
Use it in a paragraph of its own, separated from surrounding text by blank
lines. It works with the default, FI, APTITUDE, and UNFOLD renderers.

```markdown
[<!-- link-model=button2 -->Register](https://example.org/register)
```

The button is centered by default. Both its visible text and its destination
come from the Markdown link. A quoted Markdown title supplies the tooltip.
The template produces one real HTML link for all clients, including classic
Outlook. Tables supply the alignment, background, decorative border, and equal
padding above and below the label. Text keeps its own line height, independent
of the total button height. A paragraph with zero margins prevents inherited
paragraph spacing from moving the label. No image or VML shape is generated.
The renderer keeps the component outside surrounding Markdown paragraph tags.
The label remains a clickable link; the decorative cell padding is not part
of that link. In classic Outlook, only the text is guaranteed to be clickable.

Select the repository's Jinja directory, for example when the configuration is
in `mails/` or `examples/`:

```markdown
<!-- var(conf/paths/root) = ".." -->
<!-- var(conf/paths/jinja) = "template/jinja" -->
```

These paths may also come from your existing configuration or Upref profile.
Like the branded components, this template ships in the source distribution;
it is not part of the standalone wheel's minimal template set.

## Customized registration button

Instructions belong inside the link label, without quotation marks around their
values. For multiple lines, indent continuation lines by four spaces so the
comments remain inside the Markdown link:

```markdown
[<!-- link-model=button2 -->
    <!-- color=#11458C -->
    <!-- buttontextcolor=#FFFFFF -->
    <!-- bordercolor=#11458C -->
    <!-- border_width=2 -->
    <!-- radius=12 -->
    <!-- button_width=300 -->
    <!-- button_height=60 -->
    <!-- font_size=18 -->
    <!-- font_weight=700 -->
    <!-- align=center -->
    <!-- mt=16 -->
    <!-- mb=24 -->
    Register for the event](https://example.org/register "Open registration")
```

## Parameters

Numeric dimensions are in pixels, written without a unit, such as `300`.
Letter spacing and corner radius also accept decimals. Zero is supported for
padding, margins, radius, letter spacing, and border width.

| Parameter | Default | Purpose |
| --- | --- | --- |
| `color` | `#11458C` | Background color; takes priority over `buttoncolor`. |
| `buttoncolor` | `#11458C` | Alternative background parameter, compatible with UNFOLD settings. |
| `buttontextcolor` | `#FFFFFF` | Text color, repeated on the label to resist inherited link colors. |
| `bordercolor` | Background color | Border color. |
| `border_width` | `1` | Border thickness; `0` removes it. |
| `border_style` | `solid` | `solid`, `dashed`, `dotted`, or `none`. |
| `radius` | `6` | Corner radius where supported; classic Outlook may use square corners. |
| `button_width` | Estimated from the label | Button width, including padding and border. |
| `button_height` | Calculated from line height and padding | Button height, including border; overrides vertical padding when supplied. |
| `padding_x` | `28` | Horizontal padding on each side. |
| `padding_y` | `14` | Vertical padding on each side when height is automatic. |
| `align` | `center` | Button position: `left`, `center`, or `right`. |
| `mt` | `16` | Space above the button, implemented as cell padding. |
| `mb` | `16` | Space below the button, implemented as cell padding. |
| `font_family` | `Arial,Helvetica,sans-serif` | Font stack. |
| `font_size` | `16` | Font size. |
| `font_weight` | `700` | Weight, such as `400`, `700`, `normal`, or `bold`. |
| `line_height` | Font size + `6` | Text line height, at least the font size. Increasing button height adds equal cell padding above and below the text without changing its line height. |
| `letter_spacing` | `0.2` | Spacing between letters. |
| `text_decoration` | `none` | `none` or `underline`. |
| `label` | Markdown link text | Override the visible text with a plain string. |
| `title` | Markdown link title | Override the tooltip. |
| `target` | `_blank` | Link target, such as `_blank` or `_self`. |
| `aria_label` | Plain visible text | Accessible link label. |

For an outline button, use a light background together with matching text and
border colors:

```markdown
[<!-- link-model=button2 --><!-- color=#FFFFFF --><!-- buttontextcolor=#11458C --><!-- bordercolor=#11458C --><!-- border_width=2 -->View the agenda](https://example.org/agenda)
```

The button is intended for a short, single-line label. Automatic width is an
estimate bounded between 140 and 560 pixels before minimum padding requirements;
set `button_width` for a long label or a custom font. Numeric sizes are bounded
so padding and text fit within the requested dimensions. Modern HTML clients
also receive `max-width:100%`; the layout tables include explicit pixel sizes
for Outlook. Font rendering and button dimensions can still vary by client.

VML is deliberately avoided: the previous version used a VML shape in Outlook
and hid its HTML link there. A shape flattened into an image during sending
could therefore lose the only clickable destination. The current version keeps
the anchor visible and the URL in its standard `href` attribute. Classic Outlook
can ignore rounded corners; a rectangular button is preferable to an unlinked
picture. See the padding-based technique in the
[Litmus guide to email buttons](https://www.litmus.com/blog/a-guide-to-bulletproof-buttons-in-email-design)
for cell padding and its rendering limitations.

## Preview the examples

The [example campaign](../examples/button2.mailmd) contains three variations and
explicitly disables real sending. Preview it without loading personal defaults:

```powershell
python -m pyoutlookmailing --conf examples/button2.mailmd --no-preferences --preview button2-preview.html
```

Preview never opens Outlook or creates a draft. The same HTML link is now used
in the preview and in Outlook. Automated tests check that it remains visible
under Outlook's conditional-comment rules and reaches the delivery adapter
without any button image or shape. A real send is not performed by those tests;
visual centering still needs a check in Outlook and in the message received
in Gmail after Outlook has converted the HTML during sending. Passing the
HTML structure checks does not validate those clients' visual rendering.
