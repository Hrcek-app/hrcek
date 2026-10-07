"""Fixtures for the tests that drive a real browser (see testing.md)."""

import pytest
from django.conf import settings
from django.utils import timezone

from hrcek.accounts.models import User

PASSWORD = "a-long-enough-passphrase"


@pytest.fixture(scope="session", autouse=True)
def _test_database_before_playwright(django_db_setup):
    # Autouse, so it comes before Playwright's own session fixtures:
    # the test database is then created, and later destroyed, while no
    # event loop is running on this thread.
    return


@pytest.fixture(scope="package", autouse=True)
def _allow_the_orm_beside_playwright():
    # Playwright's sync API runs an event loop on this thread; Django's
    # ORM refuses to run under one unless told it is safe, which it is
    # here: the test and the live server never use a connection at the
    # same time. Set for this package only, not at import, so the rest
    # of the suite keeps Django's check; package-scoped, so it outlasts
    # pytest-django's flush of the database after each test.
    with pytest.MonkeyPatch.context() as patch:
        patch.setenv("DJANGO_ALLOW_ASYNC_UNSAFE", "true")
        yield


@pytest.fixture
def person(transactional_db):
    return User.objects.create_user(
        email="nina@example.com", password=PASSWORD, email_verified_at=timezone.now()
    )


def _sign_in(context, live_server, person, client):
    client.force_login(person)
    cookie = client.cookies[settings.SESSION_COOKIE_NAME]
    context.add_cookies(
        [
            {
                "name": settings.SESSION_COOKIE_NAME,
                "value": cookie.value,
                "url": live_server.url,
            }
        ]
    )


@pytest.fixture
def signed_in_page(page, live_server, person, client):
    """A page whose browser is signed in as person."""
    _sign_in(page.context, live_server, person, client)
    return page


@pytest.fixture
def signed_in_page_without_js(browser, live_server, person, client):
    """The same, in a browser with JavaScript switched off."""
    context = browser.new_context(java_script_enabled=False)
    _sign_in(context, live_server, person, client)
    yield context.new_page()
    context.close()
