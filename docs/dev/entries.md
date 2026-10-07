# Entries

The `hrcek.entries` app holds what Hrček is actually for: an `Entry`
belonging to one person, with tags.

## Ownership

Every entry and every tag has an owner, and every query is scoped to
`request.user`. Somebody else's entry answers **404, not 403**; a 403
would confirm the id exists.

Tags belong to a person too. Nina's `watches` and Marko's `watches` are
different rows.

## URL identity

A person cannot hold the same address twice, enforced by a
`UniqueConstraint(owner, url)`. Saving an address already held updates
that entry. This makes a re-run import idempotent, and it is the same
rule on the web form as in the API.

**Matching is deliberately near-exact**: whitespace trimmed, scheme and
host lowercased, nothing else.

Fuller normalisation — trailing slashes, `www.`, stripping `utm_*` — is
a rabbit hole where every rule is wrong for some site, and its failure
mode is silent: two genuinely different pages merge into one entry and
one is lost. Near-exact matching fails visibly instead, as a duplicate
somebody can see and fix. Do not "improve" this without a reason
stronger than tidiness.

## Ordering

`Meta.ordering` is `("-created_at", "-pk")`. The `-pk` is not
decoration: entries saved in one batch share a timestamp to the
microsecond, and without a tiebreaker SQLite is free to order them
differently between queries, so pagination can show a row twice or skip
it. There is a test that fixes two entries to the same instant.

## save_entry is the only writer

`services.save_entry()` is the single place an entry is written. The web
form, the API create endpoint and the batch endpoint all go through it,
so upsert-on-URL, tag assignment and URL validation exist once rather
than in three copies that drift apart.

URL validation lives there rather than on the form for the same reason:
the web form has a `URLField` in front of it, the API has nothing, and
the shared path is where the rule belongs.

## Tags

Parsed from one comma-separated field, trimmed, empties dropped,
deduplicated ignoring case, keeping the first spelling seen. Created on
demand.

`Tag.prune_orphans(owner)` deletes that person's tags that no entry uses
any more, and is called after every save and every delete. Without it
every typo lives in the tag list forever. It spares a tag a label
collection follows: `Collection.label` cascades, so deleting the tag
would delete the collection and its shared link as a side effect of
relabelling. It is written as
`filter(owner=owner, entries__isnull=True, collections__isnull=True)` —
string lookups rather than reverse accessors, because `ty` does not run
the django-stubs plugin and cannot see `tag.entries`.

So a tag can exist with no entries. Everything that shows tags to a
person goes through `Tag.in_use(owner)`, which lists only tags some
entry carries: the tag list beside the entries, `GET /api/labels/`, and
the `?tag=` filter, which answers 404 for a name nothing carries.

## Custom fields

`FieldDefinition` is a field somebody has decided their entries should
carry; `FieldValue` is what one entry holds for one of them. Both belong
to an owner, like everything else here.

**Values live in a column matching their type.** `value_text` and
`value_number`, not one text column, so a number sorts and compares as a
number when something eventually wants to. `FieldValue.value` is a
property reading and writing whichever column the definition's kind
calls for, so nothing outside the model has to know which it is.

`format_number` renders a stored number the way it was most likely
typed. The column keeps six decimal places, so 129 comes back as
129.000000; `Decimal.normalize` strips the zeros but turns round numbers
into exponent form — 1000 becomes `1E+3` — so those are quantized back
to an integer. There is a test for each case.

### Seeding

Every account starts with **Price** (number) and **Priority** (choice:
high, medium, low). A `post_save` receiver seeds new accounts and a data
migration covered the ones that already existed. Both are idempotent, so
running either again changes nothing.

They are **ordinary rows**: no flag marks them as built in, and they can
be renamed or deleted like any other. This is deliberate — a special
case would have to be defended everywhere a field is read.

Their names are **data, not interface**, and are therefore not
translated. A name that changed with the interface language would be two
different fields to the API, and there would be no sensible answer to
what happens when somebody renames one and then switches language.

### Why `choice` cannot be created

The kind exists in the model for the seeded priority and is not offered
by the form. A choice field needs options, and there is no interface for
editing them; offering the kind without that would produce a field that
can hold nothing.

Delete priority and it is gone for good. The manual says so plainly.

### Why the kind is fixed after creation

An existing value cannot always be reread as another type. Changing
`number` to `text` is harmless, the other direction is not, and a form
that silently drops values on save is worse than one that does not offer
the change at all. `FieldDefinitionForm` removes the control when it is
editing an existing row.

### set_field_values is a patch

`services.set_field_values(entry, mapping)` sets the names the mapping
carries and leaves every other field alone. An empty string removes a
value, and that is the only way to remove one.

This is the single place the API is not uniform — everything else about
an entry is replaced on save. The reason is in [the API
guide](api.md#fields-is-patched-not-replaced), and it is worth repeating
here: a client that predates fields must not be able to destroy them.
Do not "fix" the inconsistency.

Validation runs over the **whole** mapping before anything is written,
so a bad value in the second field cannot leave the first one changed.
A name nobody owns raises `HRC-FIELD-0001` rather than being dropped: a
typo should be reported, and silently ignoring it would let a client
believe it had saved something.

Errors from `validate_field_value` are keyed by the field's name —
`ValidationError({definition.name: [...]})` — so the API can say which
field was wrong without parsing the message. `_details()` in `api.py`
turns that into `details.fields`, using `url` for the address.

## Unsaved changes on the form

The entry form is marked `data-guard-unsaved`, and
`src/hrcek/core/static/js/unsaved.js` asks before anybody leaves it
with changes that are not saved. "Changed" means what the form would
submit differs from what it held at load, so typing and deleting again
is not a change. A form re-rendered with errors (`form.is_bound`)
carries `data-unsaved="true"` and counts as changed from the start:
its contents are on the page and nowhere else.

Submitting never asks. Everything else does: links, reloads, closing
the tab. The question is the browser's own `beforeunload` prompt, whose
wording a page cannot change, and browsers only show it once the user
has interacted with the page.

Any other form that holds typing worth keeping can opt in with the same
attribute; the script is loaded by the page's `head` block.

Links on the form that lead elsewhere but are part of filling it in,
like the one to your fields, open in a new tab instead, so following
them loses nothing.

## The entries list

Each `<article>` in `entries/list.html` always renders the same four
direct `<div>` children, in order, whether or not they have anything
in them: `entry-head` (title and the date added), `entry-body` (notes
and fields), `entry-labels` (tags) and `entry-actions` (Edit and
Delete). An entry's optional picture is a fifth, sibling element,
`a.entry-thumb`.

Always rendering all four, even empty, is what gives later branches
somewhere to put a new row (an "In:" line, say) without touching the
template everywhere else. Each `<article>` is a flex column (selector:
`ul.entries article:has(> .entry-head)`, in `static_src/hrcek.css`),
so the gap between head, body, labels and actions depends only on
that card's own content, never on a neighbour's title or notes. A
card used to share rows with the rest of its grid row through
`grid-template-rows: subgrid`; that made one entry's long notes push
every other card's body, labels and actions down to match, and it is
gone. What still makes every row's "Edit"/"Delete" land on the same
line is simpler: the grid's own default alignment already stretches
every `<li>` in a visual row to the tallest one, and `.entry-actions`
is pushed to the bottom of that stretched height with a plain
`margin-block-start: auto`.

`entry-body` and `entry-labels` hold only conditional content, so the
template glues each one's opening tag straight to its first
`{% if %}` and its last `{% endif %}` straight to the closing tag,
with no whitespace in between. An entry with no notes, no fields and
no tags therefore renders `<div class="entry-body"></div>`, genuinely
empty rather than full of blank lines, and a `:empty` rule in
`static_src/hrcek.css` hides it, so that row adds no gap either side
of itself in the flex column.

An entry's optional picture, `a.entry-thumb`, is taken out of the
flex column with `position: absolute` and pinned to the top end,
beside the title and date rather than spanning rows, so a picture
never forces the card taller than its own text would.

**The date added.** `<time datetime="…">` carries the exact instant,
machine-readable; what a person sees is `MONTH_DAY_FORMAT` ("7 Oct")
for something added this year and `DATE_FORMAT` ("7 Oct 2024") once it
is not, compared by `{% now "Y" %}` against the entry's own year so the
page does not need the server's "today" passed in separately. The
`title` attribute is the tooltip: the full day name and date, in the
translatable format string `"l, j F Y"` (Slovenian: `"l, j. F Y"`).

**Deleting from the list.** Each entry's Delete link carries
`?next=` set to the current page's own address (including `?page=`
and `?tag=`), so confirming the delete, or choosing "Keep it", returns
to the same page — including page 2 of a label-filtered list. See
`safe_next` below for how that address is checked.

One exception: deleting the last entry carrying the filtered label
prunes that label, and the list gives a label nothing carries no page.
`hrcek.entries.navigation.still_there(back, owner)` returns `back`
unless its `tag` value — stripped and matched case-insensitively, the
list view's own rule — is no longer in `Tag.in_use(owner)`, in which
case it returns the plain list. `entry_delete` passes its `safe_next`
target through it after `Tag.prune_orphans`.

## safe_next: returning somewhere without being an open redirect

`hrcek.core.navigation.safe_next(request, default)` reads `next` from
POST then GET, and returns it only if
`django.utils.http.url_has_allowed_host_and_scheme` says it names a
relative, same-host address; anything else, including a missing
`next`, falls back to `default`. `entries:delete` uses it both for the
confirmation page's hidden field and "Keep it" link, and for where the
POST redirects to once the entry is gone.

It is deliberately generic rather than entries-specific — later
features that offer a "come back here" link (adding or removing a
label, for instance) reuse the same function rather than growing their
own copy of the same host check.

[The API guide](api.md) is the client-facing contract. What follows is
why it is shaped that way.

```
POST /api/entries/          one entry; 201 created, 200 updated
POST /api/entries/batch/    up to HRCEK_MAX_BATCH; 200 or 207
GET  /api/entries/          your entries, paginated
GET  /api/entries/by-url/   one entry by its address, or 404
```

Everything on `EntryIn` except `url` has a default, so a client can post
a bare link. A client that knows nothing about a later addition must
keep working, which is also why `fields` is patched rather than
replaced.

**`by-url` must stay above any `/{id}/` route.** There is no
detail-by-id route today; whoever adds one has to declare it after
`by-url`, or Ninja will read `by-url` as an id. The comment in `api.py`
says so at the point it matters.

It exists because posting is an upsert: without it a client cannot ask
what an address currently says before writing over it, and fetching the
whole list to filter locally is the wrong shape once somebody holds
thousands of entries. It normalises through `Entry.normalise_url`, so
the lookup and the save agree on what counts as the same address.

**The batch contract.** One result per row, in submission order, each
`created`, `updated` or `error`. The call answers **200 when every row
succeeded and 207 when any failed** — a flat 200 would hide the failure
from a client that checks only the status.

**It is not atomic, on purpose.** Each row runs in its own transaction,
so the rows that were fine are saved and re-running fixes only the rows
that were not. A client has to be able to handle a partially applied
import, which is what the per-row results are for.

Exceeding the limit refuses the whole request with `HRC-ENTRY-0001`
rather than saving a prefix — a half-applied batch with no report is
worse than none.


## Addresses stay out of query strings

`POST /api/entries/lookup` reads, but it is a POST, because the
address travels in the body. A query string is written into the web
server's access log, into any proxy in front, and onto Sentry events —
none of which this project controls — and an address is the private
half of an entry.

Hrček's own JSON log records `request.path` and never the query
string, so the application log was already clean; the exposure was
everything downstream of it. Sentry now has its query strings stripped
as well, in `hrcek.core.telemetry.strip_query_strings`, because
`send_default_pii=False` covers cookies, bodies and user details but
not the query string.

The 404 carries no details for the same reason: the address would
otherwise reach any client and any log that keeps bodies.

## Reading the definitions

`src/hrcek/entries/fields_api.py` serves `/api/fields/` and
`/api/labels/`, both read-only. They are mounted at the top level
rather than under `/api/entries/`: a client asking what fields it has
is not asking about any particular entry.

Labels take an optional `starts_with`, so one endpoint serves both a
full list and an autocomplete. The filter is `istartswith` — a
literal, not a pattern, because whatever somebody types into an
autocomplete box has to mean itself.

A label page holds a thousand, set as both the default and the
maximum on the pagination input so the ceiling appears in the OpenAPI
schema. Over that is a 422, not a silent truncation: a client that
asked for five thousand and got a thousand would page wrongly.

Paging is by cursor, not offset: `after` takes the last name served
and the next page begins past it. An offset counts rows and the rows
move — insert a label that sorts earlier and everything after it
shifts, so the next offset skips whatever crossed the boundary.

The ordering and the cursor have to agree exactly or pages fall
between rows, so both use the lowercased name: the queryset is
annotated `sort_key=Lower("name")` and ordered by it, and the cursor
compares `sort_key__gt=after.casefold()`. There are no ties to break,
because a label cannot differ from another only by case — the
per-owner unique constraint is case-insensitive.
