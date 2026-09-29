import re
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


def _source_css():
    return (Path(settings.BASE_DIR) / "src/hrcek/core/static_src/hrcek.css").read_text(
        encoding="utf-8"
    )


def _compiled_css():
    return (Path(settings.BASE_DIR) / "src/hrcek/core/static/css/hrcek.css").read_text(
        encoding="utf-8"
    )


def test_every_page_offers_the_theme_toggle(client):
    """Hidden until the script wires it up: without JavaScript it
    would be a button that does nothing, and the page still follows
    the system theme."""
    structure = _structure(client.get(reverse("landing")))
    toggles = [a for a in structure.buttons if "theme-toggle" in (a.get("class") or "")]
    assert len(toggles) == 1
    toggle = toggles[0]
    assert toggle["type"] == "button"
    assert toggle["aria-pressed"] == "false"
    assert "hidden" in toggle


def test_a_pinned_theme_is_applied_before_the_stylesheet_loads(client):
    """The pin is read by an inline, blocking script in the head, so a
    page never paints in the system theme and then flips."""
    html = client.get(reverse("landing")).text
    head = html[: html.index("</head>")]
    script = head.index("<script>")
    assert head.index('<meta name="color-scheme"') < script
    assert script < head.index('rel="stylesheet"')
    assert 'localStorage.getItem("hrcek-theme")' in head
    assert 'src="/static/js/theme.js" defer' in head


def test_both_dark_blocks_define_the_same_colors():
    """Dark comes from the system or from a pin; the two blocks must
    not drift apart, or a pinned dark page differs from a system one."""
    source = _source_css()
    system = re.search(r':root:not\(\[data-theme="light"\]\)\s*\{(.*?)\}', source, re.S)
    pinned = re.search(r':root\[data-theme="dark"\]\s*\{(.*?)\}', source, re.S)
    assert system and pinned

    def colors(block):
        return dict(re.findall(r"(--[\w-]+):\s*([^;]+);", block))

    assert colors(system.group(1)) == colors(pinned.group(1))
    assert len(colors(system.group(1))) >= 9


def test_the_compiled_stylesheet_honours_a_pinned_theme():
    compiled = _compiled_css()
    assert ":root[data-theme=dark]" in compiled
    assert ":root:not([data-theme=light])" in compiled
