# Error codes

Every failure a client can see has a code. Codes are stable: the text
of a message may be reworded or translated, but a code never changes
meaning and is never reused.

## Format

`HRC-<DOMAIN>-<NNNN>`

`DOMAIN` is three to six uppercase letters naming the area (`CORE`,
later `ITEM`). `NNNN` is a four-digit number unique within that domain.
`HRC-TEST-9xxx` is reserved for the test suite and must never be used by
real code.

## Adding a code

Register it in the owning app's `errors.py`:

```python
from django.utils.translation import gettext_lazy as _

from hrcek.core.errors import register

ITEM_NOT_FOUND = register("HRC-ITEM-0001", 404, _("The saved item does not exist."))
```

Then add a row to the table below. A test fails if a registered code is
missing here, or if this file lists a code that no longer exists.

Raise it with `HrcekError`:

```python
raise HrcekError(ITEM_NOT_FOUND, {"item_id": item_id})
```

`details` carries machine-readable context. It is never translated and
must never contain anything private.

## Registered codes

`HRC-OPS` codes are reported by management commands on the host, never
over HTTP, so they have no status.

| Code | Status | Meaning |
|---|---|---|
| `HRC-CORE-0001` | 500 | An unexpected error occurred. The traceback is in the logs and in Sentry; the client is told nothing more. |
| `HRC-CORE-0002` | 422 | The submitted data is not valid. `details.fields` lists the offending fields. |
| `HRC-CORE-0003` | 404 | The requested resource does not exist. |
| `HRC-AUTH-0001` | 401 | The email address or password is not correct. Also returned for a disabled account, deliberately. |
| `HRC-AUTH-0002` | 403 | The account exists and the password was right, but the email address is not confirmed. |
| `HRC-AUTH-0003` | 401 | The endpoint needs a session or a bearer token and got neither. |
| `HRC-AUTH-0004` | 401 | The bearer token is unknown, revoked, expired, or belongs to a disabled account. |
| `HRC-AUTH-0005` | 403 | A session-authenticated unsafe request arrived without a valid CSRF token. |
| `HRC-AUTH-0006` | 403 | A bearer token tried to create another token. Only a signed-in session may mint one, so that revoking a leaked token actually ends the access. |
| `HRC-ACCT-0001` | 403 | The address is neither individually allowed nor on an allowed domain. |
| `HRC-ACCT-0002` | 400 | The invitation link is unknown, expired, revoked or already used. |
| `HRC-ACCT-0003` | 400 | The confirmation link is expired, tampered with, or refers to a deleted user. |
| `HRC-ACCT-0004` | 409 | The requested display name belongs to somebody else, ignoring case. |
| `HRC-ACCT-0005` | 400 | The email change link is expired, tampered with, or superseded by a later request. |
| `HRC-ENTRY-0001` | 422 | More rows in one batch than the limit allows. The whole request is refused; nothing is saved. |
| `HRC-FIELD-0001` | 422 | The request named a field this person does not have. `details.field` is the name as sent. |
| `HRC-ACCT-0006` | 409 | Another account already uses that email address. Shown inline on the form too, where the status is 200 because the person can simply pick another. |
| `HRC-COLL-0001` | 404 | An entry belonging to somebody else was offered to a collection. 404, not 403: a 403 would confirm the entry exists. |
| `HRC-COLL-0002` | 422 | Entries cannot be added by hand to a collection that follows a label; its membership comes from the label. |
| `HRC-IMAGE-0001` | 422 | The bytes are not a raster image Pillow can decode, or are in a format we do not accept. SVG is refused on purpose. |
| `HRC-IMAGE-0002` | 422 | The image is larger than the byte limit. `details.limit_bytes` carries the limit. |
| `HRC-IMAGE-0003` | 422 | The image decoded as a known format but could not be read — truncated, damaged, or too many pixels. `details.limit_pixels` appears in the last case. |
| `HRC-IMAGE-0004` | 422 | The address is not http or https, has no host, or a redirect tried to leave those schemes. `details.scheme` carries what was asked for. |
| `HRC-IMAGE-0005` | 422 | The address resolves somewhere Hrček refuses to go: loopback, a private or link-local network, cloud metadata, or carrier-grade NAT. `details.address` is the resolved address. |
| `HRC-IMAGE-0006` | 422 | The fetch failed: the host did not resolve, the connection broke, the answer was not 200, or there were too many redirects. `details` carries `status`, `host` or `redirects`. |
| `HRC-OPS-0001` | — | The database has migrations this release does not know: a newer release ran here. The container refuses to start. Roll back using the newer release, or restore a snapshot. `details.migrations` lists them. |
| `HRC-OPS-0002` | — | A rollback named a release that never ran against this database, so its migration state is unknown. |
| `HRC-OPS-0003` | — | A rollback named the release that is already current. |
| `HRC-OPS-0004` | — | A snapshot could not be written or read (disk full, folder not writable) or failed `PRAGMA integrity_check`. A half-written file is removed. |
| `HRC-OPS-0005` | — | The snapshot named for a restore does not exist. |
| `HRC-OPS-0006` | — | `releases.json` is not valid JSON or not a list of release entries. |
| `HRC-OPS-0007` | — | The file named for a restore is not named like a snapshot, so the release it holds is unknown. |
| `HRC-OPS-0008` | — | `releases --current` found no release recorded. |
| `HRC-OPS-0009` | — | A rollback named a release whose migrations this code does not know: it is newer. Deploy it instead. |
| `HRC-OPS-0010` | — | `restore --earliest-since` was given a time not in the form `20260924T100000Z`. |
| `HRC-OPS-0011` | — | Migrating down failed partway. The `pre-rollback` snapshot (`details.snapshot`) was put back, so the database is exactly as before the rollback began. |
| `HRC-OPS-0012` | — | `releases.json` could not be written: its folder is missing or not writable. No temporary file is left behind. |

## Response shape

```json
{
  "error": {
    "code": "HRC-CORE-0003",
    "message": "The requested resource does not exist.",
    "details": {}
  }
}
```

`message` is translated into the language negotiated from
`Accept-Language`. Clients that need to branch on a failure must switch
on `code`, never on `message`.
