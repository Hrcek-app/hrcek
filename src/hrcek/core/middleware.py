"""Request-scoped plumbing."""

from __future__ import annotations

from collections.abc import Callable
from http import HTTPStatus
from urllib.parse import urlsplit

from django.conf import settings
from django.contrib.auth.views import redirect_to_login
from django.db import DatabaseError, connection
from django.http import HttpRequest, HttpResponse
from django.shortcuts import resolve_url
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from sentry_sdk import set_tag

from hrcek.core.htmx import htmx_redirect, is_htmx
from hrcek.core.request_id import (
    REQUEST_ID_HEADER,
    is_acceptable,
    new_request_id,
    reset_request_id,
    set_request_id,
)


class RequestIDMiddleware:
    """Give every request an id, and put it where it can be found again.

    An id supplied by a caller is honoured when it is well formed, so a
    reverse proxy can correlate its own logs with ours.
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        incoming = request.headers.get(REQUEST_ID_HEADER, "").strip()
        request_id = incoming if is_acceptable(incoming) else new_request_id()
        token = set_request_id(request_id)
        # Also on the request itself. Django logs a failing response
        # *after* the middleware chain has unwound, by which time the
        # context variable below has been reset; the record it writes
        # carries the request, so the id can still be found there.
        # HttpRequest carries no such field, hence the silenced check.
        request.request_id = request_id  # ty: ignore[unresolved-attribute]
        try:
            # A no-op when Sentry is not configured.
            set_tag("request_id", request_id)
            response = self.get_response(request)
            response[REQUEST_ID_HEADER] = request_id
            return response
        finally:
            reset_request_id(token)


class HtmxSignInRedirectMiddleware:
    """Send an htmx request with no valid session to a real sign-in page.

    Two things leave an htmx request unauthenticated: a session that
    has expired (`login_required` answers with a redirect to
    `LOGIN_URL`), and a CSRF check that fails (Django answers 403 —
    the only thing that ever does in this project; nothing here raises
    `PermissionDenied` on purpose, so any 403 reaching an htmx request
    means the session is stale the same way). Left alone, fetch()
    follows the redirect itself and hands htmx the sign-in page's own
    HTML to swap into whatever the request targeted — a card, say.
    Converting the response to `HX-Redirect` (`hrcek.core.htmx.
    htmx_redirect`) makes htmx navigate there for real instead.

    The sign-in page's `next` is the page the person was looking at —
    htmx sends its address as `HX-Current-URL` — not the URL the
    request went to: that is usually POST-only, and landing on it with
    a GET after signing in is a blank 405.
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        response = self.get_response(request)
        if not is_htmx(request):
            return response

        location = response.get("Location")
        if response.status_code == HTTPStatus.FORBIDDEN or (
            HTTPStatus.MULTIPLE_CHOICES <= response.status_code < HTTPStatus.BAD_REQUEST
            and location
            and urlsplit(location).path == resolve_url(settings.LOGIN_URL)
        ):
            sign_in = redirect_to_login(_current_page(request))["Location"]
            return htmx_redirect(sign_in)

        return response


def _current_page(request: HttpRequest) -> str:
    """The page an htmx request was made from, as a path and query.

    Only when `HX-Current-URL` points back into this site; anything
    else, or no header at all, is the entries list.
    """
    current = request.headers.get("HX-Current-URL", "")
    if current and url_has_allowed_host_and_scheme(
        current, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        parts = urlsplit(current)
        if parts.path:
            return f"{parts.path}?{parts.query}" if parts.query else parts.path
    return reverse("entries:list")


class HealthCheckMiddleware:
    """Answer /healthz before anything that could refuse a local probe.

    It sits first in the stack: the container's own health check calls
    it over plain HTTP with a Host of 127.0.0.1, which the SSL redirect
    and ALLOWED_HOSTS would otherwise turn away. It says nothing beyond
    whether the database answers.
    """

    PATH = "/healthz"

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        if request.path != self.PATH:
            return self.get_response(request)
        # Fixed tokens for a machine, deliberately not translated.
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
        except DatabaseError:
            return HttpResponse("unavailable", status=503, content_type="text/plain")
        return HttpResponse("ok", content_type="text/plain")
