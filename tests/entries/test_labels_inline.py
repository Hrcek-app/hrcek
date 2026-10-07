"""Adding and removing an entry's labels from the list itself."""

import re

import pytest
from django.contrib.messages import get_messages
from django.urls import reverse
from django.utils import timezone

from hrcek.accounts.models import User
from hrcek.collections.models import Collection
from hrcek.entries.models import Entry, Tag

pytestmark = pytest.mark.django_db

PASSWORD = "a-long-enough-passphrase"
HTMX = {"HX-Request": "true"}
OPEN = re.compile(r"<details[^>]* open>")


def _person(email):
    return User.objects.create_user(
        email=email, password=PASSWORD, email_verified_at=timezone.now()
    )


@pytest.fixture
def person(client):
    person = _person("nina@example.com")
    client.force_login(person)
    return person


@pytest.fixture
def entry(person):
    return Entry.objects.create(owner=person, url="https://example.com/a", title="A")


def _add(entry):
    return reverse("entries:label_add", args=[entry.pk])


def _remove(entry):
    return reverse("entries:label_remove", args=[entry.pk])


def _names(entry):
    return list(entry.tags.values_list("name", flat=True))


def _messages(response):
    return [str(m) for m in get_messages(response.wsgi_request)]


def test_adding_a_label(client, person, entry):
    client.post(_add(entry), {"name": "watch"})
    assert _names(entry) == ["watch"]


def test_adding_keeps_the_labels_already_there(client, person, entry):
    Tag.set_for(entry, ["books"])
    client.post(_add(entry), {"name": "watch"})
    assert _names(entry) == ["books", "watch"]


def test_adding_several_separated_by_commas(client, person, entry):
    client.post(_add(entry), {"name": " a, b ,a"})
    assert _names(entry) == ["a", "b"]


def test_adding_an_existing_label_in_another_case_changes_nothing(
    client, person, entry
):
    Tag.set_for(entry, ["watch"])
    client.post(_add(entry), {"name": "Watch"})
    assert _names(entry) == ["watch"]
    assert Tag.objects.filter(owner=person).count() == 1


def test_adding_reuses_a_label_another_entry_carries(client, person, entry):
    other = Entry.objects.create(owner=person, url="https://example.com/b")
    Tag.set_for(other, ["watch"])
    client.post(_add(entry), {"name": "WATCH"})
    assert _names(entry) == ["watch"]
    assert Tag.objects.filter(owner=person).count() == 1


def test_removing_a_label(client, person, entry):
    Tag.set_for(entry, ["books", "watch"])
    client.post(_remove(entry), {"name": "watch"})
    assert _names(entry) == ["books"]


def test_removing_ignores_case(client, person, entry):
    Tag.set_for(entry, ["watch"])
    response = client.post(_remove(entry), {"name": "WATCH"})
    assert _names(entry) == []
    # Named as it was shown, not as it was posted.
    assert _messages(response) == ["Label “watch” removed."]


def test_adding_several_names_them_all(client, person, entry):
    Tag.set_for(entry, ["books"])
    response = client.post(_add(entry), {"name": "a, Books, b"})
    assert _messages(response) == ["Labels “a”, “b” added."]


def test_adding_only_labels_already_there_says_so(client, person, entry):
    Tag.set_for(entry, ["watch"])
    response = client.post(_add(entry), {"name": "Watch"})
    assert _messages(response) == ["This entry already has the label “watch”."]


def test_removing_a_label_prunes_it_when_unused(client, person, entry):
    Tag.set_for(entry, ["watch"])
    client.post(_remove(entry), {"name": "watch"})
    assert not Tag.objects.filter(owner=person).exists()


def test_removing_keeps_a_label_another_entry_carries(client, person, entry):
    other = Entry.objects.create(owner=person, url="https://example.com/b")
    Tag.set_for(entry, ["watch"])
    Tag.set_for(other, ["watch"])
    client.post(_remove(entry), {"name": "watch"})
    assert _names(entry) == []
    assert _names(other) == ["watch"]


def test_removing_keeps_a_label_a_collection_follows(client, person, entry):
    Tag.set_for(entry, ["watch"])
    label = Tag.objects.get(owner=person, name="watch")
    Collection.objects.create(
        owner=person, name="Watches", kind=Collection.BY_LABEL, label=label
    )
    client.post(_remove(entry), {"name": "watch"})
    assert _names(entry) == []
    assert Tag.objects.filter(pk=label.pk).exists()


def test_removing_the_last_of_a_followed_label_says_the_collection_is_empty(
    client, person, entry
):
    Tag.set_for(entry, ["watch"])
    label = Tag.objects.get(owner=person, name="watch")
    Collection.objects.create(
        owner=person, name="Watches", kind=Collection.BY_LABEL, label=label
    )
    response = client.post(_remove(entry), {"name": "watch"})
    assert any("“Watches” has nothing in it now" in m for m in _messages(response))


@pytest.mark.parametrize("name", ["", "   ", " , ,"])
def test_an_empty_name_is_refused(client, person, entry, name):
    Tag.set_for(entry, ["books"])
    response = client.post(_add(entry), {"name": name})
    assert response.status_code == 302
    assert _messages(response) == ["Type a label to add."]
    assert _names(entry) == ["books"]


def test_a_too_long_name_is_refused(client, person, entry):
    response = client.post(_add(entry), {"name": "x" * 51})
    assert _messages(response) == [
        "A label can be at most 50 characters long; that one has 51."
    ]
    assert _names(entry) == []
    assert not Tag.objects.exists()


def test_fifty_characters_are_enough(client, person, entry):
    client.post(_add(entry), {"name": "x" * 50})
    assert _names(entry) == ["x" * 50]


def test_a_too_long_name_among_several_refuses_them_all(client, person, entry):
    client.post(_add(entry), {"name": "fine, " + "x" * 51})
    assert _names(entry) == []


def test_only_the_owner_may_change_labels(client, person):
    marko = _person("marko@example.com")
    theirs = Entry.objects.create(owner=marko, url="https://example.com/theirs")
    Tag.set_for(theirs, ["watch"])
    assert client.post(_add(theirs), {"name": "mine"}).status_code == 404
    assert client.post(_remove(theirs), {"name": "watch"}).status_code == 404
    assert _names(theirs) == ["watch"]


def test_signed_out_is_sent_to_sign_in(client, entry):
    client.logout()
    response = client.post(_add(entry), {"name": "watch"})
    assert response.status_code == 302
    assert "/?next=" in response["Location"]
    assert _names(entry) == []


@pytest.mark.parametrize("url", [_add, _remove])
def test_get_is_not_allowed(client, person, entry, url):
    assert client.get(url(entry)).status_code == 405


def test_label_add_returns_to_next_with_a_message(client, person, entry):
    Tag.set_for(entry, ["books"])
    response = client.post(
        _add(entry), {"name": "watch", "next": "/entries/?tag=books&page=2"}
    )
    assert response.status_code == 302
    assert response["Location"] == "/entries/?tag=books&page=2"
    assert _messages(response) == ["Label “watch” added."]


def test_label_remove_returns_to_next_with_a_message(client, person, entry):
    Tag.set_for(entry, ["books", "watch"])
    response = client.post(
        _remove(entry), {"name": "watch", "next": "/entries/?tag=books"}
    )
    assert response["Location"] == "/entries/?tag=books"
    assert _messages(response) == ["Label “watch” removed."]


def test_without_next_it_returns_to_the_list(client, person, entry):
    response = client.post(_add(entry), {"name": "watch"})
    assert response["Location"] == reverse("entries:list")


def test_label_add_ignores_an_off_site_next(client, person, entry):
    response = client.post(
        _add(entry), {"name": "watch", "next": "https://evil.example/"}
    )
    assert response["Location"] == reverse("entries:list")
    assert _names(entry) == ["watch"]


def test_removing_the_label_being_filtered_by_returns_to_all_entries(
    client, person, entry
):
    # The filtered page would be a 404 once nothing carries the label.
    Tag.set_for(entry, ["watch"])
    response = client.post(
        _remove(entry), {"name": "watch", "next": "/entries/?tag=Watch&page=2"}
    )
    assert response["Location"] == reverse("entries:list")


def test_removing_the_filter_label_from_one_of_several_keeps_the_filter(
    client, person, entry
):
    other = Entry.objects.create(owner=person, url="https://example.com/b")
    Tag.set_for(entry, ["watch"])
    Tag.set_for(other, ["watch"])
    response = client.post(
        _remove(entry), {"name": "watch", "next": "/entries/?tag=watch"}
    )
    assert response["Location"] == "/entries/?tag=watch"


def test_htmx_gets_the_entrys_labels_fragment(client, person, entry):
    response = client.post(_add(entry), {"name": "watch"}, headers=HTMX)
    body = response.content.decode()
    assert response.status_code == 200
    assert "<html" not in body
    assert body.lstrip().startswith(f'<div class="entry-labels" id="labels-{entry.pk}"')
    assert ">watch</a>" in body
    assert "hx-swap-oob" in body and "Label “watch” added." in body
    assert "HX-Request" in response["Vary"]
    # The message is the status line's; it must not also wait for the
    # next page load.
    assert _messages(response) == []


def test_htmx_fragment_keeps_the_add_form_open_and_empty(client, person, entry):
    body = client.post(_add(entry), {"name": "watch"}, headers=HTMX).content.decode()
    assert OPEN.search(body)
    assert re.search(r'<input id="label-\d+" name="name"[^>]*autofocus', body)
    assert 'value="watch"' not in body.split('name="name"')[-1].split(">")[0]


def test_htmx_fragment_returns_to_the_same_next(client, person, entry):
    body = client.post(
        _add(entry),
        {"name": "watch", "next": "/entries/?tag=watch"},
        headers=HTMX,
    ).content.decode()
    assert 'name="next" value="/entries/?tag=watch"' in body
    assert reverse("entries:label_add", args=[entry.pk]) + '"' in body


def test_htmx_remove_announces_and_moves_focus_to_the_add_control(
    client, person, entry
):
    Tag.set_for(entry, ["watch"])
    response = client.post(_remove(entry), {"name": "watch"}, headers=HTMX)
    body = response.content.decode()
    assert response.status_code == 200
    assert "Label “watch” removed." in body
    assert ">watch</a>" not in body
    assert "<summary autofocus>" in body
    assert not OPEN.search(body)


def test_htmx_gets_the_error_in_the_fragment(client, person, entry):
    response = client.post(_add(entry), {"name": "x" * 51}, headers=HTMX)
    body = response.content.decode()
    assert response.status_code == 422
    assert f'id="labels-{entry.pk}"' in body
    assert "at most 50 characters" in body
    assert f'aria-describedby="label-{entry.pk}-error"' in body
    assert 'aria-invalid="true"' in body
    assert f'value="{"x" * 51}"' in body
    assert OPEN.search(body)
    assert "HX-Request" in response["Vary"]
    assert _messages(response) == []
    assert _names(entry) == []


def test_htmx_removing_the_label_being_filtered_by_redirects_to_all_entries(
    client, person, entry
):
    """Pruning the label the current page is filtered by leaves no
    fragment to answer with: a real navigation, the same `htmx_redirect`
    `entry_delete` sends for the same situation — otherwise the page
    stays on a now-404 filter."""
    Tag.set_for(entry, ["watch"])
    response = client.post(
        _remove(entry),
        {"name": "watch", "next": "/entries/?tag=watch"},
        headers=HTMX,
    )
    assert response.status_code == 200
    assert response["HX-Redirect"] == reverse("entries:list")
    assert "entry-labels" not in response.text


def test_the_page_an_htmx_removal_redirects_to_confirms_the_removal(
    client, person, entry
):
    """The navigation replaces the page the status would have been
    written to, so the confirmation travels as a message instead."""
    Tag.set_for(entry, ["watch"])
    client.post(
        _remove(entry),
        {"name": "watch", "next": "/entries/?tag=watch"},
        headers=HTMX,
    )
    page = client.get(reverse("entries:list"))
    assert [str(m) for m in page.context["messages"]] == ["Label “watch” removed."]


def test_htmx_removing_a_surviving_filter_label_still_answers_in_place(
    client, person, entry
):
    other = Entry.objects.create(owner=person, url="https://example.com/b")
    Tag.set_for(entry, ["watch"])
    Tag.set_for(other, ["watch"])
    response = client.post(
        _remove(entry),
        {"name": "watch", "next": "/entries/?tag=watch"},
        headers=HTMX,
    )
    assert response.status_code == 200
    assert "HX-Redirect" not in response
    assert f'id="labels-{entry.pk}"' in response.text


def test_htmx_drains_the_emptied_collection_notice_in_place(client, person, entry):
    """The "now empty" notice has nowhere to live but the messages
    list, same as a delete that empties a collection — drained from
    the queue now, not left for whatever page is seen next."""
    Tag.set_for(entry, ["watch"])
    label = Tag.objects.get(owner=person, name="watch")
    Collection.objects.create(
        owner=person, name="Watches", kind=Collection.BY_LABEL, label=label
    )
    response = client.post(_remove(entry), {"name": "watch"}, headers=HTMX)
    body = response.text
    assert 'id="messages" role="status" hx-swap-oob="true"' in body
    assert "“Watches” has nothing in it now" in body

    # Drained, not only shown: the next page does not see it again.
    later = client.get(reverse("entries:list"))
    assert "has nothing in it now" not in later.content.decode()


def test_adding_a_brand_new_label_refreshes_the_sidebar(client, person, entry):
    """A label the owner never had before now belongs in the "Labels"
    sidebar too, not only on the next full page load."""
    response = client.post(_add(entry), {"name": "watch"}, headers=HTMX)
    body = response.text
    assert 'id="tags-sidebar" hx-swap-oob="true"' in body
    assert 'href="?tag=watch"' in body


def test_adding_a_label_the_owner_already_has_does_not_refresh_the_sidebar(
    client, person, entry
):
    other = Entry.objects.create(owner=person, url="https://example.com/b")
    Tag.set_for(other, ["watch"])
    body = client.post(_add(entry), {"name": "watch"}, headers=HTMX).text
    assert "tags-sidebar" not in body


def test_removing_the_last_entry_with_a_label_refreshes_the_sidebar(
    client, person, entry
):
    """Pruning the owner's last "watch" takes it off the sidebar too,
    the same question a delete that empties a label already asks."""
    Tag.set_for(entry, ["watch"])
    body = client.post(_remove(entry), {"name": "watch"}, headers=HTMX).text
    assert 'id="tags-sidebar" hx-swap-oob="true"' in body
    assert "watch" not in body.split('id="tags-sidebar"')[1]


def test_removing_a_label_that_survives_does_not_refresh_the_sidebar(
    client, person, entry
):
    other = Entry.objects.create(owner=person, url="https://example.com/b")
    Tag.set_for(entry, ["watch"])
    Tag.set_for(other, ["watch"])
    body = client.post(_remove(entry), {"name": "watch"}, headers=HTMX).text
    assert "tags-sidebar" not in body


def test_the_list_renders_each_entrys_labels_through_the_partial(client, person):
    first = Entry.objects.create(owner=person, url="https://example.com/1")
    second = Entry.objects.create(owner=person, url="https://example.com/2")
    Tag.set_for(first, ["books"])
    Tag.set_for(second, ["watch"])
    body = client.get(reverse("entries:list"), {"tag": "books"}).content.decode()
    assert body.count(f'id="labels-{first.pk}"') == 1
    assert "hx-swap-oob" not in body
    assert body.count('id="status"') == 1
    assert not OPEN.search(body)
    assert "autofocus>" not in body.split("<dialog")[0]
    assert 'aria-label="Remove label books"' in body
    assert 'name="next" value="/entries/?tag=books"' in body
    assert reverse("entries:label_remove", args=[first.pk]) in body


def test_the_entry_labels_div_stays_the_articles_third_child(client, person, entry):
    Tag.set_for(entry, ["books"])
    body = client.get(reverse("entries:list")).content.decode()
    article = body.split("<article>")[1]
    order = [
        article.index('class="entry-head"'),
        article.index('class="entry-body"'),
        article.index(f'class="entry-labels" id="labels-{entry.pk}"'),
        article.index('class="entry-actions"'),
    ]
    assert order == sorted(order)


def _summary(body):
    return body.split("<summary")[1].split("</summary>")[0]


def test_the_summary_carries_both_plus_label_and_cancel_text(client, person, entry):
    """Both texts live in the markup always; CSS shows the right one
    for details[open] — see docs/dev/javascript.md."""
    body = client.get(reverse("entries:list")).content.decode()
    summary = _summary(body)
    assert '<span class="label-add-text">+ Label</span>' in summary
    # The multiplication sign is decorative (aria-hidden), so the
    # accessible name is "Cancel" alone.
    assert '<span class="label-cancel-text"><span aria-hidden="true">' in summary
    assert "</span> Cancel</span>" in summary


def test_the_summary_still_carries_both_texts_while_open(client, person, entry):
    body = client.post(_add(entry), {"name": "watch"}, headers=HTMX).content.decode()
    summary = _summary(body)
    assert "+ Label" in summary
    assert "Cancel" in summary
