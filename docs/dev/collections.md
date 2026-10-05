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
not: they are meant to be found.

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

Items come from `Collection.entries()` — the same method the page uses,
so neither what a feed holds nor the order it holds it in can drift
from the page. Notes appear only where `show_notes` is on; a feed that
carried what its page hides would be a back door, and
`test_a_feed_hides_what_its_page_hides` holds that line.

Django's `Feed` wants the collection's description under two names:
`description` for RSS readers, and `subtitle`, which is what Atom
actually emits. Both are defined.

Each page advertises its feed with a `<link rel="alternate">` in the
head, through the `head` block added to `base.html`.
