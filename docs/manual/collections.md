# Collections

A collection is a set of your entries with a name. Use one to gather
the watches you are thinking about, the recipes you keep coming back
to, or anything else that belongs together.

## Two kinds, chosen once

**Chosen by hand.** You tick this collection on each entry's own
edit page, under **Collections** — as many entries as you like, one
at a time — or use **+ Collection** under the entry in your entries
list (see [Saving things](entries.md#adding-to-collections-from-the-list)).
To take an entry out, untick it there, use the **×** beside the
collection's name in your entries list, or press **Take it out** on
the collection's own page. With JavaScript on, that last one removes
the entry from the page at once, without reloading it — the entry
disappearing is the confirmation, and screen readers announce it;
take out the last one and the page says the collection is empty. If
it fails to go through, an error at the top of the page says so and
the entry stays.

**Everything with a label.** You name one of your labels, and the
collection holds every entry carrying it — including entries you save
later. Label something and it appears; take the label off and it goes.
There is nothing to add by hand.

**When the last entry loses its label, the collection stays.** Take
the label off the last entry carrying it, or delete that entry, and
Hrček tells you the collection has nothing in it now, with a link to
delete it if you no longer want it. Otherwise it waits, empty, and fills
again the moment you use the label again. Its link, if you shared one,
keeps working. The label itself leaves your list of labels in the
meantime, because nothing carries it.

**Which kind it is cannot be changed afterwards.** Switching would
either throw away everything you had picked or swallow a label's
entries whole, and neither is a surprise worth risking. If you want the
other kind, make another collection; nothing stops a single entry being
in several.

## Making one

From *Collections*, follow *Make a collection*. A name is required. A
description is optional, and anyone who can see the collection sees the
description too.

Choose the kind first. Picking *everything with a label* asks which
label to follow; picking *chosen by hand* does not ask, because there
is no label to name.

The way back from the form — *Back to your collections* while making
one, *Back to the collection* while editing — opens in a new tab, so
what you have typed stays where it is.

*Collections* lists each one's name, its kind and who can see it —
for example *Chosen by hand · Private* — and its description, if it
has one. Follow the name to open it, where *Edit* sits beside the
title.

## Order

Newest first. A collection you fill by hand orders by when you added
each entry to it, so what you put in most recently is at the top. A
collection following a label orders by when you saved the entry itself
— labelling something old does not push it to the top.

## Deleting

Deleting a collection deletes only the grouping. Every entry that was
in it stays exactly where it was, in your entries, with its labels and
everything else untouched.

## Who can see it

Every collection is one of three things, and you choose which:

**Private.** Only you can see it. There is no address to share. This is
what every new collection starts as.

**Anyone with the link.** The collection gets an address with a long
random part in it, which nobody can guess. Anyone you send it to can
open it — and can pass it on. The link is not a password: treat it as
"anyone who ends up with this may read it". Search engines are asked
not to index these pages.

**Public.** Anyone can open it, and search engines may list it. The
address is made from your public name and the collection's name, like
`/u/your-name/watches/`.

You need a public name before you can make anything public. Set one on
your account page. **If you change it later, every public address
changes with it, and links you have already shared stop working.** The
same is true of renaming a public collection: its address is made from
its name.

Changing a collection back to private closes both doors at once. An
address that used to work stops working immediately.

## Wish lists

Tick *Wish list* on a collection's edit page to turn it into a list of
things you would like to be given. Share it by link or publicly, as
above; a private wish list has nobody to give you anything.

**What visitors see.** Anyone who can open the list sees what is on it.
Somebody signed in to Hrček also sees a *Got it* button beside each
item. When they press it, the item disappears for everybody else, so
nobody gets you the same thing twice. They keep seeing it, marked *You
got this*, with an *Undo* button in case they pressed it by mistake.
Visitors who are not signed in only read the list; there is a link to
sign in.

**What you see.** Everything, as if nothing had been got — even on the
shared page itself — so the surprise survives you checking what your
family sees. When you want to know, follow *Show what has been got* on
the collection's page: each item somebody has got is marked *Got*. You
are never told who got it. The next time you open the page it is
unspoiled again.

This only works while you are signed in. Open your own link signed
out, or read its feed in a feed reader, and Hrček cannot tell it is
you: you see what any visitor sees, with whatever has been got already
gone.

**Putting something back.** Beside each item marked *Got* is *Put it
back on the list*, for a gift that fell through or a mark somebody
forgot to undo. It clears the mark, whoever made it.

**One list at a time.** The same entry can be on two wish lists, say
*Birthday* and *Christmas*. Getting it on one says nothing about the
other.

**Coming back.** Take an item off a wish list and the mark is kept, out
of sight. If you later put the item back — by hand, or by labelling it
again on a list that follows a label — Hrček tells you somebody has
already got it, and offers to put it back on the list. That message
does give away that it was got; you chose to bring it back.

Turning *Wish list* off hides the buttons and shows every item to
everybody again. Turning it back on brings the marks back as they were.

## What visitors see

The collection's name and description are always shown, and so are the
address and title of every entry in it. Everything else starts hidden.
On the collection's own form, under **Show**, tick what you want
visible: notes, pictures, labels, and each of your own fields
separately. Anything you leave unticked stays private.

**A picture you show can be opened by anyone who can see the page, on
its own address, outside the page.** That is what publishing a picture
means. Turn the picture off, or make the collection private, and it
goes back to being yours alone straight away.

## Feeds

Every collection page has a feed, at the same address with `feed/` on
the end. Put that address into any feed reader and new entries appear
there as you add them. The address is given on the collection's own
page, in the same sentence that says who can see it.

A feed is exactly as private as its page. Your private collection's
feed is yours alone and needs you to be signed in, so most readers
cannot fetch it. The feed of a collection shared by link sits under the
same hard-to-guess address, and a public collection's feed is public.

A feed shows only what its page shows: if you have not turned notes on,
they are not in the feed either.
