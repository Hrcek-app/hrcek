# JavaScript

Hrček's pages work without JavaScript. Every control is a real link or
a real `<form>` that does its job on its own; scripts only make it
quicker — fewer page loads, focus kept where it was, results read out.
There is no Node, npm or build step: the few scripts are plain files
under `src/hrcek/core/static/js/`, loaded with `defer` from `base.html`
or from the page that needs them.

## Principles

- **Everything works without JavaScript.** Write the plain link or form
  first, make it work, test it with JavaScript off, then enhance it.
- **One implementation per feature.** The view that answers the plain
  form also answers the enhanced request. It renders the whole page, or
  only a fragment when the request comes from htmx. A fragment is a
  small template of its own that the whole page also `{% include %}`s
  — `entries/_empty_list.html`, say, shared by the list page's own
  empty state and the out-of-band fragment a delete sends. Included
  templates rather than `{% partialdef %}` partials, because most
  fragments are reused across views and pages (`_status.html`,
  `_messages.html`, the tags sidebar), and a partial belongs to the one
  template that defines it. Forms, validation and permissions are
  shared, never duplicated.
- **Never lose what was typed.** New navigation from a form opens in a
  new tab or is covered by the `data-guard-unsaved` guard
  (`js/unsaved.js`).
- **Accessible by construction.** Enhanced controls follow the WAI-ARIA
  patterns they imitate; results of in-place changes are announced
  through the one status region (below).
- **Strict-CSP-ready.** No Content Security Policy is set yet, but
  nothing may stand in the way of a strict one:
  - scripts come from `'self'` only — vendored, never from a CDN;
  - no `hx-on:*` attributes, no `js:` values, no htmx trigger filters
    (`hx-trigger="click[…]"`) — each of those is code evaluated from an
    attribute;
  - no `<script>` in a fragment, no inline event handlers, and no new
    inline scripts — a script is a file in `static/js/`.

  Two inline scripts predate this: the one in the `<head>` of
  `base.html` and `500.html` (the theme pin, and in `base.html` the
  `js` class below, both of which must run before first paint), and
  the kind/label toggle in `collections/form.html`. A CSP would carry
  the first one's hash; the second should move to a file first.

## htmx

[htmx](https://htmx.org) 4.0.0 is vendored, unmodified, at
`src/hrcek/core/static/js/vendor/htmx-4.0.0.min.js`:

| | |
|---|---|
| Source | https://registry.npmjs.org/htmx.org/-/htmx.org-4.0.0.tgz, file `package/dist/htmx.min.js` |
| Tarball integrity (npm) | `sha512-T/171FUY93Kdfp8t+DnHdk45QvKRiBhVhhrwSzrXgUi4pHKvhp77dUA/qg8FAjsFWPIHNbmUuIdCrcVHuiZWng==` |
| SHA-256 of the file | `e484d9171a9db30a39c8f16e3d709d4137f3211c659f8e6125816635033d593f` |

The version is in the file name, so a browser never runs a cached old
copy after an upgrade, and the pre-commit whitespace fixers skip
`static/js/vendor/` so the file stays byte-for-byte what upstream
shipped.

`base.html` loads it with `defer` and puts the CSRF token on `<body>`:

```html
<body … hx-headers:inherited='{"X-CSRFToken": "…"}'>
```

In htmx 4 attributes are not inherited unless they say so; the
`:inherited` suffix makes every htmx request from anywhere in the page
send the token, so `hx-post` works against Django's CSRF protection
without each element repeating it.

### Upgrading htmx

```bash
version=4.0.1   # for example
curl -sL "https://registry.npmjs.org/htmx.org/-/htmx.org-$version.tgz" \
    -o /tmp/htmx.tgz
curl -s "https://registry.npmjs.org/htmx.org/$version" \
    | uv run python -c \
        'import json, sys; print(json.load(sys.stdin)["dist"]["integrity"])'
echo "sha512-$(openssl dgst -sha512 -binary /tmp/htmx.tgz | base64)"
```

The two `sha512-…` lines must match. Then:

```bash
tar -xzO -f /tmp/htmx.tgz package/dist/htmx.min.js \
    > "src/hrcek/core/static/js/vendor/htmx-$version.min.js"
shasum -a 256 "src/hrcek/core/static/js/vendor/htmx-$version.min.js"
git rm src/hrcek/core/static/js/vendor/htmx-4.0.0.min.js
```

Update the `<script>` in `base.html`, the file name in
`tests/core/test_htmx.py`, and the table above; read the htmx changelog
for anything the browser tests would not catch; run the browser tests
in all three engines.

## The server side: `hrcek.core.htmx`

No django-htmx; what Hrček needs is two functions.

- `is_htmx(request) -> bool` — the request came from htmx (its
  `HX-Request: true` header). A view uses it to choose between the
  whole page and a fragment template the page itself includes.
- `vary_on_htmx(response) -> response` — adds `HX-Request` to `Vary`.
  A fragment and a whole page share a URL; without it a cache could
  hand one to someone who asked for the other. Every view that answers
  differently for htmx passes its response through it.

## The status region

`#status` is the only live region scripts write to. It is rendered by
`_status.html` (`src/hrcek/core/templates/`) as the first thing in the
page frame:

```html
<div id="status" class="sr-only" role="status" aria-live="polite"
     data-error-text="Something went wrong. Please check and try again.">
</div>
```

It is visually hidden and empty. `data-error-text` is the translated
failure message `js/htmx-errors.js` writes (below). A view that
changes something in place tells screen-reader users what happened by
including the same template in its fragment, with the text and the
`oob` flag:

```django
{% include "_status.html" with status=message oob=True %}
```

`oob` adds `hx-swap-oob="innerHTML"`. htmx finds the page's region by
its id, wherever it is and separately from the fragment's own target,
and puts the new text **inside** it; the wrapper the fragment carried
is dropped. In the vendored 4.0.0, any out-of-band style that does not
start with `outer` strips the wrapper this way, while `"true"` means
`outerHTML`.

**Why not replace the region.** A live region is announced when its
content changes while it sits in the page. Swapping in a fresh
`role="status"` element that already holds its text is the pattern
screen readers miss most often — NVDA and JAWS with Chromium frequently
say nothing — so the element in `base.html` must stay the same node for
the life of the page and only its text may change. A browser test marks
the node before an htmx change and checks the mark is still there
after.

**Say something different each time.** Even updated in place, the same
sentence twice in a row may be read only once. Name what changed —
"Label “watch” added.", not "Label added." — so consecutive results
differ, and so the message stands on its own when it appears as a
Django message on a page without JavaScript. That page uses the same
text.

The text, like every other, is translatable. Do not add a second
region for scripts to write to, and do not put `hx-swap-oob` on the one
in `base.html`.

The flash-message list in `base.html` (`ul.messages`) is a
`role="status"` too, by design, but a different kind: it is rendered
with the page and holds what the last request did. Two things replace
its contents afterwards: a fragment swapping it out of band, to show a
notice the change queued — a collection it emptied, say
([below](#the-messages-list-is-also-an-out-of-band-target)) — and
`js/htmx-errors.js` writing a visible error into it when a request
fails. What an in-place change did is `#status`'s job, not this
list's.

**Later enhancements** (a dialog that confirms in place, say) announce
their result the same way: the view's htmx answer includes
`_status.html` with `oob=True` and a sentence naming what was done,
and never ships a region of its own.

## Confirmation dialogs: `js/confirm-dialog.js`

A destructive action has a confirmation page of its own (the entries'
`confirm_delete.html`, say), reached by a plain link. To ask in place
instead:

1. Give the link `data-confirm-dialog="ID"`.
2. Render a closed `<dialog id="ID" aria-labelledby="…">` holding the
   same POST form the confirmation page has — same action, same hidden
   `next` — with the confirm button first and a
   `<button type="button" data-dialog-cancel autofocus>` to back out.
3. The non-destructive choice takes the initial focus: `autofocus` on
   the cancel button, which `showModal()` honours in every engine.
   Otherwise focus lands on the first button — the destructive one —
   and a stray Enter deletes.

With the script, a click on the link opens that dialog with
`showModal()` instead of navigating: the rest of the page goes inert,
focus moves to the cancel button, Escape or the cancel button closes
it, and focus returns to the link. Confirming submits the form the
ordinary way unless it is also enhanced with `hx-post` (below), in
which case the view, its redirect and its messages are still the
page's — just not by way of a page load. Without the script — or in a
browser without `<dialog>` — the link simply goes to the confirmation
page.

The script is one delegated `click` listener on `document`, so dialogs
in content swapped in later work without re-binding. A closed dialog
takes no room, and an open one is in the top layer, so a dialog may sit
inside a grid item (the entries list puts it in `entry-actions`)
without disturbing the grid.

## Removing a row in place: `hx-swap="delete"` and `js/delete-focus.js`

A row that disappears outright — the entries list's Delete, say — asks
for `hx-swap="delete"` on the control that removes it, targeting the
row itself (`hx-target="closest li"`, typically). That swap style
discards the response body for its own target entirely, so the view
only has to carry whatever else needs to change, as out-of-band
fragments: `#status`, and anything that replaces what the removed row
leaves behind (`entries/_empty_list.html`, say, when the row was the
last one).

Deciding where focus goes next is `js/delete-focus.js`'s job, because
the removed row is gone by the time anything could ask it. It listens
for two htmx 4 lifecycle events — note the colons, not camelCase:
`htmx:before:swap` and `htmx:after:swap` — both dispatched on
`document` once the element that triggered the request is no longer
connected, which a "delete" swap's own target always ends up being.
On `before:swap`, while the row and its still-connected siblings are
there to ask, it finds the main task in `event.detail.tasks` (the one
with `type: "main"`), checks its `swapSpec.style` is `"delete"`, and
remembers the first `[data-focus-after-delete]` in
`target.nextElementSibling`, or `previousElementSibling`, or the
page's one `[data-focus-after-delete-fallback]`. It cannot focus that
element yet — the row usually still sits inside an open, modal
`<dialog>`, which makes everything outside it inert — so it waits for
`after:swap`, once the removal (dialog included) has actually
happened, to call `.focus()`.

A row that is only sometimes removed — the delete can fail — needs one
more thing: **a failed request must not run the swap anyway.** The
page-wide configuration ([below](#error-pages-are-never-swapped-in))
already keeps a 404 or a 5xx from being swapped, but any other 4xx
still is, and for a "delete" swap that would remove the row for a
request that changed nothing. `hx-status:` is the per-element answer:
`hx-status:4xx="swap:none"` on the control itself (the entries list
also says `hx-status:5xx`, harmlessly, for the same reason), checked
against the exact status, then the two-digit wildcard, then the
one-digit one, first match wins. There is no `hx-status:*`, so an
unmatched status is untouched, which is what a successful response
needs to stay true.

## Error pages are never swapped in

htmx 4's default `noSwap` list covers only 204 and 304: a 4xx or 5xx is
swapped exactly like a 2xx unless told otherwise, which would put
Hrček's own 404 or 500 page inside a card or a form. `base.html` sets
it once, for every page:

```html
<meta name="htmx-config" content='{"noSwap":[204,304,404,"5xx"]}'>
```

htmx compares each entry, as a string, with the exact status, then its
two-digit wildcard (`"50x"`), then its one-digit one (`"5xx"`), so the
list covers 404 and every 5xx. Other 4xx responses are still swapped
on purpose: a form that fails validation answers 422 with itself, its
errors included, and that is the feedback. A control's own
`hx-status:` for a code can still override the list for that code,
but nothing here does.

## Saying a request failed: `js/htmx-errors.js`

A response nobody swaps still needs to be said somewhere, and so does a
request that never got a response at all — offline, say. **A failure
is never silent, for anyone:** on htmx 4's own failure events,
`htmx:response:error` (a 4xx or 5xx came back) and `htmx:error` (it
didn't come back at all), one delegated listener on `document` writes
a generic, translatable "Something went wrong. Please check and try
again." twice:

- **visibly**, as the only item of the page's `ul.messages`
  (`<li class="error">`, the same look as a Django error message),
  replacing whatever it held, so two failures in a row show one error;
- **to screen readers**, as `#status`'s text.

**Not every 4xx, though.** A control that swaps its own 4xx response —
a validation error rendered back into a form, say, 422 for adding a
label — is already its own feedback; overwriting it with a generic
"something went wrong" would bury the actual error, and closing the
form's dialog (below) out from under it would be actively wrong. The
listener acts only on responses htmx will not swap: a status in the
configured `noSwap` list (404 and every 5xx, read from
`htmx.config.noSwap`), a control that declared `hx-status:…`
`"swap:none"` for it, or no response at all (`htmx:error`). It
resolves this itself, the same order htmx does — exact status,
two-digit wildcard, one-digit wildcard, the list before the control's
`hx-status:` at each step — since by the time `htmx:response:error`
fires, htmx has not yet decided the swap style itself. **4xx responses
that a form swaps are its own feedback; the announcer is for responses
nobody shows.**

A plain script file carries no translation, so the message itself
lives on `#status`'s own `data-error-text`, rendered once by
`_status.html` (`{% trans %}`, the ordinary way) and simply read by the
script. `#status` is `.sr-only` and, while a modal `<dialog>` is open,
also inert — and its text changing while inert is not announced at all
once the dialog does eventually close, only genuinely new text is. So
the order matters: the listener closes whatever `dialog[open]` it
finds **first**, then writes the error into `ul.messages`, clears
`#status` and only then writes the message — clearing first so that
an identical second failure in a row still counts as a change and gets
announced again. Writing the text before closing the dialog would set
it while still inert, which is the same as not writing it at all.

A success, by contrast, is visually silent: the change on screen — a
card gone, a label added — is the confirmation, and `#status` says it
for screen readers. The account page's forms are the one exception
([below](#forms-saved-in-place-inside-a-tab)): a saved form looks the
same as before, so they show what was saved as well.

## Not sending two requests for one click: `hx-disable`

What was `hx-disabled-elt` before htmx 4 is now `hx-disable`, taking a
selector (`"findAll button"`, say) resolved the same way `hx-target`
is — `closest `, `find `, a plain selector, or `this`. Elements it
matches are disabled for the request's duration and re-enabled after,
counted so two overlapping requests do not re-enable too early. On the
delete dialog's form it keeps a double click, or Enter held a moment
too long, from sending a second POST while the first is still in
flight.

## The messages list is also an out-of-band target

`_messages.html` (`src/hrcek/core/templates/`) is `ul.messages`,
`id="messages"`, shared by `base.html` and any fragment that needs to
say something a link-free `#status` cannot — the emptied-collection
notice, say, which points at the collection's delete page. Always
rendered, even with nothing in it, the same reasoning as `#status`: an
out-of-band swap needs a matching id already on the page, and a
`:empty` rule in `static_src/hrcek.css` keeps an empty one from
changing how the page looks. A fragment that drains the request's
queued messages this way — by including `_messages.html` with
`oob=True`, which iterates `messages` same as the page itself does —
leaves nothing queued for whatever page the owner looks at next;
leaving it queued, the other option, means it survives a redirect the
in-place path does not take.

## Full navigation from an htmx request: `hrcek.core.htmx.htmx_redirect`

Two things an htmx request needs to answer with a real page load
rather than a swap: the sign-in page, and a page the current fragment
has no business updating in place (a label the request itself pruned,
leaving its filtered list without a page at all). fetch(), which every
htmx request goes through, follows an ordinary redirect on its own and
hands htmx the page it lands on to swap in — exactly wrong for either
case. `htmx_redirect(location)` answers 200 with an `HX-Redirect`
header instead: never auto-followed by fetch(), and read by htmx as
`location.href = location`, a genuine navigation, whatever the
response status says.

`hrcek.core.middleware.HtmxSignInRedirectMiddleware` applies this to
every htmx request automatically: a redirect to `LOGIN_URL`
(`login_required` on an expired session) or a 403 (a failed CSRF check
— the only thing that answers 403 here, so an htmx request meeting one
is treated the same as an expired session) both become a full
navigation to the sign-in page instead of swapping its markup into
whatever the request targeted. The sign-in page's `next` is the page
the person was on — htmx sends its address as `HX-Current-URL`; the
middleware keeps its path and query, after checking it with
`url_has_allowed_host_and_scheme` against the request's own host —
never the URL the request was sent to, which is usually POST-only:
signing in and landing on it with a GET would be a blank 405. A
missing or foreign `HX-Current-URL` falls back to the entries list.

A view that needs the same thing for some other redirect —
`entries.views.entry_delete` does, for a pruned label — calls
`htmx_redirect` itself, and queues with `messages.success` what its
`#status` would have said, since the navigation replaces the page that
text would have been written to.

## Tabs: `js/tabs.js`

A page section split into accessible tabs — the account hub's
Profile, Sign-in, and Fields and clients — starts as three stacked
`<section class="tab-section" id="…">` elements, each opening with an
`<h2>`, inside one `<div data-tabs data-tabs-label="…">`. Without
JavaScript they simply stack, each after the first opened by a
hairline and some room; with it, `tabs.js` turns the same markup into
a WAI-ARIA tab set.

For every `[data-tabs]` with at least two `section[id]` children, the
script:

- builds a `role="tablist"` and a `role="tab"` button per section,
  from each section's own `<h2>` (whose text becomes the tab's label;
  the heading is then hidden with `sr-only` rather than removed, so it
  still carries the section's accessible structure — it is just not
  shown twice);
- gives each section `role="tabpanel"` and `aria-labelledby` pointing
  at its tab, and each tab `aria-controls` pointing at its section;
- shows one panel and hides the rest with the `hidden` attribute,
  marks the open tab with `aria-selected`, and keeps only that tab in
  the page's tab order (roving `tabindex`: `0` on it, `-1` on the
  others);
- wires `ArrowLeft`/`ArrowRight`/`Home`/`End`, on the tablist, to move
  focus and select, wrapping at both ends; a click on a tab selects it
  without moving focus;
- opens the section a server-side error marked `data-open`, or else
  the one named by the page's `#hash`, or else the first — `data-open`
  wins when both are present. The initial selection never touches the
  URL: calling `history.replaceState` there, before the browser's own
  scroll-to-fragment step has run, used to land a plain visit scrolled
  past the heading. Switching tabs afterwards (a click, or
  `ArrowLeft`/`ArrowRight`/`Home`/`End`) does update the hash, with
  `history.replaceState` so it adds no history entry.

`[data-tabs]` carries the tablist's accessible name as
`data-tabs-label`, a string the template already translated, so
`tabs.js` itself holds no user-facing text — strict-CSP-ready scripts
never do.

Once the tablist is built, the script adds the class `tabbed` to the
`[data-tabs]` element. The hairline between stacked sections is styled
only on `[data-tabs]:not(.tabbed)`: with the tabs in place, the open
panel sits right under the tablist's own bottom border, and the
section's separator would draw a second line beneath it. A browser
test counts the borders between the tablist and the first form control
— exactly one — and checks the stacked sections are still separated
without JavaScript.

A page with fewer than two sections is left alone: the script does
nothing, and the stacked markup is the whole of it.

## Forms saved in place inside a tab

The account hub's forms (see
[Accounts](accounts.md#the-pages)) save without a reload, and
inside a tab set that takes one rule beyond the labels' pattern below:
**swap the panel's content, never the panel.** `tabs.js` gave each
`<section>` `role="tabpanel"`, `aria-labelledby`, a `tabindex` and
`hidden`; markup from the server has none of them, so replacing the
section would leave a panel that is no longer one. Each section
therefore holds its `<h2>` (made `sr-only` by the script, and kept
out of the swap for the same reason) and one wrapper,
`<div class="tab-content" id="profile-content">`, which is its own
template (`accounts/_profile.html`) the page includes and the view
answers htmx with. The forms in it say:

```html
hx-post="…same URL…" hx-target="#profile-content" hx-swap="outerHTML"
hx-disable="find button"
```

- **Success** is the section re-rendered with fresh forms, the saved
  value in them. The view queues its Django message as usual and the
  fragment carries `_status.html` (the same sentence) and
  `_messages.html`, both with `oob=True`, so `#status` announces it
  and `#messages` shows and drains it. `autofocus` goes on the button
  just used, since the one that had focus was swapped away. This is
  the one in-place success that is also shown, not only announced:
  a saved form looks exactly as it did before the click, so there is
  no change on screen to serve as the confirmation.
- **Errors are 422s**, the section with the bound form and its field
  errors, swapped like a success (a 422 is not in the `noSwap` list,
  and `js/htmx-errors.js` leaves a swapped 4xx alone). `autofocus` goes
  on the first field in error. A 404 or a 5xx is never swapped into
  the section; `js/htmx-errors.js` shows and announces the failure
  instead, and the section stays as it was.
- **The tab stays selected and the URL is unchanged**: nothing outside
  the wrapper is touched, and `hx-post` pushes no history.
- **Without JavaScript nothing changes**: the same views redirect to
  `?section=` on success and re-render the whole page, the section
  marked `data-open`, on an error.

**Why `autofocus` works more than once here.** The browser's own
autofocus processing runs once per document — after the first
`autofocus` element is connected, later ones are ignored until a full
navigation, which is why `js/delete-focus.js` exists. But htmx does
not rely on it: after every swap it looks for the first `[autofocus]`
in the new content and calls `.focus()` on it itself. A browser test
fails the same field twice in a row and checks it has focus both
times.

## Forms changed in place: the entries' labels

The labels on the entries list are the first forms htmx submits (see
[Entries](entries.md#labels-on-the-list)). Each is an ordinary
`<form method="post" action="…">` with `{% csrf_token %}` and a hidden
`next`, plus:

```html
hx-post="…same URL…" hx-target="#labels-12" hx-swap="outerHTML"
```

The attributes sit on the form itself: in htmx 4 nothing is inherited
unless it says so. The CSRF token travels twice — as form data and in
the `X-CSRFToken` header from `<body>` — and a browser test removes the
form's token to prove the header alone gets through.

- **The fragment is its own small template** (`entries/_entry_labels.html`),
  the whole page also `{% include %}`s inside its loop, so the markup
  exists once. It carries the status line with `oob=True`, naming the
  label added or removed, `_messages.html` with `oob=True` alongside it
  (draining whatever a collection-emptied or already-got notice queued,
  same as `_delete_result.html`), and — only when adding or removing
  changed what `Tag.in_use` offers — `entries/_tags_sidebar.html` with
  `oob=True` too, same as a delete that prunes a label.
- **Errors are 422s.** htmx 4 swaps a 422 like any other response, so
  the fragment with the error beside the input simply replaces the old
  one. A 404 or a 5xx is never swapped
  ([Error pages are never swapped in](#error-pages-are-never-swapped-in)):
  the labels stay as they were and `js/htmx-errors.js` shows the
  failure.
- **A pruned filter is a full navigation, not a fragment.** Removing the
  only entry a filtered list is showing leaves nothing sensible to swap
  in place — same question `entry_delete` asks when its own delete
  prunes the label a filtered page was started from — so the view
  answers with `htmx_redirect` to `still_there`'s plain-list answer
  instead, with the status queued as a message for the page it lands
  on, exactly as that delete does.
- **Focus is set by the server, with `autofocus`.** htmx focuses the
  first `[autofocus]` in swapped content, so the fragment says where
  focus belongs: in the add input after an add or an error, on the
  "+ Label" summary after a removal. No script needed.
- **`outerHTML`, not `outerMorph`.** Morphing keeps a form control's
  current value, which is right for a half-typed form and wrong here:
  the label just added would stay in the box.

**"+ Label" becomes "Cancel" while it is open: `js/add-pill.js`.**
The summary holds two spans, `.add-pill-text` ("+ Label") and
`.add-pill-cancel-text` ("× Cancel"); `details.add-pill[open] >
summary` in `static_src/hrcek.css` shows one and hides the other with
`display: none`, which also takes the hidden one out of the
accessible name — so the summary is announced as "+ Label" closed and
plainly "Cancel" open, the "×" itself marked `aria-hidden` so it never
joins that name. Clicking either way is `<details>`'s own native
behaviour, nothing to enhance; the one thing it does not do by itself
is close on Escape, which `js/add-pill.js` adds with one delegated
`keydown` listener on `document` — closing the nearest open
`details.add-pill` and focusing its own summary — so a fragment
swapped in later by an add or a remove works without re-binding. The
entries' "+ Collection" is the same pattern: any `details.add-pill`
with those two spans gets it.

## Forms changed in place: the entries' collections

The "In:" line on the entries list (see
[Entries](entries.md#adding-and-taking-out-from-the-list)) is the
labels' pattern again: its own small template,
`entries/_entry_collections.html`, swapped `outerHTML` over
`#collections-<pk>`, carrying `#status` and `_messages.html` with
`oob=True`, and `autofocus` saying where focus goes. One difference:
the forms declare `hx-status:4xx="swap:none"` and
`hx-status:5xx="swap:none"`. They have no validation error of their
own to show — the only 4xx is a 404 for a collection that is gone or
was never the owner's — so a refusal leaves the line as it was and
`js/htmx-errors.js` shows and announces it, as it does for a failed
delete.

### Controls for JavaScript only: `.js-only`

The rule is that every feature works without JavaScript *somewhere*,
not that every control does. "+ Collection" has no plain version on
the list — the entry's edit form is the way without JavaScript — so it
should not be drawn when it cannot work. The inline script in the
`<head>` of `base.html` puts a `js` class on `<html>`, and
`html:not(.js) .js-only { display: none; }` keeps anything marked
`.js-only` out of sight without it.

**Before first paint, not deferred.** A deferred script runs only
after every deferred script before it has downloaded — htmx first,
some 37 KB — so the page would be drawn without the class, then every
pill would pop in and push its card taller. Set inline, the class is
there before anything is drawn, and nothing moves when htmx arrives; a
browser test holds the htmx download back to prove it.

A class on the root, rather than a `hidden` attribute each control's
script removes, also means a fragment swapped in later is visible the
moment it lands — no re-processing, and no race with the `autofocus`
htmx gives it after the swap.

**A row holding only JavaScript controls goes too.** An entry in no
collection yet has a collections line holding nothing but the pill, so
the line itself is `.js-only` then, and
`html:not(.js) ul.entries article > .entry-body:not(:has(> :not(.js-only)))`
hides an `entry-body` with nothing else in it, the same as an empty
one — otherwise it would leave a blank row in the card without
JavaScript.

## Removing a row in place on a collection's page

"Take it out" on `collections/detail.html` is the entries list's
Delete without the dialog: `hx-post` on the same form,
`hx-target="closest li"`, `hx-swap="delete"`, `hx-status:4xx`/`5xx`
`"swap:none"` and `hx-disable`. `collections/_remove_result.html` answers with
everything out of band — `#status` naming the entry, the drained
`#messages`, and `collections/_empty.html` (the page's own empty
state, `id="collection-entries"`, swapped over the list's `ul`) when
that was the last entry. `js/delete-focus.js` moves focus to the next
row's title link, else the previous one's, else the "In this
collection" heading (`tabindex="-1"`,
`data-focus-after-delete-fallback`), which sits right above the empty
state.

## Adding an enhancement

1. Build and test the plain version: a link or a form, a view that
   redirects, a test with the Django test client.
2. Test it in a browser with JavaScript off (`tests/browser/`, see
   [Testing](testing.md#browser-tests)).
3. Enhance it with htmx attributes on the same markup, or with a small
   delegated script in `static/js/`, never with inline code. If the view
   answers htmx differently, branch on `is_htmx`, render a fragment —
   the whole page's own template, or a small one both `{% include %}` —
   and wrap the response in `vary_on_htmx`.
4. Announce the result through `_status.html` with `oob=True`. Failures
   need nothing of their own: an error page is never swapped in, and
   `js/htmx-errors.js` shows and announces it. Only a form that renders
   its own errors back (422) is swapped, and is its own feedback.
5. Add browser tests for the enhanced path, in Chromium, Firefox and
   WebKit, and keep the JavaScript-off test.
