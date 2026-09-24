"""Request-scoped plumbing."""

from __future__ import annotations

from collections.abc import Callable

from django.db import DatabaseError, connection
from django.http import HttpRequest, HttpResponse
from sentry_sdk import set_tag

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
