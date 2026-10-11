# Getting started

Hrček runs as a small web service on a machine you control — a home
server, a spare computer, a small VPS. Whoever set it up can tell you its
address; the examples below assume `http://localhost:8000`.

## Checking that it is running

Open `http://localhost:8000/` in a browser. You should see a sign-in
form, with Hrček's hamster above it.

If you want to check the service itself rather than sign in, open
`http://localhost:8000/api/health`. A healthy service answers:

```json
{
  "status": "ok",
  "service": "hrcek",
  "version": "0.1.0",
  "message": "Service is running."
}
```

If the page does not load at all, Hrček is not running. Ask whoever
looks after it to start the service.

## Appearance

Hrček follows your device's appearance setting: it is light when your
system is light and dark when your system is dark.

If you would rather have the other one, press the sun or moon at the
top right of any page. Press it again to go back to following your
device. The choice is remembered by this browser only, so another
device, or another browser on the same one, keeps following its own
setting.

## Getting an account

You need an account before Hrček is much use. Either somebody invites
you, or you sign yourself up if your address is permitted. See
[your account](accounts.md).

## Browsing what Hrček can do

`http://localhost:8000/api/docs` lists every available operation and
lets you try each one from the browser. It is the quickest way to see
what the current version supports.

This page is switched off on production installations, so it may not be
available on yours.
