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

## Light and dark themes

Pages follow the system theme. The mechanism is the token block again:
the `@media (prefers-color-scheme: dark)` block redefines the same
custom properties, so every rule and utility that consumes a token
adapts by itself. Templates carry no `dark:` variants, and adding a new
color means adding it to both blocks.

Two details support this: `base.html` declares
`<meta name="color-scheme" content="light dark">` so the browser picks
the right canvas color before the stylesheet loads, and `:root` sets
`color-scheme: light dark` plus `accent-color` so native widgets
(checkboxes, selects, scrollbars) match. A test asserts the meta tag and
the stylesheet link are present.

## Markup Django generates

Forms render with `{{ form.as_p }}`, and Django also emits
`class="errorlist"` and `class="helptext"`. That markup cannot carry
utility classes, so it is styled once, by element and class selectors,
in the `@layer components` block of the source file. The same block
defines the small vocabulary templates use for structure:

| Class | Meaning |
|---|---|
| `row` | A list laid out as a wrapping row (nav, tags, pagination) |
| `stacked` | A plain vertical list |
| `entries` | The entry list: hairline separators, field grid |
| `messages` | Django's flash messages |
| `tag` | A tag pill |
| `danger` | A destructive button (deletes) |

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
