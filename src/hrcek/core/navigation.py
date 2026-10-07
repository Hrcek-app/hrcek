"""Where to send somebody back to, without being an open redirect."""

from __future__ import annotations

from django.http import HttpRequest
from django.utils.http import url_has_allowed_host_and_scheme


def safe_next(request: HttpRequest, default: str) -> str:
    """The `next` to return to, or `default` if it is not safe to use.

    Checked against the request's own host, so `next` can only point
    back into this site: an open redirect would let a link to Hrček
    carry its signed-in visitor straight on to somewhere else.
    """
    target = request.POST.get("next") or request.GET.get("next") or ""
    if target and url_has_allowed_host_and_scheme(
        target, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return target
    return default
