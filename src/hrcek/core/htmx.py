"""The little htmx needs from the server: knowing it is asking."""

from django.http import HttpRequest, HttpResponse
from django.utils.cache import patch_vary_headers


def is_htmx(request: HttpRequest) -> bool:
    return request.headers.get("HX-Request") == "true"


def vary_on_htmx(response: HttpResponse) -> HttpResponse:
    # A fragment and a whole page share a URL; caches must not mix
    # them up.
    patch_vary_headers(response, ["HX-Request"])
    return response


def htmx_redirect(location: str) -> HttpResponse:
    """A full browser navigation for an htmx request.

    fetch(), which every htmx request goes through, follows an ordinary
    redirect on its own and hands htmx the page it lands on rather than
    the redirect itself — which would swap that page's markup into
    whatever the request targeted. `HX-Redirect` is htmx's own answer:
    never auto-followed by fetch(), and read by htmx as `location.href
    = ...`, a real navigation, whatever the response status is.
    """
    response = HttpResponse(status=200)
    response["HX-Redirect"] = location
    return response
