"""A wish list as its visitors, and its owner, meet it."""

import pytest
from django.urls import reverse
from django.utils import timezone

from hrcek.accounts.models import User
from hrcek.collections.models import Collection, CollectionEntry, GotIt
from hrcek.entries.models import Entry

pytestmark = pytest.mark.django_db


def _person(email, **extra):
    return User.objects.create_user(
        email=email,
        password="a-long-enough-passphrase",
        email_verified_at=timezone.now(),
        **extra,
    )


@pytest.fixture
def nina():
    return _person("nina@example.com", namespace="nina")


@pytest.fixture
def ana():
    return _person("ana@example.com")


@pytest.fixture
def bor():
    return _person("bor@example.com")


@pytest.fixture
def wishes(nina):
    return Collection.objects.create(
        owner=nina,
        name="Birthday",
        visibility=Collection.UNLISTED,
        is_wish_list=True,
    )


def _on(collection, title):
    entry = Entry.objects.create(
        owner=collection.owner, url=f"https://example.com/{title}", title=title
    )
    CollectionEntry.objects.create(collection=collection, entry=entry)
    return entry


def _got_it_url(collection, entry):
    return reverse(
        "shared:unlisted_got_it",
        kwargs={"secret": collection.secret, "entry_pk": entry.pk},
    )


def _undo_url(collection, entry):
    return reverse(
        "shared:unlisted_undo",
        kwargs={"secret": collection.secret, "entry_pk": entry.pk},
    )


def test_a_signed_in_visitor_gets_an_item(client, wishes, ana):
    entry = _on(wishes, "Watch")
    client.force_login(ana)
    response = client.post(_got_it_url(wishes, entry))
    assert response.status_code == 302
    assert response.url == wishes.unlisted_url()
    assert GotIt.objects.get().got_by == ana


def test_a_signed_in_visitor_sees_the_button(client, wishes, ana):
    entry = _on(wishes, "Watch")
    client.force_login(ana)
    page = client.get(wishes.unlisted_url()).content.decode()
    assert _got_it_url(wishes, entry) in page


def test_the_giver_still_sees_it_with_undo(client, wishes, ana):
    entry = _on(wishes, "Watch")
    GotIt.objects.create(collection=wishes, entry=entry, got_by=ana)
    client.force_login(ana)
    page = client.get(wishes.unlisted_url()).content.decode()
    assert "Watch" in page
    assert "You got this." in page
    assert _undo_url(wishes, entry) in page


def test_others_no_longer_see_it(client, wishes, ana, bor):
    entry = _on(wishes, "Watch")
    _on(wishes, "Scarf")
    GotIt.objects.create(collection=wishes, entry=entry, got_by=ana)
    client.force_login(bor)
    page = client.get(wishes.unlisted_url()).content.decode()
    assert "Watch" not in page
    assert "Scarf" in page
    client.logout()
    assert "Watch" not in client.get(wishes.unlisted_url()).content.decode()


def test_the_owner_on_their_shared_page_sees_all_and_no_buttons(
    client, wishes, nina, ana
):
    entry = _on(wishes, "Watch")
    GotIt.objects.create(collection=wishes, entry=entry, got_by=ana)
    client.force_login(nina)
    page = client.get(wishes.unlisted_url()).content.decode()
    assert "Watch" in page
    assert _got_it_url(wishes, entry) not in page
    assert _undo_url(wishes, entry) not in page
    assert "You got this." not in page


def test_anonymous_visitors_are_invited_to_sign_in_but_get_no_buttons(client, wishes):
    entry = _on(wishes, "Watch")
    page = client.get(wishes.unlisted_url()).content.decode()
    assert f"?next={wishes.unlisted_url()}" in page
    assert _got_it_url(wishes, entry) not in page


def test_an_anonymous_post_goes_to_sign_in_and_back_to_the_page(client, wishes):
    entry = _on(wishes, "Watch")
    response = client.post(_got_it_url(wishes, entry))
    assert response.status_code == 302
    assert response.url == f"/?next={wishes.unlisted_url()}"
    assert not GotIt.objects.exists()


@pytest.mark.parametrize("which", ["unknown", "not_on_list", "someone_elses"])
def test_an_item_not_on_the_list_gets_one_answer(client, wishes, ana, bor, which):
    entry_pk = {
        "unknown": 999_999,
        "not_on_list": Entry.objects.create(
            owner=wishes.owner, url="https://example.com/x"
        ).pk,
        "someone_elses": Entry.objects.create(
            owner=bor, url="https://example.com/y"
        ).pk,
    }[which]
    client.force_login(ana)
    response = client.post(
        reverse(
            "shared:unlisted_got_it",
            kwargs={"secret": wishes.secret, "entry_pk": entry_pk},
        ),
        follow=True,
    )
    assert "That item is not on this list." in response.content.decode()
    assert not GotIt.objects.exists()


def test_somebody_else_already_got_it(client, wishes, ana, bor):
    entry = _on(wishes, "Watch")
    GotIt.objects.create(collection=wishes, entry=entry, got_by=ana)
    client.force_login(bor)
    response = client.post(_got_it_url(wishes, entry), follow=True)
    assert "Somebody else has already got this." in response.content.decode()


def test_undo(client, wishes, ana):
    entry = _on(wishes, "Watch")
    GotIt.objects.create(collection=wishes, entry=entry, got_by=ana)
    client.force_login(ana)
    response = client.post(_undo_url(wishes, entry))
    assert response.url == wishes.unlisted_url()
    assert not GotIt.objects.exists()


def test_everything_got(client, wishes, ana):
    entry = _on(wishes, "Watch")
    GotIt.objects.create(collection=wishes, entry=entry, got_by=ana)
    page = client.get(wishes.unlisted_url()).content.decode()
    assert "Everything on this list has been got." in page


def test_the_public_address_works_too(client, wishes, ana):
    wishes.visibility = Collection.PUBLIC
    wishes.save()
    entry = _on(wishes, "Watch")
    client.force_login(ana)
    page = client.get(wishes.public_url()).content.decode()
    url = reverse(
        "shared:public_got_it",
        kwargs={"namespace": "nina", "slug": wishes.slug, "entry_pk": entry.pk},
    )
    assert url in page
    response = client.post(url)
    assert response.url == wishes.public_url()
    assert GotIt.objects.exists()


def test_an_unlisted_address_is_dead_once_public(client, wishes, ana):
    entry = _on(wishes, "Watch")
    url = _got_it_url(wishes, entry)
    wishes.visibility = Collection.PUBLIC
    wishes.save()
    client.force_login(ana)
    assert client.post(url).status_code == 404


def test_got_it_only_answers_post(client, wishes, ana):
    entry = _on(wishes, "Watch")
    client.force_login(ana)
    assert client.get(_got_it_url(wishes, entry)).status_code == 405


def test_an_ordinary_shared_collection_has_no_buttons(client, wishes, ana):
    wishes.is_wish_list = False
    wishes.save()
    entry = _on(wishes, "Watch")
    client.force_login(ana)
    page = client.get(wishes.unlisted_url()).content.decode()
    assert _got_it_url(wishes, entry) not in page


# --- the owner's page ---------------------------------------------------


def test_the_owner_page_is_unspoiled_by_default(client, wishes, nina, ana):
    entry = _on(wishes, "Watch")
    GotIt.objects.create(collection=wishes, entry=entry, got_by=ana)
    client.force_login(nina)
    page = client.get(f"/collections/{wishes.pk}/").content.decode()
    assert "Wish list" in page
    assert "Show what has been got" in page
    assert 'class="tag got"' not in page
    assert reverse("collections:put_back", args=[wishes.pk, entry.pk]) not in page


def test_an_ordinary_collection_has_no_reveal(client, wishes, nina):
    wishes.is_wish_list = False
    wishes.save()
    client.force_login(nina)
    page = client.get(f"/collections/{wishes.pk}/?got=show").content.decode()
    assert "Show what has been got" not in page
    assert "Wish list" not in page


def test_the_owner_can_reveal_without_learning_who(client, wishes, nina, ana):
    entry = _on(wishes, "Watch")
    GotIt.objects.create(collection=wishes, entry=entry, got_by=ana)
    client.force_login(nina)
    page = client.get(f"/collections/{wishes.pk}/?got=show").content.decode()
    assert 'class="tag got"' in page
    assert reverse("collections:put_back", args=[wishes.pk, entry.pk]) in page
    assert "ana@example.com" not in page


def test_putting_back_keeps_the_reveal_once_but_not_for_ever(client, wishes, nina, ana):
    entry = _on(wishes, "Watch")
    GotIt.objects.create(collection=wishes, entry=entry, got_by=ana)
    client.force_login(nina)
    response = client.post(
        reverse("collections:put_back", args=[wishes.pk, entry.pk]),
        {"reveal": "1"},
    )
    assert response.url == f"/collections/{wishes.pk}/?got=show"
    assert not GotIt.objects.exists()
    GotIt.objects.create(collection=wishes, entry=entry, got_by=ana)
    plain = client.get(f"/collections/{wishes.pk}/").content.decode()
    assert 'class="tag got"' not in plain


def test_nobody_else_can_put_back(client, wishes, ana):
    entry = _on(wishes, "Watch")
    GotIt.objects.create(collection=wishes, entry=entry, got_by=ana)
    client.force_login(ana)
    response = client.post(reverse("collections:put_back", args=[wishes.pk, entry.pk]))
    assert response.status_code == 404
    assert GotIt.objects.exists()


def _tick(client, entry, collection):
    """Save the entry's own form with `collection` ticked: the way an
    entry joins a manual collection now that the collection's own page
    offers no form for it."""
    return client.post(
        reverse("entries:edit", args=[entry.pk]),
        {
            "url": entry.url,
            "title": entry.title,
            "notes": "",
            "tags": "",
            "collections": [collection.pk],
        },
        follow=True,
    )


def test_adding_back_an_item_already_got_says_so(client, wishes, nina, ana):
    entry = _on(wishes, "Watch")
    GotIt.objects.create(collection=wishes, entry=entry, got_by=ana)
    CollectionEntry.objects.filter(entry=entry).delete()
    client.force_login(nina)
    page = _tick(client, entry, wishes).content.decode()
    assert "Somebody has already got this for “Birthday”." in page
    assert f"/collections/{wishes.pk}/?back={entry.pk}" in page
    assert "ana@example.com" not in page


def test_the_came_back_notice_shows_nothing_for_an_item_not_got(client, wishes, nina):
    entry = _on(wishes, "Watch")
    client.force_login(nina)
    page = client.get(f"/collections/{wishes.pk}/?back={entry.pk}").content.decode()
    assert "already got" not in page


def test_adding_a_fresh_item_says_nothing_of_the_sort(client, wishes, nina):
    entry = Entry.objects.create(owner=nina, url="https://example.com/new")
    client.force_login(nina)
    page = _tick(client, entry, wishes).content.decode()
    assert "already got" not in page


def test_a_strange_back_parameter_is_ignored(client, wishes, nina):
    client.force_login(nina)
    for back in ("²", "x", "-1", ""):
        response = client.get(f"/collections/{wishes.pk}/", {"back": back})
        assert response.status_code == 200


def test_resubmitting_an_item_already_on_the_list_says_nothing(
    client, wishes, nina, ana
):
    """Already a member before the save, so this is not an arrival:
    nothing is said, got or not."""
    entry = _on(wishes, "Watch")
    GotIt.objects.create(collection=wishes, entry=entry, got_by=ana)
    client.force_login(nina)
    page = _tick(client, entry, wishes).content.decode()
    assert "already got" not in page


def test_the_owner_cannot_probe_through_undo(client, wishes, nina, ana):
    got = _on(wishes, "Watch")
    free = _on(wishes, "Scarf")
    GotIt.objects.create(collection=wishes, entry=got, got_by=ana)
    client.force_login(nina)
    answers = {
        client.post(_undo_url(wishes, e), follow=True)
        .content.decode()
        .count("You cannot say “Got it” on your own wish list.")
        for e in (got, free)
    }
    assert answers == {1}
    assert GotIt.objects.filter(entry=got).exists()
