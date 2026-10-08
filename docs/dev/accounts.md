# Accounts

The `hrcek.accounts` app owns identity: the user model, sign-in,
invitations, self-signup, email confirmation, password reset, and API
credentials.

## The user model

`User` is keyed on `email` and has an optional `display_name` that
doubles as a sign-in identifier. Password and `last_login` come from
`AbstractBaseUser`; permissions from `PermissionsMixin`.

`is_active` is redeclared as a real field on purpose: the base class
defines it as a class attribute fixed at `True`, and only a field can
be switched off from the admin.

**Why `email` carries both `unique=True` and a `Lower()` constraint.**
The constraint provides case-insensitive uniqueness. `unique=True` is
not redundant with it: Django's `auth.E003` check requires
`USERNAME_FIELD` to be unique, and satisfying that through a
`UniqueConstraint` alone downgrades the error to the `auth.W004`
*warning*. `tests/test_boot.py` asserts `manage.py check` writes nothing
to stderr, so that warning would fail the suite.

`display_name` is `NULL` when unset, never `""`. SQL treats NULLs in a
unique index as distinct, which is what lets any number of users have
no display name while set ones stay unique.

A display name may not contain `@`. That single rule is what keeps the
two identifier spaces from overlapping, so sign-in needs no precedence
rule between them.

## Why email confirmation is not checked in the backend

`EmailOrDisplayNameBackend` verifies the password and `is_active`, and
nothing else. A backend can only return a user or `None`, so folding
the confirmation check in would collapse "wrong password" and
"unconfirmed address" into one indistinct failure.

Instead every entry point checks `is_email_confirmed` *after* the
password is verified — the API login endpoint and
`HrcekAdminSite.has_permission`. This leaks nothing, because reaching
that check already required the correct password.

A disabled account is a different matter: the backend returns `None`,
so callers cannot tell it from a wrong password without hashing twice.
It therefore reports `HRC-AUTH-0001` like any other failure, which is
also the better answer against enumeration.

## API authentication, and why the order matters

The root API declares:

```python
auth = [ApiTokenAuth(), SessionAuth()]
```

**Reversing this breaks every token-authenticated `POST`.** django-ninja
runs auth callbacks in sequence and aborts the whole chain on the first
exception. Ninja's `SessionAuth` performs its CSRF check inside
`_get_key()`, before it even reads the session cookie, and raises on any
unsafe request without a CSRF token. Listed first, it rejects a request
carrying a perfectly valid bearer token before anything looks at the
token.

`test_a_token_post_needs_no_csrf_token` is the regression test. It uses
`Client(enforce_csrf_checks=True)` deliberately: the default test client
sets `_dont_enforce_csrf_checks`, which makes ninja's check pass
regardless, so the test would pass with the order wrong.

Ninja's own errors are mapped onto our contract: `AuthenticationError`
becomes `HRC-AUTH-0003`, and the bare `HttpError(403, "CSRF check
Failed")` becomes `HRC-AUTH-0005`.

**Accepted risk: login is not CSRF-protected.** `POST /api/auth/login`
uses `auth=None`, so ninja performs no CSRF check on it. A cross-site
form could log somebody into an account the attacker controls; it
cannot read anything or act as the victim. Requiring a CSRF token to
sign in would mean handing every client a cookie round-trip first, and
scripts should use bearer tokens rather than session login anyway.

## The pages

`/` is the sign-in page: `LoginView` with `redirect_authenticated_user`,
so anyone already signed in is sent to `/accounts/me/`. It always links
to the password reset, and links to signup only while
`allowlist.is_open()` — with both tables empty there is nothing to
offer, and a link to a form that refuses every visitor would be a dead
end.

**A gap that was closed here.** Django's `AuthenticationForm` checks only
`is_active`, so the web form used to admit unconfirmed accounts that the
API refused with `HRC-AUTH-0002`.
`ConfirmedUserAuthenticationForm` overrides `confirm_login_allowed()` so
both doors agree. Anyone adding a third way in needs to apply the same
check: email confirmation is deliberately *not* enforced in the
authentication backend, because a backend can only answer yes or no and
that would make "unconfirmed" indistinguishable from "wrong password".

**The account hub.** One page, but each form posts to its own URL rather
than to a single handler branching on a hidden action field. A failing
view re-renders the hub with its own form bound, through
`render_account(request, **overrides)` (or, with htmx, only the form's
own section; below). One page for the person, one responsibility per
view.

The hub is laid out as three sections — Profile (display name, public
name), Sign-in (the email address, the email-change block, the link
to change the password) and Fields and clients (a sentence and a link
to each) — that `js/tabs.js` turns into tabs; see
[JavaScript](javascript.md#tabs-jstabsjs).

A successful form redirects to `accounts:account` with
`?section=profile` or `?section=sign-in`, which the `account` view
reads (against `ACCOUNT_SECTIONS`; anything else is ignored) and
passes on as `open_section`. A view that re-renders the hub after a
validation error does the same directly, with
`render_account(..., open_section="profile")` (or `"sign-in"`). Either
way the section comes back marked `data-open`, so the script opens it
instead of defaulting to the first one — and because the redirect
carries a query parameter rather than a `#fragment`, the browser never
jumps the viewport to the section before the Django message above it
(see [Styling](styling.md#flash-messages)) has been seen.

**Saving in place.** With JavaScript, the four forms in Profile and
Sign-in — display name, public name, email change and cancelling one —
post with htmx and get back only their own section's content, so the
tab they are on stays open and the page is not reloaded. Each section's
content is its own template, `accounts/_profile.html` and
`accounts/_sign_in.html` (`SECTION_TEMPLATES` maps a section to its
template), which `account.html` includes inside the `<section>`, after
the `<h2>`. Each is one `div.tab-content` with an id
(`#profile-content`, `#sign-in-content`) the forms name as their
`hx-target`, swapped `outerHTML`. The `<section>` itself is never
swapped: tabs.js gave it `role="tabpanel"`, `aria-labelledby` and
`hidden`, and a fresh copy from the server would have none of them.

Two helpers keep every view to one line per outcome:

- `_section_saved(request, section, message, focus)` queues the
  message, then answers a plain request with the `?section=` redirect,
  as before, and an htmx request with the section re-rendered with
  fresh forms. That fragment carries the message twice, out of band:
  as `#status`'s text, and in the drained `#messages` list, so it is
  not shown again on the next page. `focus` names the button that gets
  `autofocus`, the one the person just used (or, after a cancel, the
  email change's button, the next thing in that section).
- `_section_invalid(request, section, form_name, form)` answers a plain
  request with the whole hub, the form bound and its section
  `data-open`, as before, and an htmx request with a 422 carrying the
  section with the form bound and `autofocus` on its first field in
  error.

Anything else that goes wrong — a 5xx, a dropped connection — is not
swapped into the section; `js/htmx-errors.js` shows the generic error
above the page and announces it (see
[JavaScript](javascript.md#saying-a-request-failed-jshtmx-errorsjs)).

Both pass the response through `vary_on_htmx`. The success messages
name what changed — the new display or public name, the address the
pending change was for — so two saves in a row announce two different
sentences; see [JavaScript](javascript.md#forms-saved-in-place-inside-a-tab).

## Changing the email address

`User.pending_email` holds the requested address while it waits.
`email` is untouched until confirmation, so **the old address keeps
working** for sign-in and password reset throughout — that is the entire
reason the field exists.

Three guards, none of them decoration:

1. The current password is required, so a borrowed session cannot move
   the account.
2. Confirmation comes from the new inbox.
3. A notice goes to the old address the moment a change is requested,
   which is how the real owner finds out while that address still works.

Removing any of the three is a security change, not a simplification.

The signed token carries the **target address** as well as the user id.
Without that, a link issued for one pending address would apply whatever
the pending address happened to be by the time it was used, so asking
again would not kill the earlier link. Confirming re-checks that the
pending address still matches the token and that it is still free.

Confirming requires no session: the link arrives in the new inbox, quite
possibly on another device, and holding it is precisely what the flow is
establishing.

`HRC-ACCT-0006` appears in two places with two statuses, which is
intentional: 409 on the confirm route, where the failure is terminal,
and inline at 200 on the form, where the person can simply type a
different address.

## Tokens

Three kinds, all single-purpose:

| Kind | Storage | Expiry |
|---|---|---|
| API token | SHA-256 hash in `ApiToken` | optional, plus revocation |
| Invitation | SHA-256 hash in `Invitation` | `HRCEK_INVITATION_EXPIRY_DAYS` |
| Email confirmation | none — signed | `HRCEK_EMAIL_CONFIRMATION_EXPIRY_HOURS` |

API tokens and invitations are stored only as hashes, so a leaked
database backup yields nothing usable; the raw value exists once, in
the admin message or the email link.

Confirmation tokens need no table at all: `django.core.signing` carries
the user id and a timestamp, and `max_age` enforces expiry.

`ApiToken.touch()` writes `last_used_at` at most once a minute. Writing
it per request would turn every authenticated read into a SQLite write.

## Signup enumeration defence

Signing up with an address that already has an account returns a
**byte-identical** page and sends that address a "someone tried to
register" notice instead of a confirmation. Without this the form tells
any stranger who has an account here.

`test_an_existing_address_is_indistinguishable` compares the two
responses byte for byte. Do not "improve" the page by mentioning the
address, and do not move the existence check into the form, where a
field error would give it away.

An address the allowlist refuses is different: that is a policy
decision the visitor cannot act on, so it gets its own page with
`HRC-ACCT-0001` and a real 403 rather than a redisplayed form.

## The allowlist

`AllowedEmail` and `AllowedDomain`, both admin-managed.
`is_signup_allowed()` matches an address exactly, or its domain
exactly. `is_open()` answers the coarser question of whether either
table has anything in it at all, which is what the landing page checks
before it offers the signup link.

Domain matching is never a suffix match: allowing `example.com` must
not admit `notexample.com`. With both tables empty nobody may sign up,
so a fresh deployment is closed and the first accounts arrive by
invitation.

Invitations do not consult the allowlist. An admin inviting somebody is
already a deliberate, authenticated act.

## Email

MJML sources live in `accounts/emails/`; the compiled HTML, the
plain-text bodies and the subjects live in `accounts/templates/emails/`,
because only files under `templates/` are visible to Django's template
loader.

```bash
uv run python manage.py compile_emails      # regenerate the HTML
uv run python manage.py compile_emails --check
uv run python manage.py preview_emails      # render with sample data
```

Both the source and its output are committed, and a commit-stage hook
fails when they diverge, so a broken template is a build failure rather
than a surprise at send time. `mjml-python` is a development dependency;
production never compiles anything.

The `{% load i18n %}` tag is emitted by the compiler rather than written
into the sources, because the MJML parser requires `<mjml>` to be the
root element. `mj-include` is unused: each template stands alone rather
than betting on the Rust port's support for it.

Sending uses Django 6.1's `MAILERS` and `message.send()`. The old
`EMAIL_*` settings, `fail_silently` and `connection=` all raise
`RemovedInDjango70Warning`, which this project's suite treats as an
error.

## Tests worth knowing about

- `test_a_token_post_needs_no_csrf_token` — the auth-ordering guard.
- `test_an_existing_address_is_indistinguishable` — the enumeration
  guard, comparing bytes.
- `test_a_missing_user_still_hashes_a_password` — the timing guard.
- `tests/conftest.py` resets the active language between tests.
  `LocaleMiddleware` never deactivates the language a request asked
  for, so without this one Slovenian request makes every later test in
  the process run in Slovenian.
