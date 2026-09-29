import pytest
from django.urls import reverse
from django.utils import timezone

from hrcek.accounts.models import User
from hrcek.entries.models import Entry, Tag
from tests.entries.helpers import _structure

pytestmark = pytest.mark.django_db

PASSWORD = "a-long-enough-passphrase"


def _person(email):
    return User.objects.create_user(
        email=email, password=PASSWORD, email_verified_at=timezone.now()
    )


@pytest.fixture
def nina():
    return _person("nina@example.com")


def _entries(owner, count, prefix="https://example.com/"):
    return [
        Entry.objects.create(owner=owner, url=f"{prefix}{n}", title=f"Entry {n}")
        for n in range(count)
    ]


def test_the_list_needs_a_session(client):
    response = client.get(reverse("entries:list"))
    assert response.status_code == 302
    assert "/?next=" in response["Location"]


def test_it_shows_your_entries_newest_first(client, nina):
    _entries(nina, 3)
    client.force_login(nina)
    page = client.get(reverse("entries:list")).context["page"]
    assert [e.title for e in page] == ["Entry 2", "Entry 1", "Entry 0"]


def test_it_shows_nobody_elses(client, nina):
    marko = _person("marko@example.com")
    Entry.objects.create(owner=marko, url="https://example.com/theirs", title="Theirs")
    _entries(nina, 1)
    client.force_login(nina)
    assert "Theirs" not in client.get(reverse("entries:list")).content.decode()


def test_a_full_first_page_holds_exactly_the_page_size(client, nina, settings):
    _entries(nina, settings.ENTRIES_PER_PAGE)
    client.force_login(nina)
    page = client.get(reverse("entries:list")).context["page"]
    assert len(page) == settings.ENTRIES_PER_PAGE
    assert not page.has_next()


def test_one_more_entry_creates_a_second_page(client, nina, settings):
    _entries(nina, settings.ENTRIES_PER_PAGE + 1)
    client.force_login(nina)
    first = client.get(reverse("entries:list")).context["page"]
    assert first.has_next()
    second = client.get(reverse("entries:list"), {"page": 2}).context["page"]
    assert len(second) == 1


def test_no_entry_appears_on_two_pages(client, nina, settings):
    _entries(nina, settings.ENTRIES_PER_PAGE + 5)
    client.force_login(nina)
    seen = []
    for number in (1, 2):
        page = client.get(reverse("entries:list"), {"page": number}).context["page"]
        seen.extend(e.pk for e in page)
    assert len(seen) == len(set(seen))


def test_a_nonsense_page_number_does_not_break_the_list(client, nina):
    _entries(nina, 3)
    client.force_login(nina)
    assert client.get(reverse("entries:list"), {"page": "banana"}).status_code == 200
    assert client.get(reverse("entries:list"), {"page": 999}).status_code == 200


def test_filtering_by_tag(client, nina):
    kept, _other = _entries(nina, 2)
    Tag.set_for(kept, ["watches"])
    client.force_login(nina)
    page = client.get(reverse("entries:list"), {"tag": "watches"}).context["page"]
    assert [e.pk for e in page] == [kept.pk]


def test_the_tag_filter_ignores_case(client, nina):
    kept, _other = _entries(nina, 2)
    Tag.set_for(kept, ["Watches"])
    client.force_login(nina)
    page = client.get(reverse("entries:list"), {"tag": "watches"}).context["page"]
    assert [e.pk for e in page] == [kept.pk]


def test_an_unknown_tag_yields_nothing_rather_than_everything(client, nina):
    _entries(nina, 3)
    client.force_login(nina)
    page = client.get(reverse("entries:list"), {"tag": "nope"}).context["page"]
    assert list(page) == []


def test_signing_in_lands_on_the_entry_list(client, nina):
    response = client.post("/", {"username": "nina@example.com", "password": PASSWORD})
    assert response["Location"] == reverse("entries:list")


def test_the_tag_filter_is_marked_up_as_a_list(client, nina):
    (entry,) = _entries(nina, 1)
    Tag.set_for(entry, ["watches"])
    client.force_login(nina)
    parsed = _structure(client.get(reverse("entries:list")))
    tag_links = [a for a in parsed.anchors if a[0].startswith("?tag=")]
    assert tag_links, "no tag links rendered"
    for href, ancestors in tag_links:
        assert "li" in ancestors, f"{href} is not inside a list item"
        assert "ul" in ancestors, f"{href} is not inside a list"


def test_the_entries_are_marked_up_as_a_list(client, nina):
    _entries(nina, 3)
    client.force_login(nina)
    parsed = _structure(client.get(reverse("entries:list")))
    assert len(parsed.articles) == 3
    for ancestors in parsed.articles:
        assert "li" in ancestors, "an entry is not inside a list item"


def test_an_entrys_own_tags_are_marked_up_as_a_list(client, nina):
    (entry,) = _entries(nina, 1)
    Tag.set_for(entry, ["watches", "diving"])
    client.force_login(nina)
    parsed = _structure(client.get(reverse("entries:list")))
    in_entry = [a for a in parsed.anchors if "article" in a[1] and "?tag=" in a[0]]
    assert len(in_entry) == 2
    for href, ancestors in in_entry:
        assert ancestors[-3:] == ["ul", "li", "a"], f"{href} is not a list item"


def test_an_entrys_tags_link_to_the_entries_carrying_them(client, nina):
    (entry,) = _entries(nina, 1)
    Tag.set_for(entry, ["Deep sea"])
    client.force_login(nina)
    parsed = _structure(client.get(reverse("entries:list")))
    in_entry = [href for href, stack in parsed.anchors if "article" in stack]
    assert f"{reverse('entries:list')}?tag=Deep%20sea" in in_entry


def test_the_pager_is_marked_up_as_a_list(client, nina, settings):
    _entries(nina, settings.ENTRIES_PER_PAGE + 1)
    client.force_login(nina)
    parsed = _structure(client.get(reverse("entries:list")))
    pager = [a for a in parsed.anchors if a[0].startswith("?page=")]
    assert pager, "no pager links rendered"
    for href, ancestors in pager:
        assert "li" in ancestors, f"{href} is not inside a list item"
        assert "nav" in ancestors, f"{href} is not inside a nav"


def test_an_empty_list_still_says_so(client, nina):
    client.force_login(nina)
    assert "Nothing saved yet." in client.get(reverse("entries:list")).content.decode()


def test_the_tag_filter_is_an_aside_that_follows_the_entries(client, nina):
    """The tags are not the page's main content. They sit in an aside
    placed after the entries, so on a phone they follow the list, and
    a wide screen puts them in a column beside it."""
    (entry,) = _entries(nina, 1)
    Tag.set_for(entry, ["watches"])
    client.force_login(nina)
    response = client.get(reverse("entries:list"))
    parsed = _structure(response)
    filters = [
        (href, ancestors)
        for href, ancestors in parsed.anchors
        if href.startswith("?tag=") and "article" not in ancestors
    ]
    assert filters
    for href, ancestors in filters:
        assert "aside" in ancestors, f"{href} is not inside the aside"
    body = response.content.decode()
    assert body.index('<ul class="entries"') < body.index("<aside")


def test_the_tag_being_shown_is_marked_in_the_aside(client, nina):
    (entry,) = _entries(nina, 1)
    Tag.set_for(entry, ["Watches", "diving"])
    client.force_login(nina)
    body = client.get(reverse("entries:list"), {"tag": "watches"}).text
    aside = body[body.index("<aside") : body.index("</aside>")]
    assert aside.count('aria-current="true"') == 1
    assert '?tag=Watches" aria-current="true"' in aside
