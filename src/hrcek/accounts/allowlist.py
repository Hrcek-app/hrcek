"""Who may create an account without being invited."""

from __future__ import annotations

from hrcek.accounts.models import AllowedDomain, AllowedEmail


def is_signup_allowed(email: str) -> bool:
    """True when *email* may register itself.

    With both tables empty this returns False, so a new deployment is
    closed and the first accounts arrive by invitation.

    Domain matching is exact on the part after "@" and never a suffix
    match: allowing "example.com" must not admit "notexample.com".
    """
    address = (email or "").strip().lower()
    if address.count("@") != 1:
        return False

    if AllowedEmail.objects.filter(email=address).exists():
        return True

    domain = address.rsplit("@", 1)[1]
    return bool(domain) and AllowedDomain.objects.filter(domain=domain).exists()


def is_open() -> bool:
    """True when anybody at all may sign up, so the form is worth offering."""
    return AllowedEmail.objects.exists() or AllowedDomain.objects.exists()
