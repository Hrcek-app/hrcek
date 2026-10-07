# Styling

Hrček's pages are styled with [Tailwind CSS](https://tailwindcss.com)
v4, compiled ahead of time with the standalone CLI. There is no Node,
npm or JavaScript build in the project: the CLI is a single binary, and
the compiled stylesheet is committed, so a fresh checkout serves styled
pages with no build step at all. You only need the CLI when you change
styles.

## The files

Every directory holding templates must be listed as an `@source` in
the stylesheet, or utilities used only there are never generated. The
collections app was added to that list after the fact; check it when
adding an app.

| File | Role |
|---|---|
| `src/hrcek/core/static_src/hrcek.css` | The source: design tokens and the few component rules. Edit this. |
| `src/hrcek/core/static/css/hrcek.css` | The compiled output. Committed, served by Django, never edited by hand. |

## Installing the CLI

macOS with Homebrew:

```bash
brew install tailwindcss
```

Without Homebrew, download the single binary for your platform from the
[tailwindcss releases page](https://github.com/tailwindlabs/tailwindcss/releases/latest)
(the assets named `tailwindcss-<os>-<arch>`), make it executable, and
put it on your `PATH`.

## Building

After changing `static_src/hrcek.css` or any template:

```bash
tailwindcss --input src/hrcek/core/static_src/hrcek.css \
    --output src/hrcek/core/static/css/hrcek.css --minify
```

Add `--watch` while iterating. Commit the compiled file together with
the source; the two must not drift apart.

If the development server was started before
`src/hrcek/core/static/css/` existed, restart it once — Django's static
file finder only discovers an app's `static/` directory at startup.

## How restyling works

Every color the site uses is a custom property defined once, at the top
of the source file:

```css
:root {
  --surface: #faf8f5;   /* page background */
  --ink: #292521;       /* body text */
  --accent: #234e9c;    /* links, buttons */
  ...
}
```

The `@theme inline` block hands those tokens to Tailwind, which is what
lets templates say `bg-surface`, `text-ink` or `text-muted`. Templates
never use raw palette utilities like `bg-zinc-100`; if you catch one in
review, it is a bug. Restyling the whole site therefore means editing
the token block and recompiling — nothing else.

## Page width

The page frame in `base.html` spans the whole window, with padding
that grows on wider screens. What sits inside it decides its own width
through the `width` block, which holds the classes of `<main>`:

- By default it is `max-w-2xl`: forms and prose keep a readable
  measure, however wide the window.
- A page of entries empties the block (`{% block width %}{% endblock %}`)
  and gets the full width. The entry list, a collection, and a shared
  collection do this. On those pages, paragraphs and forms sitting
  directly in `<main>` are still capped at the same measure; only the
  lists stretch.
- A page with nothing to orient against — a sign-in form, the 404
  page, an error preview — sets `{% block width %}max-w-2xl
  mx-auto{% endblock %}`. Centred, it reads as its own small page
  rather than as content pinned to the left of a wide window. Use this
  for every page that is only a form or a short message and has no
  surrounding navigation of its own to anchor it: signing in, signing
  up, resetting a password, accepting an invitation, and the 404 and
  500 pages. An ordinary working page (the account hub, a collection)
  keeps the default, unmoved block so it lines up with the header.

Inside a collection's entry (a single `.entry-text` div: title, notes,
fields, tags, the "Got it"/"Undo" button), every part keeps the same
gap from the one before it; the parts' own margins are dropped, so no
combination of them adds up to a bigger gap or collapses to none.
`entries/list.html`'s own card is different — see [the entries
list](entries.md#the-entries-list) — a flex column of four named
rows (head, body, labels, actions), spaced the same way but with the
actions row pushed to the card's bottom instead.

`ul.entries` is a grid that fits as many columns of at least 22rem as
the window allows, so one column on a phone and three or four on a
desktop. Every entry opens with its own hairline, because which entry
starts a row depends on the window. Cards sharing a visual row are
stretched to equal height by the grid's own default alignment; that
used to also be shared across each card's internal rows with
`grid-template-rows: subgrid`, which made one entry's long notes push
every other card's labels and actions down to match. It no longer is.

## Flash messages

Django's messages are rendered in exactly one place: `base.html`,
right after the `<h1>` and before `{% block content %}`. No template
has its own `{% if messages %}` block any more; a page that needs one
gets it for free by extending `base.html`. Each message is an
`<li class="{{ message.tags }}">` inside a single
`<ul class="messages" role="status">`, so a success and an error on
the same page are told apart by their tag, not by a separate markup
shape. A message built with `format_html` (a link inviting the reader
back to a wish list, say) renders unescaped, as `{{ message }}` always
has — moving the markup into `base.html` changed nothing about that.

The one exception is `collections/detail.html`'s "came back" notice: it
also looks like a `ul.messages` panel, but it is not a Django message
(it has no tag, and survives a redirect that would clear real
messages), so it stays written out in the template.

Pages follow the system theme unless somebody pins one with the toggle
in the header. The mechanism is the token block again: two dark blocks
redefine the same custom properties, so every rule and utility that
consumes a token adapts by itself. Templates carry no `dark:` variants.

| Block | Applies when |
|---|---|
| `:root` | Always; holds the light colors |
| `@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) }` | The system is dark and light is not pinned |
| `:root[data-theme="dark"]` | Dark is pinned, whatever the system says |

The two dark blocks must stay identical, so adding a color means adding
it to all three blocks. A test fails if the dark two drift apart.

### The toggle

The toggle follows Lea Verou's
[recommendation](https://lea.verou.me/blog/2026/dark-mode-toggles/):
one button with two states, never a three-way light/dark/system choice.

- Pressing it always flips what is on screen.
- The flip is stored only when it differs from the system theme; a flip
  that lands on the system theme removes the pin instead. That is what
  keeps "follow my device" reachable without a third state.
- A pin is never removed behind the user's back. If the system later
  changes to match it, it stays until the button is pressed again.

The pin lives in `localStorage` under `hrcek-theme`, as `light` or
`dark`, and nowhere else: it belongs to the browser, not the account.
Two pieces of script apply it:

- An inline, blocking script in the `<head>` of `base.html` reads the
  pin and sets `data-theme` on `<html>` before the first paint. Moving
  it into a file or deferring it brings back a flash of the wrong
  theme.
- `src/hrcek/core/static/js/theme.js`, deferred, wires up the button,
  keeps `aria-pressed` in step with the theme shown, and follows
  changes to the system theme and to the pin in other tabs.

Both also rewrite `<meta name="color-scheme">` to the pinned theme, so
the browser's own canvas and controls match. `:root` sets
`color-scheme: light dark` plus `accent-color` so native widgets
(checkboxes, selects, scrollbars) follow too; the pinned blocks narrow
`color-scheme` to the one theme. Tests assert the meta tag, the order
of the head, and that the compiled stylesheet carries the pinned
selectors.

The button is rendered `hidden` and revealed by the script, so a
browser without JavaScript never shows a control that does nothing.
It is announced as "Dark theme" with `aria-pressed`, and shows the sun
in light and the moon in dark.

## Markup Django generates

Most forms render with `{{ form.as_p }}`, and Django also emits
`class="errorlist"` and `class="helptext"`. Two forms are laid out by
hand in the same markup: the entry form renders each field through
`entries/_field.html`, which reproduces what `as_p` emits so it can
group fields in fieldsets, and the collection form
(`collections/form.html`) writes out each field's label, input, errors
and `helptext` itself around its "Show" fieldset. None of this markup
can carry utility classes, so it is styled once, by element and class
selectors, in the `@layer components` block of the source file. The
same block defines the small vocabulary templates use for structure:

| Class | Meaning |
|---|---|
| `row` | A list laid out as a wrapping row (nav, tags, pagination) |
| `stacked` | A plain vertical list |
| `entries` | The entry list: hairline separators, field grid |
| `messages` | Django's flash messages |
| `entry-text` | A collection's entry: everything except its picture |
| `entry-head`, `entry-body`, `entry-labels`, `entry-actions` | An `entries/list.html` card's four rows — see [the entries list](entries.md#the-entries-list) |
| `entry-thumb` | Such a card's picture, pinned to its top end |
| `thumb` | An entry's picture, a small square |
| `notes` | An entry's notes, which `linebreaks` turns into paragraphs; never wrap it in a `<p>` |
| `tag` | A tag pill |
| `danger` | A destructive button (deletes) |
| `actions` | A form's submit button and its way out, side by side |
| `danger-zone` | A section after a form holding something that cannot be undone, set well apart |
| `theme-toggle` | The icon button in the header that switches themes |

Checkbox rows get their own treatment. Django renders the label
before the input, and the global `label { display: block }` would drop
the box onto the next line, so a row containing a checkbox becomes a
flex line with the box moved ahead of the label and the help text
below both. Only one control in the row is focusable, so moving it
visually does not disturb tab order.

Do not name a template class after a Tailwind utility (`inline`,
`block`, `flex`...): the generated utility would override the component
rule. `row` exists because `inline` fell into exactly that trap.

## The mascot

Three pictures of the hamster live in `src/hrcek/core/static/img/`:

| File | Where it appears |
|---|---|
| `hrcek.png` | The whole hamster, above the title on the landing page |
| `apple-touch-icon.png` | The head only: the home-screen icon, and the small logo beside the name in every page header |
| `favicon-32.png` | The head only, small enough for a browser tab |

The header logo carries an empty `alt`: the link already reads
"Hrček", and a screen reader has no use for hearing it twice.
