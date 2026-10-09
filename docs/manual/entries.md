# Saving things

An entry is one thing you want to keep: a page you mean to read, a watch
you are pricing, a recipe. It holds a web address, a title, some notes,
and any labels you give it.

## Saving something

Sign in and you land on your entries. "Save something" asks for:

- **Address** — where it is on the web. The only thing actually
  required.
- **Title** — what to call it. Leave it blank and Hrček shows the
  address instead.
- **Notes** — anything you want to remember. Plain text; line breaks are
  kept.
- **Labels** — separated by commas.

## Saving the same address twice

**If you save an address you already have, Hrček updates that entry
instead of making a second one.** This is deliberate: it means a script
or an import can be re-run without doubling everything.

It is also worth knowing before it surprises you. Re-saving a page with
an empty notes box replaces the notes you had written. If you want to
add to an entry, edit it rather than saving the address again.

Two different people saving the same address is unrelated. Your entries
are yours.

## Labels

Labels are your own: nobody else sees them, and nobody else's appear in
your list. Capitals do not make a label different — `Watches` and
`watches` are the same label, and the first spelling you used is the
one shown.

Every label you have is listed under **Labels**: beside your entries on
a wide screen, after them on a narrow one. Click a label there, or on
any entry, to see only the entries carrying it; the label you are
looking at is shown in bold, and **All entries** takes you back.

### Adding and removing labels in the list

You do not have to open an entry to label it. Under each entry in your
list, **+ Label** opens a small box: type a label and press Enter or
**Add**. Several at once work too, separated by commas. Adding a label
the entry already has, in any capitals, changes nothing. The box stays
open and ready, so you can type the next one straight away — while it
is, the same control reads **× Cancel**; click it, or press Escape, to
close the box without adding anything.

Each label on an entry has a small **×** beside it that takes it off
that entry — only that one; other entries keep it.

Both happen in place: the page does not reload, you stay where you
were in the list, and the labels on the entry change before your eyes
— that is the confirmation; screen readers announce what changed. If
the change fails to go through, an error at the top of the page says
"Something went wrong. Please check and try again.", and the entry's
labels stay as they were. (With JavaScript switched off in your
browser, the page reloads and brings you back to the same place
instead, with a note at the top saying what changed.)

If you were looking at a label's own list and took that label off the
last entry carrying it, you land on all your entries instead, with a
note saying the label was removed, because that label's list no
longer exists — whether or not JavaScript is switched on.

A label can be at most 50 characters long.

**A label disappears once nothing uses it.** Take the last entry off
`diving` and the label leaves the list, and its page is gone. This
keeps the list from filling up with typos; it also means a label is not
a place to keep something. A collection following the label is not
deleted with it: see [Collections](collections.md). If that leaves the
collection with nothing in it, that notice appears straight away too,
in the usual place at the top of the page.

## Pictures

An entry can have one picture. Everything about it is under
**Picture** on the form for saving or editing an entry: you can either
choose a file from your device or paste the address of a picture on
the web — one or the other, not both. Paste the address of the picture
itself, not of the page it appears on. Hrček keeps its own copy, so
the picture stays even if the original page takes it down.

The picture appears as a small square beside the entry in your list.
When you edit an entry that has one, the form shows it under
**Picture**. To swap it, add another below it; to get rid of it, tick
**Remove the picture**, right under the picture, and save. Changing an
entry's title or notes never disturbs its picture.

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
is where you do it, and where you add your own. You reach it from
**Your account**, or from the line under the form for saving or
editing an entry — the place you are most likely to notice a field is
missing. That link opens in a new tab, so the form you were filling in
stays as it was. A field you add there shows up on the form the next
time you open it.

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

## When an entry was added

Every entry in your list shows when you saved it: "Added 7 Oct" for
something from this year, or "Added 7 Oct 2024" once a year has gone
by. Hover it (or, on a phone, press and hold) to see the full day and
date.

## Editing and deleting

Every entry has an "Edit" link, and beside it a "Delete" link, so you
do not have to open an entry to remove it. Delete asks you to confirm
first, and **cannot be undone** — there is no trash to recover from.
The question appears over the list itself, with "Keep it" ready to
press; "Keep it", or the Escape key, closes it and leaves everything as
it was. Confirming removes the entry from the list on the spot: the
page does not reload, the card simply disappears, and screen readers
announce what was deleted. If that was the last entry you had, you
see "Nothing saved yet."; if it was the last one with the label you
were looking at, you land on all your entries instead, since that
label is gone too, with a note at the top saying what was deleted. If
deleting it also left a [collection](collections.md) with nothing in
it, that notice appears straight away, in the usual place at the top
of the page.

If a delete fails to go through — your connection drops, say — the
entry is **not** removed, and an error at the top of the page says
"Something went wrong. Please check and try again."

With JavaScript switched off in your browser, the question is a page
of its own, and confirming takes you back to wherever you were
looking — page 2, or a label's filtered list — rather than to the top
of your entries. If you deleted the last entry with the label you were
looking at, that label is gone too, so you land on all your entries
instead.

On the edit page, **Save** keeps your changes and **Back to your
entries** beside it leaves without saving.

Hrček does not let changes slip away unnoticed. If you have typed
something into the form for saving or editing an entry and try to leave
without saving — by a link, by reloading, or by closing the tab — your
browser asks whether you really want to leave. The same goes for a form
Hrček has sent back to you with a problem to fix: what you typed there
is not saved yet either.

**Delete this entry** on the edit page itself is set apart at the very
bottom, in red, so it is not hit on the way to saving.

## Entries and scripts

If you use Hrček from a script, see [the API guide](../dev/api.md). A
script can save one entry or a batch of them, and saving works the same
way: an address you already hold is updated.
