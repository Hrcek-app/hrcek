# Your account

Hrček keeps a small number of accounts, one per person. This page
explains how to get one and how to get back in when something goes
wrong.

## Getting an account

There are two ways in.

**Someone invites you.** Whoever looks after this Hrček sends an
invitation to your email address. Open the link in it, choose a
password, and you are done — following the link is proof enough that
the address is yours, so there is nothing else to confirm.

Invitation links expire, by default after a week. If yours has, ask for
a new one; the old link cannot be revived.

**You sign yourself up.** Go to `/accounts/signup/` and fill in your
email address and a password. This only works if your address has been
permitted in advance, either individually or because your whole email
domain is allowed. If it has not, you will be told so, and the way
forward is an invitation.

The sign-in page shows a "Sign up" link whenever anybody at all is
allowed to self-register. If nobody is, the link is not shown, since
it would only lead to a form that turns you away.

After signing up you get a confirmation email. **You cannot sign in
until you follow that link.** It expires after two days.

## Your display name

A display name is optional. Set one and you can sign in with it instead
of your email address, which is shorter to type.

Two rules:

- It may not contain `@`. Hrček accepts either identifier at sign-in,
  and an `@` would make a display name indistinguishable from an email
  address.
- Capitals do not count. If somebody is already `Nina`, you cannot be
  `nina`.

You can leave it empty, and any number of people can.

## Managing your account

Once you are signed in, `/accounts/me/` is where everything about your
account lives.

**Display name.** Change it or clear it whenever you like. The rules are
the same as when you first set one: no `@`, and capitals do not make it
different from somebody else's.

**Email address.** Changing it asks for your current password, then
sends a confirmation link to the *new* address.

Three things are worth knowing:

- **Your old address keeps working until you follow that link.** You can
  still sign in, and still reset your password, with the address you
  have always used. Nothing changes until you confirm.
- **A notice goes to your old address** as soon as a change is asked
  for. If you did not ask for it, somebody else is trying to move your
  account — sign in and cancel it while your old address still works.
- Asking again replaces the previous request, and the earlier link stops
  working.

There is a cancel button next to the pending address for as long as one
is waiting.

**Fields.** A link to your fields, the extras you record about each
entry. See [fields](entries.md#fields).

**Password.** There is a link to change it. You will be asked for your
current password, and you stay signed in afterwards.

## Clients and API tokens

A client is a script or another program that acts as you without a
browser and without your password. Each client authenticates with an
API token.

Tokens live on their own page: from your account page, follow *Manage
clients and their authorizations*. Create one there and give it a name
you will recognise later. **The token is shown once and never again** —
copy it before you leave the page. Only a fingerprint of it is stored,
so nobody, including whoever runs this Hrček, can look it up for you
afterwards.

A program can also make a token for itself, which saves pasting one in
by hand when it is set up: it asks for your email address and password
once, trades them for a token, and keeps only the token. A browser
extension works this way. Your password should never be stored by it —
if a program asks to keep your password rather than a token, that is
worth questioning. That is a detail for whoever writes the program;
the developer documentation covers it.

Delete a token and it stops working immediately, which is what to do if
you think one has leaked. Deleting cannot be undone; make a new one.

## Signing in

Use either your email address or your display name, with your password.
Capitals do not matter for either identifier.

If you are told your details are wrong when you are sure they are not,
two things are worth checking: whether you ever followed the
confirmation link, and whether your account has been disabled. Hrček
deliberately gives the same answer for a wrong password as for a
disabled account, so it cannot tell you which — ask whoever runs it.

## Forgotten password

Go to `/accounts/password/reset/` and enter your email address. If
there is an account for it, a link arrives; if there is not, you get
the same page anyway, so nobody can use that form to find out who has
an account here.

The link works once. After you set a new password it stops working, so
if you need to change it again, ask for a new link.

## When something goes wrong

Every failure comes with a code such as `HRC-ACCT-0002`. The wording
may change between versions; the code does not. Quote it when asking
for help — see [when something goes wrong](troubleshooting.md).
