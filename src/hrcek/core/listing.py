"""The two ways a list of entries can be shown.

As a list of wide rows, each with a small picture when it has one, or
as cards that lead with the picture and stand in a placeholder when
there is none. An account remembers which it last chose for its own
entries; a collection carries its own, which everybody who opens it
sees first. See docs/dev/entries.md.
"""

from __future__ import annotations

from typing import Any

from django.http import HttpRequest
from django.utils.translation import gettext_lazy as _

LIST = "list"
CARDS = "cards"
VIEWS: list[tuple[str, Any]] = [
    (LIST, _("List")),
    (CARDS, _("Cards")),
]
NAMES = frozenset(name for name, _label in VIEWS)


def chosen(asked: str | None, default: str) -> str:
    """`asked` when it names a view, otherwise `default`."""
    return asked if asked in NAMES else default


def switch_links(request: HttpRequest, shown: str) -> list[dict[str, Any]]:
    """One link per view for a page that switches by its address.

    Each keeps whatever else the address already says (a wish list's
    reveal, say) and adds or replaces `view`. Nothing is saved: the
    switch lasts for as long as the visitor stays on that address.
    """
    links = []
    for name, label in VIEWS:
        query = request.GET.copy()
        query["view"] = name
        links.append(
            {
                "name": name,
                "label": label,
                "url": f"?{query.urlencode()}",
                "current": name == shown,
            }
        )
    return links
