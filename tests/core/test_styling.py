from pathlib import Path

import pytest
from django.conf import settings
from django.urls import reverse

from tests.entries.helpers import _structure

pytestmark = pytest.mark.django_db


def test_pages_link_the_compiled_stylesheet(client):
    response = client.get(reverse("landing"))
    assert response.status_code == 200
    assert 'href="/static/css/hrcek.css"' in response.text


def test_pages_declare_both_color_schemes(client):
    response = client.get(reverse("landing"))
    assert '<meta name="color-scheme" content="light dark">' in response.text


def test_landing_page_shows_the_mascot_above_the_title(client):
    response = client.get(reverse("landing"))
    assert 'src="/static/img/hrcek.png"' in response.text
    assert response.text.index('src="/static/img/hrcek.png"') < response.text.index(
        "<h1"
    )


def test_pages_link_the_favicon(client):
    response = client.get(reverse("landing"))
    assert 'rel="icon" href="/static/img/favicon-32.png"' in response.text
    assert 'rel="apple-touch-icon" href="/static/img/apple-touch-icon.png"' in (
        response.text
    )


def test_checkbox_rows_are_laid_out_beside_their_label():
    """The compiled stylesheet carries the rule, not just the source.

    The compiled file is committed, so forgetting to rebuild after
    editing static_src ships a stylesheet that does not match the
    source. This catches that.
    """
    compiled = (
        Path(settings.BASE_DIR) / "src/hrcek/core/static/css/hrcek.css"
    ).read_text(encoding="utf-8")
    assert ":has(>input[type=checkbox])" in compiled
    assert "checkbox])>label" in compiled, "the label rule did not compile"


def test_the_home_link_carries_the_head_only_logo(client):
    """The small mascot sits inside the home link, beside the name.

    Decorative: the link already says "Hrček", so the picture has an
    empty alt rather than repeating it to a screen reader.
    """
    structure = _structure(client.get(reverse("landing")))
    in_header = [(a, stack) for a, stack in structure.images if "header" in stack]
    assert len(in_header) == 1
    logo, stack = in_header[0]
    assert logo["src"] == "/static/img/apple-touch-icon.png"
    assert logo["alt"] == ""
    assert stack[-1] == "a"
