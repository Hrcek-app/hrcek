import re
from pathlib import Path

import pytest
from django.conf import settings
from django.urls import reverse
from django.utils import timezone

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


def _main_class(response):
    match = re.search(r'<main class="([^"]*)"', response.text)
    assert match, "main carries no class"
    return match.group(1).split()


def test_the_page_frame_is_not_capped_at_phone_width(client):
    html = client.get(reverse("landing")).text
    frame = re.search(r'<body[^>]*>\s*<div class="([^"]*)"', html)
    assert frame
    assert not any(c.startswith("max-w-") for c in frame.group(1).split())


def test_reading_pages_keep_a_readable_measure(client):
    """Forms and prose stay narrow even in a wide window: a sign-in
    box a whole screen wide is harder to use, not easier."""
    assert "max-w-2xl" in _main_class(client.get(reverse("landing")))


def test_the_entry_list_uses_the_whole_width(client, django_user_model):
    user = django_user_model.objects.create_user(
        email="wide@example.com", password="x" * 20, email_verified_at=timezone.now()
    )
    client.force_login(user)
    classes = _main_class(client.get(reverse("entries:list")))
    assert not any(c.startswith("max-w-") for c in classes)


def test_entries_flow_into_columns_when_there_is_room():
    assert "ul.entries" in _source_css()
    assert "repeat(auto-fill,minmax(min(100%,22rem),1fr))" in _compiled_css()


def test_messages_have_no_side_bar():
    css = _compiled_css()
    block = css.split(".messages", 1)[1].split("}", 1)[0]
    assert "border-inline-start" not in block


def test_entries_no_longer_share_rows_across_cards():
    """A subgrid made every li/article in a visual row share the same
    rows, so a long title or long notes in one card pushed every
    other card's body, labels and actions down to match. Cards no
    longer share rows at all: each one sizes itself from its own
    content."""
    assert "subgrid" not in _source_css()
    assert "subgrid" not in _compiled_css()


def _rule(css, selector):
    """The declaration block of the first `selector { ... }` in css."""
    start = css.index(selector + "{") + len(selector) + 1
    return css[start : css.index("}", start)]


def test_entry_cards_are_a_flex_column():
    """entries/list.html's card — identified by its entry-head, the
    one child collections' single-.entry-text cards never have — is
    a flex column, so the gap between head, body, labels and actions
    never depends on a neighbouring card's title or notes."""
    rule = _rule(_compiled_css(), "ul.entries article:has(>.entry-head)")
    assert "display:flex" in rule
    assert "flex-direction:column" in rule


def test_entry_actions_are_pinned_to_the_card_bottom():
    """Cards sharing a grid row are already stretched to the same
    height by the grid's own default alignment; pushing the actions
    row down with a plain auto margin is what lands every row's
    Edit/Delete links on the same line, however tall the cards beside
    it are."""
    rule = _rule(_compiled_css(), "ul.entries article:has(>.entry-head)>.entry-actions")
    assert "margin-block-start:auto" in rule
