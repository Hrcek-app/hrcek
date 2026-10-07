# The API

Hrček has a small HTTP API for saving entries from scripts and other
programs. This page is written for somebody building a client.

## What it is for, and what it is not

The API **saves and reads entries**. It deliberately cannot create
accounts, change a password, or manage API tokens: those are web-only,
because each involves a confirmation or a re-authentication step that
does not belong in a script. If your client needs one of them, send the
person to the website.

## Base address and stability

Everything lives under `/api/` on whatever address your Hrček is served
from. There is no version in the path. The API is at `1.0.0`, reported
in the OpenAPI schema.

What is stable: paths, the error envelope, and **error codes**. What is
not: the human-readable text of messages, which is translated and may be
reworded. Branch on `code`, never on `message`.

## Authentication

Every endpoint requires credentials except `GET /api/health` and
`POST /api/auth/login`.

**Use a bearer token.** Create one from the clients page at
`/accounts/me/clients/`, or with the call below; it is shown once, so
copy it then. Tokens look like `hrcek_` followed by random
characters.

```bash
curl -H "Authorization: Bearer hrcek_8Xr2mQ7pLk4vNs1TzYbW..." \
     https://hrcek.example.com/api/auth/me
```

Session cookies also work, which is how the website itself talks to the
API. **Scripts should use tokens**: a session makes unsafe requests
subject to CSRF checks, and a token does not. A token is refused if it
is unknown, revoked, expired, or belongs to a disabled account.

Without credentials:

```json
{"error": {"code": "HRC-AUTH-0003",
           "message": "You must sign in to do that.", "details": {}}}
```

### POST /api/auth/tokens

Create a token. `name` is required — it is how you will recognise this
client months from now. `expires_at` is optional; leave it out and the
token does not expire.

```bash
curl -X POST https://hrcek.example.com/api/auth/tokens \
  -H "Content-Type: application/json" \
  -b cookies.txt \
  -d '{"name": "backup script", "expires_at": "2027-01-01T00:00:00Z"}'
```

**201** with the token:

```json
{"id": 4, "name": "backup script",
 "token": "hrcek_8Xr2mQ7pLk4vNs1TzYbW...",
 "created_at": "2026-09-18T09:12:44.201Z",
 "expires_at": "2027-01-01T00:00:00Z"}
```

Every call makes a new token; nothing is reused. **`token` appears in
this reply and nowhere else** — only a hash of it is stored, so if you
lose the value, nobody can look it up for you, including whoever runs
this Hrček. Make another one instead.

**This call needs a session, not a token.** Signing in with
`POST /api/auth/login` and keeping the cookie is the way to reach it
from a script. A token that could mint tokens would make revoking a
leaked one pointless — the holder would simply issue a replacement —
so presenting a bearer token here is refused:

```json
{"error": {
  "code": "HRC-AUTH-0006",
  "message": "Creating a token needs a signed-in session, not another token.",
  "details": {}
}}
```

A missing, blank or over-long name, or an expiry already in the past,
comes back as **422** `HRC-CORE-0002` with the offending field named in
`details.fields`.

To remove a token, use the clients page at `/accounts/me/clients/`.

### POST /api/auth/tokens/exchange

Trade an email address and password directly for a token. Same body
as above plus `identifier` and `password`, same **201** reply.

```bash
curl -X POST https://hrcek.example.com/api/auth/tokens/exchange \
  -H "Content-Type: application/json" \
  -d '{"name": "Hrček extension (Firefox on macOS)",
       "identifier": "nina@example.com",
       "password": "…"}'
```

This exists for clients that cannot hold a session. A browser
extension is the case: Firefox attaches `Origin: moz-extension://<uuid>`
to every request it makes, the uuid differs for every install so it
cannot be trusted in advance, and Django refuses the origin before it
reads anything else. An extension can therefore sign in and then do
nothing unsafe with the session it was given.

The route reads **no session at all**, which is what makes it safe
without a CSRF check: nothing here can be reached with a cookie alone,
so a signed-in browser visiting a hostile page gains an attacker
nothing. Being signed in does not stand in for the password either.

Refusals reuse the sign-in codes: **401** `HRC-AUTH-0001` for a wrong
password, an unknown identifier or a disabled account — one answer for
all three, so the route cannot be used to discover who has an account
— and **403** `HRC-AUTH-0002` for an address that has never been
confirmed. A missing, blank or over-long name, or an expiry in the
past, is **422** `HRC-CORE-0002`.

**It is rate-limited, two ways.** It is unauthenticated and it hands
out a durable credential, so every call counts, successful or not, and
past either limit it answers **429**:

| Counted per | Default | Setting |
|---|---|---|
| Calling address | 10/h | `HRCEK_TOKEN_EXCHANGE_RATE` |
| Account named in the request | 10/h | `HRCEK_TOKEN_EXCHANGE_ACCOUNT_RATE` |

Both are needed. An address limit alone does nothing against somebody
with a pool of addresses working through one account's password, and
an account limit alone does nothing against somebody sweeping many
accounts.

Which address counts depends on `HRCEK_PROXY_COUNT`, the number of
reverse proxies in front. It defaults to **0**, meaning the socket is
believed and forwarding headers are ignored. That default is
deliberate: left unset, django-ninja takes the caller's identity from
`X-Forwarded-For` whenever the header is present, and a header is
whatever the caller says it is — so the limit could be sidestepped by
sending a different value each time. Behind a single nginx or Caddy,
set it to 1, or every caller will be counted as the proxy and share
one allowance.

Counters live in Django's cache, which is per-process local memory by
default: with one process that is exactly right, and with several each
keeps its own tally.

Store the token and nothing else. There is no way to look it up
again, and the password should not be kept once the token exists.

## Errors

Every failure has the same shape and a truthful status code:

```json
{"error": {"code": "HRC-CORE-0002",
           "message": "The submitted data is not valid.",
           "details": {"fields": {"url": ["Enter a valid URL."]}}}}
```

`code` identifies the condition and never changes meaning. `message` is
for showing a person and is translated. `details` carries whatever
machine-readable context the condition has, and may be empty.

Statuses mean what they usually mean: 401 you are not authenticated, 403
you are not allowed, 404 it is not there, 409 a conflict, 422 the input
is wrong, 500 our fault. A failure is never returned as 2xx.

Every code is listed in [error codes](error-codes.md).

## Saving an entry

`POST /api/entries/` — the main thing the API is for.

```bash
curl -X POST https://hrcek.example.com/api/entries/ \
  -H "Authorization: Bearer $HRCEK_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com/watch",
       "title": "A watch",
       "notes": "38mm, sapphire",
       "tags": ["watches", "diving"],
       "fields": {"price": "129.00", "priority": "high"}}'
```

Only `url` is required. Everything else defaults to empty, so a minimal
client can post a bare link and nothing else. `tags` holds the entry's
labels — the web pages call them labels; the API, the code and the
database keep the older name `tags`. Anything added in a later
version will have a default too, so a client that does not know about it
keeps working.

**201** when the entry was created:

```json
{"id": 1,
 "url": "https://example.com/watch",
 "title": "A watch",
 "notes": "38mm, sapphire",
 "tags": ["diving", "watches"],
 "fields": {"Price": "129", "Priority": "high"},
 "created_at": "2026-09-13T12:28:12.937Z",
 "updated_at": "2026-09-13T12:28:12.937Z"}
```

**200** when an entry for that address already existed and was updated.
The status is how you tell which happened without comparing ids.

### Saving an address you already hold replaces the entry

You cannot hold the same address twice. Posting one you already have
updates that entry — which is what makes re-running an import safe.

**It is a replace, not a patch.** Fields you leave out take their
defaults, so they are cleared. Posting this:

```json
{"url": "https://example.com/watch", "title": "A watch, revisited"}
```

over the entry above leaves `notes` empty and `tags` empty — but note
that the field values survive:

```json
{"id": 1, "url": "https://example.com/watch",
 "title": "A watch, revisited", "notes": "", "tags": [],
 "fields": {"Price": "129", "Priority": "high"},
 "created_at": "2026-09-13T12:28:12.937Z",
 "updated_at": "2026-09-13T12:28:12.953Z"}
```

If your client means to change one attribute, read the entry first —
[the lookup](#reading-one-entry-by-its-address) is there for exactly
that — and send the whole thing back. There is no PATCH.

**`fields` is the one exception**, and the next section says why.

Addresses are matched almost exactly: surrounding whitespace is
ignored and the scheme and host are lowercased, and nothing else. A
trailing slash, a `www.`, or a tracking parameter makes it a different
address.

## Fields

Every account has fields of its own: extra things to record about an
entry, beyond its address, title and notes. A new account starts with
one, **Priority**, which takes `high`, `medium` or `low`. It can be
renamed or deleted by its owner, and any number of others added, so
**do not hard-code any of them** — read
[`GET /api/fields/`](#get-apifields), or read what came back on an
entry.

The examples below use a number field called Price. It is not one an
account is given: a price without a currency says too little, and
Hrček has no field type that holds a currency, so anybody wanting one
makes it themselves.

```json
{"url": "https://example.com/watch",
 "fields": {"price": "129.00", "priority": "high"}}
```

Names match without regard to case, so `price`, `Price` and `PRICE` are
the same field.

**Values come back as strings, always.** You never have to guess whether
a price arrives as `129` or `"129"`. On the way in a JSON number is
accepted too, because refusing `129.00` written as a number would be
pedantic. A number comes back the way it was most likely typed —
`"129.00"` becomes `"129"`, `"38.50"` becomes `"38.5"`.

The key on the way out is the field's name as its owner spells it, not
as you sent it: send `"price"` and `"Price"` comes back.

### `fields` is patched, not replaced

This is the one place this API is not uniform, and it is deliberate.

**The names you send are set. Every field you do not name keeps what it
had.** So this:

```json
{"url": "https://example.com/watch", "fields": {"priority": "low"}}
```

changes the priority and leaves the price alone:

```json
{"id": 1, "url": "https://example.com/watch",
 "title": "", "notes": "", "tags": [],
 "fields": {"Price": "129", "Priority": "low"},
 "created_at": "2026-09-13T12:28:12.937Z",
 "updated_at": "2026-09-13T12:28:12.966Z"}
```

Sending `"fields": {}`, or leaving `fields` out entirely, therefore
changes nothing.

**To clear a value, name it with an empty string:**

```json
{"url": "https://example.com/watch", "fields": {"price": ""}}
```

```json
{"id": 1, "url": "https://example.com/watch",
 "title": "", "notes": "", "tags": [],
 "fields": {"Priority": "low"},
 "created_at": "2026-09-13T12:28:12.937Z",
 "updated_at": "2026-09-13T12:28:12.979Z"}
```

The reason for the exception is that a client need not know about fields
at all. If leaving `fields` out cleared them, an importer written before
they existed would wipe somebody's prices every time it re-ran. Losing
data should never be the default; clearing is worth saying out loud.

### When a field is wrong

A name nobody has is **422** with `HRC-FIELD-0001`, not a silent drop,
because it is almost always a typo:

```json
{"error": {"code": "HRC-FIELD-0001",
           "message": "There is no field with that name.",
           "details": {"field": "colour"}}}
```

A value the field cannot hold is ordinary validation — **422** with
`HRC-CORE-0002`, and `details.fields` keyed by the field's name:

```json
{"error": {"code": "HRC-CORE-0002",
           "message": "The submitted data is not valid.",
           "details": {"fields": {"Price": ["This field takes a number."]}}}}
```

```json
{"error": {"code": "HRC-CORE-0002",
           "message": "The submitted data is not valid.",
           "details": {"fields":
             {"Priority":
               ["This field must be one of: high, medium, low."]}}}}
```

Nothing is saved in either case — not the entry, and not the fields that
were fine.

## Saving many entries at once

`POST /api/entries/batch/` takes an array of the same objects, up to 200
per call, and answers with one result per row **in the order you sent
them**.

```bash
curl -X POST https://hrcek.example.com/api/entries/batch/ \
  -H "Authorization: Bearer $HRCEK_TOKEN" \
  -H "Content-Type: application/json" \
  -d '[{"url": "https://example.com/a", "fields": {"price": "10"}},
       {"url": "not a url"},
       {"url": "https://example.com/b", "fields": {"colour": "red"}}]'
```

```json
{"results": [
  {"index": 0, "status": "created", "id": 2, "error": null},
  {"index": 1, "status": "error", "id": null,
   "error": {"code": "HRC-CORE-0002",
             "message": "The submitted data is not valid.",
             "details": {"fields": {"url": ["Enter a valid URL."]}}}},
  {"index": 2, "status": "error", "id": null,
   "error": {"code": "HRC-FIELD-0001",
             "message": "There is no field with that name.",
             "details": {"field": "colour"}}}
]}
```

`status` is `created`, `updated` or `error`. `id` is set for the first
two; `error` for the third.

**The status code tells you whether anything failed**: **200** if every
row succeeded, **207** if any did not. Check the status first, then walk
the results.

**The call is not atomic, on purpose.** Rows that validate are saved
even when siblings fail. A 300-row import does not die on row 200, and
re-running it fixes the rows that were wrong while the ones that were
right are simply updated in place. Your client has to be able to handle
a partially applied batch; the per-row results are what makes that
possible.

Sending more than 200 rows refuses the **whole** request with
`HRC-ENTRY-0001` and saves nothing — a half-applied batch with no report
would be worse than none.

## Reading entries

`GET /api/entries/` returns your own entries, newest first, paginated.

```json
{"items": [{"id": 2, "url": "https://example.com/a",
            "title": "", "notes": "", "tags": [],
            "fields": {"Price": "10"},
            "created_at": "2026-09-13T12:28:26.331Z",
            "updated_at": "2026-09-13T12:28:26.331Z"}],
 "count": 2}
```

`count` is the total across all pages. Use `?limit=` and `?offset=` to
page through it.

You only ever see your own entries. Two people may hold the same
address; their entries are unrelated.

### Reading one entry by its address

`POST /api/entries/lookup` answers the entry you hold at an address, so
your client can look before it writes.

```bash
curl -X POST https://hrcek.example.com/api/entries/lookup \
  -H "Authorization: Bearer $HRCEK_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com/watch"}'
```

**A POST, and the address goes in the body**, even though this reads
rather than writes. An address is the private half of an entry — what
somebody reads — and a query string is written into the web server's
access log, into any proxy in front of it, and onto Sentry events.
None of those are Hrček's to control, so the address never goes near
one. Hrček's own log records the path and never the query string.

```json
{"id": 1, "url": "https://example.com/watch",
 "title": "", "notes": "", "tags": [],
 "fields": {"Priority": "low"},
 "created_at": "2026-09-13T12:28:12.937Z",
 "updated_at": "2026-09-13T12:28:12.979Z"}
```

**404** if you do not hold that address:

```json
{"error": {"code": "HRC-CORE-0003",
           "message": "The requested resource does not exist.",
           "details": {"url": "https://example.com/nothing"}}}
```

Somebody else holding it answers 404 too, not 403: a 403 would tell you
that somebody does.

This is the call to make before deciding whether to save. Posting is an
upsert, so without it a client cannot tell a new address from one it is
about to write over, and cannot read what an entry says in order to
merge into it. Fetching the whole list and filtering locally is the
wrong shape once somebody holds thousands of entries.

The address is matched by the same rule the save uses — whitespace
trimmed, scheme and host lowercased — so the two always agree on what
counts as the same address.

## Pictures

An entry may carry one picture. Every entry in a reply describes it,
or says `null`:

```json
{"image": {"url": "/entries/1/image/", "width": 1280, "height": 960}}
```

The bytes never appear in JSON. `url` is an address to fetch, and it
answers only to the account that owns the entry, so send your
credentials with it as you would anywhere else.

### Giving an address

Add `image_url` to any entry you post, including inside a batch.
Hrček fetches it, keeps the original, and builds the copy it serves.

```bash
curl -X POST https://hrcek.example.com/api/entries/ \
  -H "Authorization: Bearer $HRCEK_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com/watch",
       "image_url": "https://example.com/watch.jpg"}'
```

Like `fields`, and unlike every other attribute, **leaving `image_url`
out changes nothing** — a client that predates pictures cannot strip
one by saving an entry. There is no way to remove a picture by posting
an entry; use the DELETE below.

Hrček will not fetch from just anywhere. Addresses that resolve to a
private, loopback or link-local network, to cloud metadata, or to
carrier-grade NAT are refused, as are non-http schemes, and the rules
are re-applied to every redirect. See
[images](images.md#fetching-from-an-address).

### POST /api/entries/{pk}/image

Upload a picture, replacing whatever the entry had. Multipart, not
JSON: base64 would inflate every upload by a third for nothing.

```bash
curl -X POST https://hrcek.example.com/api/entries/1/image \
  -H "Authorization: Bearer $HRCEK_TOKEN" \
  -F "file=@watch.jpg"
```

The entry comes back, with its new `image`. **404** if the entry is
not yours — never 403, which would tell you it exists.

### DELETE /api/entries/{pk}/image

Remove the picture. **204** with no body when it is gone, **404** when
there was none to remove.

```bash
curl -X DELETE https://hrcek.example.com/api/entries/1/image \
  -H "Authorization: Bearer $HRCEK_TOKEN"
```

### When a picture is refused

PNG, JPEG, WebP, AVIF and GIF are accepted, up to 10 MB. Whether
something is an image is decided by decoding it, so a `Content-Type`
header or a filename changes nothing, and SVG is refused outright — it
is a document that can carry script.

| Code | Why |
|---|---|
| `HRC-IMAGE-0001` | Not an image Hrček can read |
| `HRC-IMAGE-0002` | Larger than the limit |
| `HRC-IMAGE-0003` | Damaged, truncated, or too many pixels |
| `HRC-IMAGE-0004` | The address is not http or https |
| `HRC-IMAGE-0005` | The address points somewhere Hrček will not go |
| `HRC-IMAGE-0006` | The fetch failed |

All of them are 422, in the usual envelope. Full text in
[error codes](error-codes.md).

## What this account has defined

Two read-only calls, so a client can fit its own interface to whoever
is using it. Both are created and renamed through the web pages; there
is no way to change them here.

### GET /api/fields/

The fields this account's entries may carry.

```bash
curl https://hrcek.example.com/api/fields/ \
  -H "Authorization: Bearer $HRCEK_TOKEN"
```

```json
{"items": [{"name": "Price", "kind": "number", "options": []},
           {"name": "Priority", "kind": "choice",
            "options": ["high", "medium", "low"]}],
 "count": 2}
```

`kind` is `text`, `number` or `choice`. `options` is empty except for
a choice field, where it is the only way to know what the choices are.

**`name` is the key**: it is what an entry's `fields` object uses, so
what you read here is what you write back. Do not hard-code these —
they are renamed and deleted by their owner, and every account starts
with its own copy.

### GET /api/labels/

This account's labels, in name order.

```bash
curl -G https://hrcek.example.com/api/labels/ \
  -H "Authorization: Bearer $HRCEK_TOKEN" \
  --data-urlencode "starts_with=wat"
```

```json
{"items": [{"name": "watches"}, {"name": "water"}], "count": 2}
```

`starts_with` narrows the list to labels beginning with it, ignoring
capitals and surrounding space. It is a literal, not a pattern, so
punctuation somebody types into an autocomplete box means itself. Omit
it and you get the lot.

The same call serves an autocomplete and a full list because they
differ only by that filter.

Labels come back in alphabetical order, ignoring capitals.

**`count` is how many labels match, not how many this page carries**,
so a client knows whether to ask again. A page holds up to a thousand,
which is both the default and the maximum: asking plainly returns
everything up to that many, and asking for more is refused with
**422** rather than quietly truncated — a client that believed it had
asked for five thousand would page wrongly.

To read the rest, **pass the last name you were given as `after`**:

```bash
curl -G https://hrcek.example.com/api/labels/ \
  -H "Authorization: Bearer $HRCEK_TOKEN" \
  --data-urlencode "after=watches"
```

Keep going until a page comes back empty. There is no offset, on
purpose: an offset counts rows, and the rows move. Add a label that
sorts earlier while somebody is reading and every later row shifts
along by one, so the next offset lands past a row that was never
served. A cursor names a place in the order instead, and that place
does not move. `after` need not be a label that exists — whatever
comes after it alphabetically is returned — so a label deleted
mid-read costs nothing.

`after` works with `starts_with` as well, should an account ever have
more than a thousand labels sharing a prefix.

A label that no entry carries is not listed: they are removed when the
last entry using one lets it go.

## The other endpoints

`GET /api/health` needs no credentials and reports that the service is
up. Useful for monitoring.

```json
{"status": "ok", "service": "hrcek", "version": "0.1.0",
 "message": "Service is running."}
```

`POST /api/auth/login` takes `{"identifier": "...", "password": "..."}`
and starts a **session**. `identifier` is an email address or a display
name. It answers 401 with `HRC-AUTH-0001` for bad credentials and 403
with `HRC-AUTH-0002` if the address has never been confirmed. Scripts
do not need this; use a token.

`POST /api/auth/logout` ends that session and answers 204.

`GET /api/auth/me` reports who you are:

```json
{"email": "nina@example.com", "display_name": null}
```

It is the cheapest way for a client to check that its token works.

## Languages

Error messages are translated. Send `Accept-Language: sl` and you get
Slovenian; anything unrecognised falls back to English. Codes never
change, which is why clients should branch on them.

## Machine-readable schema

The OpenAPI schema is committed at [`../api/openapi.json`](../api/openapi.json),
so you can generate a client without running Hrček:

```bash
openapi-generator-cli generate -i docs/api/openapi.json -g python
```

A hook keeps it in step with the code; it cannot drift from what the
server actually serves.

A running instance also serves interactive documentation at `/api/docs`,
where each endpoint can be tried in the browser. **Production disables
it** (`HRCEK_API_DOCS=false`), so on a deployed Hrček use the committed
schema.
