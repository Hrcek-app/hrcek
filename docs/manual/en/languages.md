# Languages

Hrček speaks English and Slovenian. By default it uses the language
your browser or app requests, and you can override that choice on any
page.

## Choosing a language

At the bottom of every page both languages are listed, with the one in
use shown plainly and the other as a link. Pick one and Hrček stays in
it — on this browser — until you pick again, whatever your browser's
own language preference says. You do not need to be signed in.

## How the language is chosen otherwise

If you have never picked a language, every request carries the
languages you prefer, in order, and Hrček answers in the first one it
knows, falling back to English otherwise. Changing your browser's or
phone's preferred language changes Hrček's replies.

## If a reply is in the wrong language

First look at the bottom of the page — if a language was picked there,
it wins. Otherwise check your browser's language settings. If Slovenian
is preferred in both places and replies still arrive in English, that
is a bug worth reporting.

## Asking for a language directly

If you are calling Hrček from a script:

```bash
curl -H "Accept-Language: sl" http://localhost:8000/api/health
```
