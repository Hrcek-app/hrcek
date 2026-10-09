from urllib.robotparser import RobotFileParser

import pytest
from django.urls import URLPattern, URLResolver, get_resolver

pytestmark = pytest.mark.django_db

WHITENOISE = "whitenoise.middleware.WhiteNoiseMiddleware"

# The top-level addresses a stranger is meant to reach.
CRAWLABLE = {"", "u/"}


@pytest.fixture
def served(settings):
    """WhiteNoise wired in as production wires it."""
    middleware = list(settings.MIDDLEWARE)
    security = middleware.index("django.middleware.security.SecurityMiddleware")
    middleware.insert(security + 1, WHITENOISE)
    settings.MIDDLEWARE = middleware
    # No collectstatic in the suite; production always has one.
    settings.STATIC_ROOT = None


def _fetch(client, **headers):
    """Get /robots.txt and read it whole; WhiteNoise streams the file."""
    response = client.get("/robots.txt", **headers)
    body = response.getvalue()
    response.close()
    return response, body


@pytest.fixture
def robots(client, served):
    response, body = _fetch(client)
    assert response.status_code == 200
    parser = RobotFileParser()
    parser.parse(body.decode().splitlines())
    return parser


def _top_level_prefixes():
    prefixes = set()
    for entry in get_resolver().url_patterns:
        if isinstance(entry, URLResolver) and str(entry.pattern) == "":
            prefixes |= {str(p.pattern).split("/")[0] + "/" for p in entry.url_patterns}
        elif isinstance(entry, URLPattern | URLResolver):
            prefix = str(entry.pattern).split("/")[0]
            prefixes.add(f"{prefix}/" if prefix else "")
    return prefixes


def test_robots_txt_is_plain_text_and_cached_for_a_day(client, served):
    response, _ = _fetch(client)
    assert response["Content-Type"].startswith("text/plain")
    assert response["Cache-Control"] == "public, max-age=86400"


def test_robots_txt_answers_a_repeat_visit_with_not_modified(client, served):
    first, _ = _fetch(client)
    again, _ = _fetch(client, HTTP_IF_NONE_MATCH=first["ETag"])
    assert again.status_code == 304


@pytest.mark.parametrize(
    "path",
    [
        "/admin/",
        "/admin/login/",
        "/accounts/me/",
        "/accounts/signup/",
        "/entries/",
        "/collections/",
        "/collections/1/feed/",
        "/api/entries",
        "/i18n/setlang/",
        "/errors/404/",
        "/healthz",
        "/c/abcdefghij/",
        "/c/abcdefghij/feed/",
    ],
)
def test_private_parts_are_closed_to_crawlers(robots, path):
    assert not robots.can_fetch("*", path)


@pytest.mark.parametrize(
    "path",
    ["/", "/u/ana/watches/", "/u/ana/watches/feed/"],
)
def test_public_parts_are_open_to_crawlers(robots, path):
    assert robots.can_fetch("*", path)


def test_every_new_top_level_address_is_decided(robots):
    # A new section of the site must be added to robots.txt or to
    # CRAWLABLE above; this fails until somebody chooses.
    undecided = {
        prefix
        for prefix in _top_level_prefixes() - CRAWLABLE
        if robots.can_fetch("*", f"/{prefix}")
    }
    assert undecided == set()
