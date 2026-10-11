# When something goes wrong

Hrček reports every problem with a code such as `HRC-CORE-0003`, along
with a description in your language. The description may be reworded
between versions; **the code never changes meaning**, so quote the code
when asking for help.

A failure looks like this:

```json
{
  "error": {
    "code": "HRC-CORE-0003",
    "message": "The requested resource does not exist.",
    "details": {}
  }
}
```

## What the codes mean

| Code | What happened | What to do |
|---|---|---|
| `HRC-CORE-0001` | Something went wrong inside Hrček. | Not your fault. Report it, with the code, the time, and what you were doing. |
| `HRC-CORE-0002` | The information sent was not valid. | Check what you entered. `details` names the fields at fault. |
| `HRC-CORE-0003` | The thing you asked for does not exist. | Check the address or the identifier. It may also have been deleted. |
| `HRC-AUTH-0001` | Your email address or password was not accepted. | Check both. Hrček gives this same answer for a disabled account, so if you are certain they are right, ask whoever runs it. |
| `HRC-AUTH-0002` | Your email address has not been confirmed. | Follow the link in the confirmation email. If it has expired, sign up again for a fresh one. |
| `HRC-AUTH-0003` | You need to be signed in. | Sign in and try again. |
| `HRC-AUTH-0004` | The API token used is not valid. | It may have been revoked or expired. Ask for a new one. |
| `HRC-AUTH-0005` | The request could not be verified. | Usually a stale page. Reload and try again. |
| `HRC-ACCT-0001` | That address is not allowed to create an account here. | Ask to be invited instead, or to have your address permitted. |
| `HRC-ACCT-0002` | The invitation link is not usable. | It has expired, been used, or been withdrawn. Ask for a new invitation. |
| `HRC-ACCT-0003` | The confirmation link is not usable. | It has probably expired. Sign up again to get a fresh one. |
| `HRC-ACCT-0004` | That display name is taken. | Pick another. Capitals do not make it different. |

## Reporting a problem

Include the error code, roughly when it happened, and what you were
doing. If you can see the response headers, include `X-Request-ID` — it
points straight at the matching entry in the logs.
