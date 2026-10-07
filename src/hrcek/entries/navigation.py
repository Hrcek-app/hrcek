"""Where to send somebody back to in the entries list."""

from __future__ import annotations

from urllib.parse import parse_qs, urlsplit

from django.urls import reverse

from hrcek.accounts.models import User
from hrcek.entries.models import Tag


def still_there(back: str, owner: User) -> str:
    """`back`, unless it filters by a label nothing carries any more.

    Taking the last entry away from a label prunes it, and the list
    gives a label nothing carries no page; the list of everything is the
    nearest page left. The test is the list view's own: the `tag` value,
    stripped, matched case-insensitively against the labels in use.
    """
    label = parse_qs(urlsplit(back).query).get("tag", [""])[0].strip()
    if label and not Tag.in_use(owner).filter(name__iexact=label).exists():
        return reverse("entries:list")
    return back
