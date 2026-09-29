import pytest
from django.urls import reverse
from django.utils import timezone

from hrcek.accounts.models import User
from hrcek.collections.models import Collection, CollectionEntry
from hrcek.entries.models import Entry, Tag

pytestmark = pytest.mark.django_db


def _person(email):
    return User.objects.create_user(
        email=email,
        password="a-long-enough-passphrase",
        email_verified_at=timezone.now(),
    )


@pytest.fixture
def nina():
    return _person("nina@example.com")


@pytest.fixture
def signed_in(client, nina):
    client.force_login(nina)
    return client


def test_the_list_needs_a_session(client):
    assert client.get(reverse("collections:list")).status_code == 302


def test_a_collection_can_be_made(signed_in, nina):
    response = signed_in.post(
        reverse("collections:create"),
        {"name": "Watches", "description": "", "kind": Collection.MANUAL},
        follow=True,
    )
    assert response.status_code == 200
    assert Collection.objects.filter(owner=nina, name="Watches").exists()


def test_a_label_collection_names_a_label(signed_in, nina):
    tag = Tag.objects.create(owner=nina, name="watches")
    signed_in.post(
        reverse("collections:create"),
        {
            "name": "Watches",
            "description": "",
            "kind": Collection.BY_LABEL,
            "label": tag.pk,
        },
        follow=True,
    )
    collection = Collection.objects.get(owner=nina, name="Watches")
    assert collection.label == tag


def test_a_label_collection_without_a_label_is_refused(signed_in):
    response = signed_in.post(
        reverse("collections:create"),
        {"name": "Watches", "description": "", "kind": Collection.BY_LABEL},
    )
    assert response.status_code == 200
    assert not Collection.objects.exists()


def test_only_your_own_labels_are_offered(signed_in):
    marko = _person("marko@example.com")
    theirs = Tag.objects.create(owner=marko, name="secret-project")
    page = signed_in.get(reverse("collections:create"))
    assert "secret-project" not in page.text
    assert theirs.name not in page.text


def test_the_kind_cannot_be_changed_later(signed_in, nina):
    collection = Collection.objects.create(owner=nina, name="Watches")
    tag = Tag.objects.create(owner=nina, name="watches")
    signed_in.post(
        reverse("collections:edit", args=[collection.pk]),
        {
            "name": "Watches",
            "description": "",
            "kind": Collection.BY_LABEL,
            "label": tag.pk,
        },
    )
    collection.refresh_from_db()
    assert collection.kind == Collection.MANUAL
    assert collection.label is None


def test_the_name_and_description_can_be_changed(signed_in, nina):
    collection = Collection.objects.create(owner=nina, name="Watches")
    signed_in.post(
        reverse("collections:edit", args=[collection.pk]),
        {"name": "Clocks", "description": "Ticking things."},
    )
    collection.refresh_from_db()
    assert collection.name == "Clocks"
    assert collection.description == "Ticking things."


def test_somebody_elses_collection_is_a_404(signed_in):
    marko = _person("marko@example.com")
    theirs = Collection.objects.create(owner=marko, name="Theirs")
    assert (
        signed_in.get(reverse("collections:detail", args=[theirs.pk])).status_code
        == 404
    )


def test_an_entry_can_be_added_and_removed(signed_in, nina):
    collection = Collection.objects.create(owner=nina, name="Watches")
    entry = Entry.objects.create(owner=nina, url="https://example.com/1")

    signed_in.post(
        reverse("collections:add_entry", args=[collection.pk]), {"entry": entry.pk}
    )
    assert list(collection.entries()) == [entry]

    signed_in.post(reverse("collections:remove_entry", args=[collection.pk, entry.pk]))
    assert collection.entries().count() == 0


def test_adding_somebody_elses_entry_is_refused(signed_in, nina):
    marko = _person("marko@example.com")
    collection = Collection.objects.create(owner=nina, name="Watches")
    theirs = Entry.objects.create(owner=marko, url="https://example.com/1")
    response = signed_in.post(
        reverse("collections:add_entry", args=[collection.pk]), {"entry": theirs.pk}
    )
    assert response.status_code == 404
    assert CollectionEntry.objects.count() == 0


def test_an_entry_already_in_it_is_not_offered_again(signed_in, nina):
    collection = Collection.objects.create(owner=nina, name="Watches")
    entry = Entry.objects.create(
        owner=nina, url="https://example.com/1", title="Already here"
    )
    CollectionEntry.objects.create(collection=collection, entry=entry)

    page = signed_in.get(reverse("collections:detail", args=[collection.pk]))
    assert page.text.count("Already here") == 1, "listed once, not offered again"


def test_a_collection_can_be_deleted_without_touching_its_entries(signed_in, nina):
    collection = Collection.objects.create(owner=nina, name="Watches")
    entry = Entry.objects.create(owner=nina, url="https://example.com/1")
    CollectionEntry.objects.create(collection=collection, entry=entry)

    signed_in.post(reverse("collections:delete", args=[collection.pk]))
    assert not Collection.objects.exists()
    assert Entry.objects.filter(pk=entry.pk).exists()


def test_the_list_shows_your_collections_and_not_others(signed_in, nina):
    marko = _person("marko@example.com")
    Collection.objects.create(owner=nina, name="Mine")
    Collection.objects.create(owner=marko, name="Theirs")
    page = signed_in.get(reverse("collections:list"))
    assert "Mine" in page.text
    assert "Theirs" not in page.text


def test_a_manual_collection_refuses_a_label_rather_than_ignoring_it(signed_in, nina):
    """Silently dropping it would teach the wrong thing.

    The form hides the label picker unless the kind is "label", so
    reaching here means the choice was made some other way. Saying so
    is better than accepting the submission and quietly discarding
    half of it.
    """
    tag = Tag.objects.create(owner=nina, name="watches")
    response = signed_in.post(
        reverse("collections:create"),
        {
            "name": "Watches",
            "description": "",
            "kind": Collection.MANUAL,
            "label": tag.pk,
        },
    )
    assert response.status_code == 200
    assert not Collection.objects.exists()


def test_the_label_picker_is_marked_for_the_kind_that_needs_it(signed_in):
    """The markup, not a script, says which kind reveals the picker."""
    page = signed_in.get(reverse("collections:create")).text
    assert "data-kind-select" in page
    assert f'data-label-field="{Collection.BY_LABEL}"' in page


def test_no_template_comment_leaks_onto_the_page(signed_in, nina):
    """A {# #} comment cannot span lines; Django renders it verbatim.

    It looked like a comment in the source and appeared as prose on
    the page, which is exactly the failure that is easy to miss.
    """
    for url in (
        reverse("collections:create"),
        reverse("collections:list"),
    ):
        body = signed_in.get(url).text
        assert "{#" not in body, f"template comment leaked into {url}"
        assert "Progressive enhancement" not in body


def test_every_page_of_this_app_is_free_of_leaked_comments(signed_in, nina):
    collection = Collection.objects.create(owner=nina, name="Watches")
    pages = [
        reverse("collections:detail", args=[collection.pk]),
        reverse("collections:edit", args=[collection.pk]),
        reverse("collections:delete", args=[collection.pk]),
    ]
    for url in pages:
        body = signed_in.get(url).text
        assert "{#" not in body, f"template comment leaked into {url}"


def test_an_entrys_tags_link_to_your_entries_carrying_them(signed_in, nina):
    entry = Entry.objects.create(owner=nina, url="https://example.com/w")
    Tag.set_for(entry, ["watches"])
    collection = Collection.objects.create(owner=nina, name="Mine", kind="manual")
    CollectionEntry.objects.create(collection=collection, entry=entry)
    body = signed_in.get(reverse("collections:detail", args=[collection.pk])).text
    assert f'href="{reverse("entries:list")}?tag=watches"' in body
