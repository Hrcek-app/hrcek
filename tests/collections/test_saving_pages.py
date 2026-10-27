"""Saving a collection, as the visitor meets it on the pages."""

import pytest
from django.urls import reverse
from django.utils import timezone

from hrcek.accounts.models import User
from hrcek.collections.models import Collection, CollectionEntry, SavedCollection
from hrcek.collections.services import save_collection
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
def bor():
    return _person("bor@example.com")


@pytest.fixture
def wishes(nina):
    wishes = Collection.objects.create(
        owner=nina,
        name="Birthday",
        visibility=Collection.UNLISTED,
        is_wish_list=True,
    )
    entry = Entry.objects.create(
        owner=nina, url="https://example.com/socks", title="Wool socks"
    )
    CollectionEntry.objects.create(collection=wishes, entry=entry)
    return wishes


def _unlisted(collection, action):
    return reverse(f"shared:unlisted_{action}", kwargs={"secret": collection.secret})


def _public(collection, action):
    return reverse(
        f"shared:public_{action}",
        kwargs={"namespace": collection.owner.namespace, "slug": collection.slug},
    )


def _make_public(collection):
    collection.visibility = Collection.PUBLIC
    collection.save()


def test_visitor_sees_save_line_at_bottom(client, wishes, bor):
    client.force_login(bor)
    page = client.get(wishes.unlisted_url()).content.decode()
    assert "Want to find this again?" in page
    assert "Save to your collections" in page
    assert page.index('id="saving"') > page.index("Wool socks")


def test_anonymous_and_owner_see_no_save_line(client, wishes, nina):
    assert 'id="saving"' not in client.get(wishes.unlisted_url()).content.decode()
    client.force_login(nina)
    assert 'id="saving"' not in client.get(wishes.unlisted_url()).content.decode()


def test_save_from_secret_link(client, wishes, bor):
    client.force_login(bor)
    response = client.post(_unlisted(wishes, "save"))
    assert response.status_code == 302
    assert response.url == wishes.shared_url()
    assert SavedCollection.objects.get(user=bor, collection=wishes).via_secret is True
    page = client.get(response.url).content.decode()
    assert "Saved to your collections." in page
    assert "Unfollow" in page


def test_save_from_public_address(client, wishes, bor):
    _make_public(wishes)
    client.force_login(bor)
    response = client.post(_public(wishes, "save"))
    assert response.url == wishes.shared_url()
    assert SavedCollection.objects.get(user=bor).via_secret is False


def test_unfollow_on_shared_page(client, wishes, bor):
    save_collection(wishes, bor, via_secret=True)
    client.force_login(bor)
    response = client.post(_unlisted(wishes, "unfollow"))
    assert response.url == wishes.shared_url()
    assert not SavedCollection.objects.exists()
    page = client.get(response.url).content.decode()
    assert "Save to your collections" in page


def test_public_save_shows_save_at_secret_link_after_narrowing(client, wishes, bor):
    _make_public(wishes)
    save_collection(wishes, bor, via_secret=False)
    wishes.visibility = Collection.UNLISTED
    wishes.save()
    client.force_login(bor)
    page = client.get(wishes.unlisted_url()).content.decode()
    assert "Save to your collections" in page
    assert "Saved to your collections." not in page


def test_owner_forced_post_gets_error_message(client, wishes, nina):
    client.force_login(nina)
    response = client.post(_unlisted(wishes, "save"), follow=True)
    assert "You cannot save your own collection." in response.content.decode()
    assert not SavedCollection.objects.exists()


def test_signed_out_post_redirects_to_sign_in_with_page_as_next(client, wishes):
    response = client.post(_unlisted(wishes, "save"))
    assert response.status_code == 302
    assert response.url == f"/?next={wishes.unlisted_url()}"
    assert not SavedCollection.objects.exists()


@pytest.mark.parametrize("action", ["save", "unfollow"])
def test_save_routes_are_post_only(client, wishes, bor, action):
    client.force_login(bor)
    assert client.get(_unlisted(wishes, action)).status_code == 405


def test_wrong_secret_is_404(client, wishes, bor):
    client.force_login(bor)
    url = reverse("shared:unlisted_save", kwargs={"secret": "nope"})
    assert client.post(url).status_code == 404


# The Collections page.


def _unfollow_from_list(collection):
    return reverse("collections:unfollow", kwargs={"pk": collection.pk})


def test_saved_section_lists_saved_after_own(client, wishes, bor):
    Collection.objects.create(owner=bor, name="Mine")
    save_collection(wishes, bor, via_secret=True)
    client.force_login(bor)
    page = client.get(reverse("collections:list")).content.decode()
    assert page.index("Saved collections") > page.index("Mine")
    assert f'href="{wishes.shared_url()}"' in page
    saved = page[page.index("Saved collections") :]
    assert "nina" in saved
    assert "Wish list" in saved


def test_saved_row_without_public_name_shows_name_only(client, bor):
    ana = _person("ana@example.com", display_name="Ana Secret")
    garden = Collection.objects.create(
        owner=ana, name="Garden", visibility=Collection.UNLISTED
    )
    save_collection(garden, bor, via_secret=True)
    client.force_login(bor)
    page = client.get(reverse("collections:list")).content.decode()
    assert "Garden" in page
    assert "Ana Secret" not in page
    assert "ana@example.com" not in page


def test_public_save_never_reveals_secret(client, wishes, bor):
    _make_public(wishes)
    save_collection(wishes, bor, via_secret=False)
    wishes.visibility = Collection.UNLISTED
    wishes.save()
    client.force_login(bor)
    page = client.get(reverse("collections:list")).content.decode()
    assert wishes.secret not in page


def test_unfollow_from_list(client, wishes, bor):
    save_collection(wishes, bor, via_secret=True)
    client.force_login(bor)
    response = client.post(_unfollow_from_list(wishes))
    assert response.status_code == 302
    assert response.url == reverse("collections:list")
    assert not SavedCollection.objects.exists()
    page = client.get(response.url).content.decode()
    assert "“Birthday” is no longer in your saved collections." in page


def test_unfollow_requires_sign_in(client, wishes, bor):
    save_collection(wishes, bor, via_secret=True)
    response = client.post(_unfollow_from_list(wishes))
    assert response.status_code == 302
    assert SavedCollection.objects.exists()


def test_unfollow_from_list_is_post_only(client, wishes, bor):
    client.force_login(bor)
    assert client.get(_unfollow_from_list(wishes)).status_code == 405


def test_empty_saved_section(client, bor):
    client.force_login(bor)
    page = client.get(reverse("collections:list")).content.decode()
    assert "Saved collections" in page
    assert "You have not saved anyone else's collections yet." in page


# In place, with htmx.

HTMX = {"HX-Request": "true"}


def test_htmx_save_returns_the_line(client, wishes, bor):
    client.force_login(bor)
    response = client.post(_unlisted(wishes, "save"), headers=HTMX)
    body = response.content.decode()
    assert response.status_code == 200
    assert 'id="saving"' in body
    assert "Saved to your collections." in body
    assert "<html" not in body
    assert 'id="status"' in body
    assert "HX-Request" in response.headers["Vary"]


def test_htmx_owner_save_navigates_back_with_the_error(client, wishes, nina):
    """Only a crafted request gets here: the owner has no button. Any
    403 to htmx means "sign in again" (core.middleware), so the refusal
    is a real navigation back to the page, where the message waits."""
    client.force_login(nina)
    response = client.post(_unlisted(wishes, "save"), headers=HTMX)
    assert response["HX-Redirect"] == wishes.shared_url()
    assert not SavedCollection.objects.exists()
    page = client.get(wishes.shared_url()).content.decode()
    assert "You cannot save your own collection." in page


def test_htmx_unfollow_from_list_returns_oob_only(client, wishes, bor):
    save_collection(wishes, bor, via_secret=True)
    client.force_login(bor)
    response = client.post(_unfollow_from_list(wishes), headers=HTMX)
    body = response.content.decode()
    assert response.status_code == 200
    assert 'id="status"' in body
    assert "hx-swap-oob" in body
    assert 'id="saved-list" hx-swap-oob="true"' in body
    assert "HX-Request" in response.headers["Vary"]


def test_htmx_unfollow_with_others_left_keeps_them(client, wishes, bor, nina):
    garden = Collection.objects.create(
        owner=nina, name="Garden", visibility=Collection.UNLISTED
    )
    save_collection(wishes, bor, via_secret=True)
    save_collection(garden, bor, via_secret=True)
    client.force_login(bor)
    body = client.post(_unfollow_from_list(wishes), headers=HTMX).content.decode()
    assert "saved-list" not in body


@pytest.mark.parametrize(
    "visibility", [Collection.PRIVATE, Collection.UNLISTED, Collection.PUBLIC]
)
@pytest.mark.parametrize("headers", [{}, HTMX], ids=["no-js", "htmx"])
def test_unfollow_by_id_never_names_a_collection_not_saved(
    client, nina, bor, visibility, headers
):
    """The id is anybody's to post; only the requester's own save may
    lend the answer a name."""
    secret = Collection.objects.create(
        owner=nina, name="Secret divorce lawyers", visibility=visibility
    )
    client.force_login(bor)
    response = client.post(_unfollow_from_list(secret), headers=headers, follow=True)
    assert "Secret divorce lawyers" not in response.content.decode()
