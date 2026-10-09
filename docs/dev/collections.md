# Collections

A collection is a named set of one person's entries. This page covers
the model; sharing and feeds arrive with those layers.

## Two kinds, one immutable choice

`Collection.kind` is either `manual` or `label`, and it is fixed at
creation. `CollectionForm` deletes the `kind` and `label` inputs once
the instance exists, so the edit page cannot offer them and a crafted
POST cannot set them either.

The database holds the shape as well, through a check constraint: a
label collection names exactly one label, a manual one names none.
The other two shapes are meaningless, so nothing may write them.

```python
models.CheckConstraint(
    condition=(
        Q(kind="label", label__isnull=False) | Q(kind="manual", label__isnull=True)
    ),
    name="label_set_exactly_when_kind_is_label",
)
```

The label picker is only of use to a collection that follows a label.
The form marks both inputs server-side — `data-kind-select` on the
kind, `data-label-field="label"` on the picker, naming the kind that
needs it — and a small script in the template reveals the picker for
that kind and hides it otherwise. Without JavaScript both inputs stay
visible, and submitting a label alongside "chosen by hand" is refused
with a message rather than silently discarded: a submission whose two
halves disagree should say so.

## Membership

Manual membership is `CollectionEntry`, a model rather than a plain
many-to-many because it carries `added_at` — which is what orders a
manual collection. Label membership is not stored at all: it is a
query over the label, so an entry gaining or losing the label moves in
or out with nothing to keep in step.

`Collection.entries()` is the single source of both, and of their
orderings:

| Kind | Ordered by | Why |
|---|---|---|
| Manual | `CollectionEntry.added_at` | The moment it was put in |
| Label | `Entry.created_at` | There is no moment of adding |

Pages, feeds and tests all call this method. Nothing re-implements the
ordering, so nothing can drift out of step with it.

### A label left with no entries

`Tag.prune_orphans` spares a tag a collection follows (see
[entries](entries.md#tags)), so a label collection survives its last
entry. The entry form and the entry delete view compare the tags the
entry carried before the change with
`collections.services.emptied_label_collections(owner, tag_ids)`, and
add a notice per collection the change emptied, linking to its delete
page. The notice comes after the save rather than as a question before
it, because a confirmation step in front of the entry form would drop a
picture chosen in its file input. The API keeps the collection without
saying anything; it has nobody to ask.

## Ownership

`services.add_entry` is the only way an entry joins a collection, and
it refuses across accounts with `HRC-COLL-0001` — a 404 code, not a
403, on the project's usual reasoning that a 403 confirms the thing
exists. It also refuses to add by hand to a label collection
(`HRC-COLL-0002`), which the pages never offer but a direct POST
could try.

Adding twice is deliberately harmless: the page lists each entry once,
and a double submission should not become an error somebody has to
read.

## Deleting

Deleting a collection cascades to its `CollectionEntry` rows and stops
there. The entries themselves are untouched, which the confirmation
page says in as many words.

## Visibility

`Collection.visibility` is one of `private`, `unlisted` or `public`,
and each has its own address:

| Level | Address | Route |
|---|---|---|
| private | `/collections/<id>/` | `collections:detail` |
| unlisted | `/c/<secret>/` | `shared:unlisted` |
| public | `/u/<namespace>/<slug>/` | `shared:public` |

The shared routes live in `shared_urls.py`, included at the root rather
than under `/collections/`, and in their own URL namespace: two
includes cannot share one.

Every lookup filters on the visibility as well as the address, so a
collection that stops being public stops answering at its public
address in the same request cycle. A wrong secret, an unknown public
name, or a visibility that does not match the address is a **404**,
never a 403 — a 403 tells a stranger that something exists.

Unlisted pages send `X-Robots-Tag: noindex, nofollow`. Public pages do
not: they are meant to be found. `robots.txt` also keeps crawlers out
of `/c/`; see [deployment](deployment.md#files-at-the-site-root).

### The secret

`secrets.token_urlsafe(16)` — 22 characters — written once by `save()`
and never rewritten, so a link already shared survives the owner
changing their mind about visibility twice. Adding the column took the
three-step migration Django documents for a unique field: add it
loose, fill it row by row, then tighten it. A callable default would
have been evaluated once and handed every row the same value.

### The slug

`slugify(name)`, made unique within the account by appending `-2`,
`-3`, and regenerated on every save of a public collection — so
renaming one moves it. That is why the form warns about it. A name
with nothing sluggable in it falls back to `collection`.

## What a shared page shows

The name and description always; of each entry, the address and title
always. Notes, labels, pictures and each custom field are off by
default and turned on per collection. Hidden means **absent from the
HTML**, not styled away: the template asks before it renders, and
`test_hidden_things_are_absent_from_the_source` holds that line.

## Wish lists

`Collection.is_wish_list` turns a shared collection into a list
visitors can say "Got it" on. A mark is a `GotIt` row: `collection`,
`entry`, `got_by`, `got_at`, unique on `(collection, entry)`. It belongs
to one list, not to the entry, so the same entry on two wish lists is
two separate wishes.

**No maintenance.** Marks are only ever read through
`Collection.entries()`, so a mark on an item that has left the list —
taken out by hand, or no longer labelled — does nothing, and nothing
deletes it. If the item returns, the mark returns with it. Switching
`is_wish_list` off suspends every mark the same way.

The rules live in `collections/services.py`, and pages, feeds and the
entry form go through them rather than querying `GotIt`:

| Function | Purpose |
|---|---|
| `get_it` / `undo_got_it` | a visitor marks or unmarks; raises `HRC-COLL-0003`–`0007` |
| `put_back` | the owner clears a mark; ownership is the caller's check |
| `shared_entries(collection, viewer)` | what a shared page or feed lists |
| `got_entry_ids` / `got_by_viewer` | ids for the owner's reveal and the giver's *Undo* |
| `label_wish_lists_holding` / `already_got_on` | the came-back notice on entry save |

Who sees what on a shared page of a wish list:

| Viewer | Nobody got it | They got it | Somebody else got it |
|---|---|---|---|
| Not signed in | shown | — | hidden |
| Signed in | shown, *Got it* | shown, *Undo* | hidden |
| The owner | shown, no buttons | — | shown |

Shared feeds use `shared_entries` with an anonymous viewer; the
owner's private feed overrides `listed()` to return everything.

The actions sit under the shared address, so the secret stays the only
key to an unlisted list:

| Action | Address | Route |
|---|---|---|
| Got it | `/c/<secret>/got/<entry>/` | `shared:unlisted_got_it` |
| Undo | `/c/<secret>/got/<entry>/undo/` | `shared:unlisted_undo` |
| Got it | `/u/<namespace>/<slug>/got/<entry>/` | `shared:public_got_it` |
| Undo | `/u/<namespace>/<slug>/got/<entry>/undo/` | `shared:public_undo` |
| Put back | `/collections/<id>/got/<entry>/put-back/` | `collections:put_back` |

All POST only. A visitor who is not signed in has no buttons; one who
posts anyway (a page loaded before signing out) is sent to sign in with
`next` set to the shared *page*, since the action address would answer
GET with 405. The entry is looked up among the owner's entries and
checked against the list by `get_it`, so an unknown id, a stranger's
entry and an entry not on this list all get `HRC-COLL-0005`.

The owner's page takes two query parameters. `?got=show` reveals the
marks; it is never remembered, and `got` is only put in the template
context when it is set. `?back=<entry>` shows the came-back notice for
that entry, and only if it is got on this list. Adding an entry by hand
redirects there when the entry is already got; saving an entry form
compares `label_wish_lists_holding` before and after and links there
for each label wish list the entry arrived on.

## Pictures

Entry images used to be readable by their owner and nobody else.
Sharing changes that rule, and it is the one place here where getting
it wrong leaks private data. See
[images](images.md#who-may-see-a-picture).

## Feeds

Atom, from `django.contrib.syndication` with `Atom1Feed`. Nothing here
writes XML by hand.

`src/hrcek/collections/feeds.py` holds three classes sharing a base.
They differ only in `get_object`, which is where visibility is
enforced: the private feed requires the owner's session, the unlisted
one looks up by secret **and** `visibility=UNLISTED`, the public one by
public name, slug **and** `visibility=PUBLIC`. A feed therefore cannot
be reachable anywhere its page is not.

| Feed | Address | Route |
|---|---|---|
| private | `/collections/<id>/feed/` | `collections:feed` |
| unlisted | `/c/<secret>/feed/` | `shared:unlisted_feed` |
| public | `/u/<namespace>/<slug>/feed/` | `shared:public_feed` |

Items come from `Collection.entries()` — through `shared_entries()` for
the shared feeds, see [wish lists](#wish-lists) — the same as the page,
so neither what a feed holds nor the order it holds it in can drift
from the page. Notes appear only where `show_notes` is on; a feed that
carried what its page hides would be a back door, and
`test_a_feed_hides_what_its_page_hides` holds that line.

Django's `Feed` wants the collection's description under two names:
`description` for RSS readers, and `subtitle`, which is what Atom
actually emits. Both are defined.

Each page advertises its feed with a `<link rel="alternate">` in the
head, through the `head` block added to `base.html`.
