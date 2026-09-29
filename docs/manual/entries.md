# Saving things

An entry is one thing you want to keep: a page you mean to read, a watch
you are pricing, a recipe. It holds a web address, a title, some notes,
and any tags you give it.

## Saving something

Sign in and you land on your entries. "Save something" asks for:

- **Address** — where it is on the web. The only thing actually
  required.
- **Title** — what to call it. Leave it blank and Hrček shows the
  address instead.
- **Notes** — anything you want to remember. Plain text; line breaks are
  kept.
- **Tags** — separated by commas.

## Saving the same address twice

**If you save an address you already have, Hrček updates that entry
instead of making a second one.** This is deliberate: it means a script
or an import can be re-run without doubling everything.

It is also worth knowing before it surprises you. Re-saving a page with
an empty notes box replaces the notes you had written. If you want to
add to an entry, edit it rather than saving the address again.

Two different people saving the same address is unrelated. Your entries
are yours.

## Tags

Tags are your own: nobody else sees them, and nobody else's appear in
your list. Capitals do not make a tag different — `Watches` and
`watches` are the same tag, and the first spelling you used is the one
shown.

Every tag you have is listed under **Tags**: beside your entries on a
wide screen, after them on a narrow one. Click a tag to see only the
entries carrying it.

**A tag stops existing once nothing uses it.** Take the last entry off
`diving` and the tag disappears. This keeps the list from filling up
with typos; it also means a tag is not a place to keep something.

## Pictures

An entry can have one picture. On the form for saving or editing an
entry you can either choose a file from your device or paste the
address of a picture on the web — one or the other, not both. Hrček
keeps its own copy, so the picture stays even if the original page
takes it down.

The picture appears with the entry in your list. To swap it, add
another; to get rid of it, tick **Remove the picture** and save.
Changing an entry's title or notes never disturbs its picture.

Pictures are private, like everything else here: they are shown to you
and to nobody else, and the address of one is no use to anyone who is
not signed in as you.

PNG, JPEG, WebP, AVIF and GIF are accepted, up to 10 MB. If a file is
not really a picture, or an address will not load, Hrček says so on
the form and saves nothing. Some addresses are refused on purpose —
ones pointing back at the machine Hrček runs on, or into your home
network — because a bookmark tool has no business fetching from there.

## Fields

Beyond an address, a title and notes, you can record whatever else
matters to you. Those extras are called fields, and they are yours:
nobody else sees them, and nobody else's appear on your form.

You start with one:

- **Priority**, which is one of `high`, `medium` or `low`

It is not special. Rename it, delete it, or leave it be. "Your fields"
on the entry list is where you do it, and where you add your own.

A price field is not given to you, deliberately. A number on its own
does not say which currency it is in, and Hrček has no field that
holds a currency. If you want one, make a number field and put the
currency in its name — "Price in EUR" — so it says what it means.

### Adding one

A field has a name and a kind. The kind is either **text**, which takes
anything, or **number**, which takes only a number — so that a price of
"about fifty" is caught when you type it, rather than found later.

**The kind cannot be changed afterwards.** A number field full of
numbers cannot become a text field without deciding what happens to
every value, so Hrček does not offer it. If you picked the wrong kind,
delete the field and add it again.

Priority is the one field you cannot recreate: its list of three
choices is set when your account is made, and the form for adding a
field does not offer lists. Delete it and it is gone for good. Renaming
it is safe — it keeps its choices.

### Filling one in

Every field you have appears on the entry form. Leave one blank and that
entry simply has no value for it; they are all optional.

### Deleting one

Deleting a field **deletes its value from every entry**, and cannot be
undone. The page tells you how many entries that is before you confirm.

## Editing and deleting

Every entry has an "Edit" link. Deleting asks first, and **cannot be
undone** — there is no trash to recover from.

## Entries and scripts

If you use Hrček from a script, see [the API guide](../dev/api.md). A
script can save one entry or a batch of them, and saving works the same
way: an address you already hold is updated.
