# Images

An entry may carry one picture, either uploaded or fetched from an
address. This page covers how it is stored, rendered and fetched; the
sections on serving and the API arrive with those layers.

## Two copies, two jobs

`EntryImage` (`src/hrcek/entries/models.py`) is a separate table with a
one-to-one link to `Entry`, not a set of columns on `Entry` itself.
SQLite stores a row's blobs inline, so keeping them on `Entry` would
mean every entry list read megabytes it did not want. Nothing joins
this table unless a page actually shows a picture.

Each image is kept twice:

| Column | What it is | Who sees it |
|---|---|---|
| `original` | The bytes exactly as they arrived | Nobody. Archival only. |
| `display` | Re-encoded AVIF, long edge ≤ 1280 px | Browsers |

The original is kept so a better rendition can always be made later —
a different format, a different size — without asking anyone to upload
anything again. It is never served, which also means the EXIF it
carries, including the GPS coordinates of where a photo was taken,
never reaches a reader. The display copy is built by decoding and
re-saving, so no metadata survives into it.

## What counts as an image

`src/hrcek/entries/imaging.py` decides. A filename proves nothing and
a `Content-Type` header proves less: bytes are an image only if Pillow
can decode them. Accepted formats are PNG, JPEG, WebP, AVIF and GIF.

SVG is refused deliberately. It is a document that can carry script,
not a picture, and serving one from our own origin would hand somebody
else's markup our cookies.

Two limits guard the decoder: `MAX_BYTES` (10 MB) is checked before
anything is parsed, and `MAX_PIXELS` (50 million) caps what a small
file is allowed to decode into, so a decompression bomb fails loudly
instead of eating the machine. Both refusals carry registered error
codes — see [error codes](error-codes.md).

## The filesystem cache

`MEDIA_ROOT` (set with `HRCEK_MEDIA_PATH`, default `media/` beside the
database) holds rendered copies at
`images/<first two characters of the checksum>/<checksum>.<format>`.
The path is content-addressed, so the same bytes always land in the
same file and a replaced image never collides with its predecessor.

**The cache is disposable.** Delete the whole directory and the next
request writes it again from the database. It exists so serving a page
does not mean pulling a blob through the ORM, not as a second source of
truth. Files are written beside the target and moved into place, so a
reader never sees a half-written file.

`EntryImage.rendition(fmt)` is the only way to read image bytes: it
returns the cached file when there is one and rebuilds it when there is
not. Asking for a format other than AVIF re-encodes from the original,
which is how an older browser gets WebP.

## Fetching from an address

`src/hrcek/entries/fetching.py` is the one place Hrček makes an
outbound request on somebody else's instruction. That is server-side
request forgery waiting to happen, and it is why the original entries
design put images last: a pasted address can name the machine Hrček
runs on, a printer on the home network, or a cloud metadata endpoint
that hands credentials to anything that asks.

The rules, all of them enforced on every redirect hop:

1. **http and https only.** A redirect may not leave those schemes —
   checked after resolving the target, because a relative redirect can
   otherwise produce a `file://` address.
2. **Every resolved address must be public.** Not just the one that
   would be used: a host answering with one public and one private
   address is refused outright, because the connection could land on
   either. Refused ranges are loopback, private, link-local,
   unique-local, multicast, reserved, unspecified, carrier-grade NAT,
   and IPv4-mapped IPv6 addresses wrapping any of those — which is how
   `::ffff:127.0.0.1` would otherwise slip through.
3. **The connection goes to the checked address, not the name.** The
   socket is opened to the address that passed the check and handed to
   the HTTP connection already made. Letting `http.client` connect by
   name would resolve a second time, and a DNS answer that changes in
   between is exactly the attack the checking exists to stop. The name
   is still used for the `Host` header and for TLS, so certificate
   validation is unaffected.
4. **Bounded.** At most three redirects, five seconds, and reading
   stops the moment the body passes `MAX_BYTES` — a declared
   `Content-Length` over the cap is refused before any body is read.

There is **no domain allowlist**: any public host is fair game. The
defence is about where an address points, not who owns it.

Nothing in this module decides whether what came back is an image. The
caller hands the bytes to `imaging.prepare`, which trusts the
`Content-Type` header no more than it trusts a filename.

`tests/entries/test_fetching.py` is the security boundary for all of
this. Read it before changing anything here.

## Serving

`GET /entries/<pk>/image/` (`entries:image`) is the only way a picture
reaches a browser. It goes through Django rather than off the web
server's disk, because an unguessable filename is not access control.

### Who may see a picture

Either of two things is enough:

- the requester owns the entry, or
- the entry sits in at least one collection that is **shared** (by
  link or in the open) **and** has `show_images` on.

`Entry.is_publicly_visible()` answers the second, counting both kinds
of collection — a label collection reaches its entries through its
label rather than through membership rows.

Two consequences, both deliberate:

- **A shared picture is readable on its own address**, outside the page
  that shows it, by anybody who has that address. That is what
  publishing a picture means, and the collection form says so before
  anybody ticks the box.
- **Taking the sharing away takes the picture back.** The question is
  asked on every request, so turning `show_images` off, or making the
  collection private, refuses the very next one.

A request for a private picture from somebody signed out is redirected
to sign in; from another account it is a **404, never a 403** — a 403
would confirm that the entry exists.

Cache headers follow the same split: a private picture is
`private, max-age=0, must-revalidate`, so no shared cache may hold one
person's picture; a public one is `public, max-age=300`, so a page of
them is not re-fetched on every scroll.

The response negotiates its format. A browser whose `Accept` header
mentions `image/avif` gets the stored display copy; anything else gets
WebP, rendered from the archived original on first request and cached
from then on. `Vary: Accept` goes out with every response so a cache
never crosses the two.

Caching is `private, max-age=0, must-revalidate` with an `ETag` of the
checksum and format, so a shared cache never holds one person's
picture, and an unchanged image comes back as a 304 instead of bytes.

The body is sent whole rather than streamed: a display copy is a couple
of hundred kilobytes, and a streaming response keeps a file descriptor
open until something consumes it.

## The entry list

The list joins the image table (`select_related("image")`) so the page
does not ask once per entry, and immediately defers both blob columns.
The page needs only to know whether an entry has a picture, and pulling
two pictures per row to render a tag would undo the reason the blobs
live in their own table. `test_the_list_query_leaves_the_blobs_in_the_table`
holds that line.

A picture shows as a 6rem square thumbnail beside the entry's text,
cropped to fit with `object-fit: cover`, so the `<img>` carries fixed
dimensions and the list does not jump about as pictures arrive. The
browser still downloads the display copy and scales it down; at family
scale a separate thumbnail rendition is not worth its storage. The
thumbnail's link repeats the title's, so it is `tabindex="-1"` and
`aria-hidden`: one stop per entry for the keyboard and screen reader.
A shared collection page shows pictures the same way.

## On the form

The entry form takes either a file or an address, never both, and
offers a checkbox to remove the picture. The form template lays these
out by hand rather than with `form.as_p`: the current picture, the
remove box directly beneath it (shown only when there is a picture to
remove), then the file and address inputs, all in one `<fieldset
class="picture">`. `EntryForm.entry_fields()` and `custom_fields()`
supply the other groups, and `entries/_field.html` marks each input up
as `as_p` would, so the form styles still apply. The bytes are validated in
`EntryForm.clean`, so a refusal comes back as a sentence beside the
input with the rest of the form still filled in — the error code goes
to the logs and to API clients, never onto the page.

Saying nothing about the picture leaves it alone. Editing a title
cannot quietly drop one.

## Through the API

Reading an entry describes its picture or says `null`; the bytes never
appear in JSON. `EntryOut.resolve_image` builds `{url, width, height}`,
where the URL is the access-controlled serving view.

Writing splits by source, because the two have different shapes:

| What | Where |
|---|---|
| An address | `image_url` on `EntryIn`, so it works in a batch too |
| An upload | `POST /api/entries/{pk}/image`, multipart |
| Removal | `DELETE /api/entries/{pk}/image` |

`image_url` is a patch, like `fields` and unlike every other attribute
on `EntryIn`: omitting it leaves any existing picture alone, so a
client written before pictures existed cannot strip one by saving an
entry it read. Removal is therefore explicit, never an empty string.

The fetch happens inside `save_entry`'s transaction. If the address
turns out to point somewhere we will not go, the entry is not left
saved with no picture and no explanation — the whole call fails with
the address's own code.

Both endpoints sit **below** `/by-url/` in `api.py`, as that route's
docstring requires: declared above it, `by-url` would be read as an id.
