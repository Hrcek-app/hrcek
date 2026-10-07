"""Pages that belong to no feature in particular."""

from __future__ import annotations

from collections.abc import Callable
from http import HTTPStatus

from django.http import Http404, HttpRequest, HttpResponse
from django.views import defaults

# Django's own handlers, so a preview cannot drift from the real page —
# the 500 one included, which Django renders without any context.
_PREVIEWS: dict[int, Callable[[HttpRequest], HttpResponse]] = {
    HTTPStatus.NOT_FOUND: lambda request: defaults.page_not_found(request, Http404()),
    HTTPStatus.INTERNAL_SERVER_ERROR: defaults.server_error,
}


def error_preview(request: HttpRequest, code: int) -> HttpResponse:
    """Show a superuser the 404 or 500 page exactly as visitors get it.

    Everybody else, and any other code, gets the ordinary 404.
    """
    if not getattr(request.user, "is_superuser", False) or code not in _PREVIEWS:
        raise Http404
    return _PREVIEWS[code](request)
