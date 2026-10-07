from urllib.parse import unquote

import pytest
from django.urls import reverse
from django.utils import timezone

from hrcek.accounts.models import User
from hrcek.collections.models import Collection, GotIt
from hrcek.entries.models import Entry, Tag
from hrcek.entries.services import save_entry

pytestmark = pytest.mark.django_db

PASSWORD = "a-long-enough-passphrase"


def _person(email):
    return User.objects.create_user(
        email=email, password=PASSWORD, email_verified_at=timezone.now()
    )


@pytest.fixture
def nina():
    return _person("nina@example.com")


def test_saving_creates_an_entry(nina):
    entry, created = save_entry(
        nina,
        url="https://example.com/watch",
        title="A watch",
        notes="38mm",
        tag_names=["watches"],
    )
    assert created is True
    assert entry.title == "A watch"
    assert [t.name for t in entry.tags.all()] == ["watches"]


def test_saving_the_same_url_again_updates_it(nina):
    save_entry(nina, url="https://example.com/watch", title="First")
    entry, created = save_entry(
        nina,
        url="https://example.com/watch",
        title="Second",
        notes="more",
        tag_names=["watches"],
    )
    assert created is False
    assert Entry.objects.filter(owner=nina).count() == 1
    assert entry.title == "Second"
    assert entry.notes == "more"


def test_the_url_is_normalised_before_matching(nina):
    save_entry(nina, url="https://example.com/watch", title="First")
    _entry, created = save_entry(
        nina, url="  https://EXAMPLE.com/watch ", title="Second"
    )
    assert created is False
    assert Entry.objects.filter(owner=nina).count() == 1


def test_another_persons_identical_url_is_untouched(nina):
    marko = _person("marko@example.com")
    theirs, _ = save_entry(marko, url="https://example.com/watch", title="Theirs")
    save_entry(nina, url="https://example.com/watch", title="Mine")
    theirs.refresh_from_db()
    assert theirs.title == "Theirs"


def test_the_create_page_saves_and_redirects(client, nina):
    client.force_login(nina)
    response = client.post(
        reverse("entries:create"),
        {
            "url": "https://example.com/watch",
            "title": "A watch",
            "notes": "",
            "tags": "watches, diving",
        },
    )
    assert response.status_code == 302
    entry = Entry.objects.get(owner=nina)
    assert sorted(t.name for t in entry.tags.all()) == ["diving", "watches"]


def test_creating_with_a_url_you_already_have_edits_it(client, nina):
    save_entry(nina, url="https://example.com/watch", title="First")
    client.force_login(nina)
    client.post(
        reverse("entries:create"),
        {
            "url": "https://example.com/watch",
            "title": "Second",
            "notes": "",
            "tags": "",
        },
    )
    assert Entry.objects.filter(owner=nina).count() == 1
    assert Entry.objects.get(owner=nina).title == "Second"


def test_a_bad_url_is_refused(client, nina):
    client.force_login(nina)
    response = client.post(
        reverse("entries:create"),
        {"url": "not a url", "title": "", "notes": "", "tags": ""},
    )
    assert response.status_code == 200
    assert not Entry.objects.filter(owner=nina).exists()


def test_editing_changes_the_entry(client, nina):
    entry, _ = save_entry(
        nina, url="https://example.com/watch", title="First", tag_names=["watches"]
    )
    client.force_login(nina)
    response = client.post(
        reverse("entries:edit", args=[entry.pk]),
        {"url": entry.url, "title": "Second", "notes": "note", "tags": "diving"},
    )
    assert response.status_code == 302
    entry.refresh_from_db()
    assert entry.title == "Second"
    assert [t.name for t in entry.tags.all()] == ["diving"]
    # "watches" was left with no entries.
    assert not Tag.objects.filter(owner=nina, name="watches").exists()


def test_the_edit_form_arrives_filled_in(client, nina):
    entry, _ = save_entry(
        nina,
        url="https://example.com/watch",
        title="A watch",
        tag_names=["watches"],
    )
    client.force_login(nina)
    form = client.get(reverse("entries:edit", args=[entry.pk])).context["form"]
    assert form.initial["title"] == "A watch"
    assert form.initial["tags"] == "watches"


def test_editing_somebody_elses_entry_is_a_404(client, nina):
    marko = _person("marko@example.com")
    theirs, _ = save_entry(marko, url="https://example.com/theirs", title="Theirs")
    client.force_login(nina)
    assert client.get(reverse("entries:edit", args=[theirs.pk])).status_code == 404


def test_deleting_asks_first(client, nina):
    entry, _ = save_entry(nina, url="https://example.com/watch")
    client.force_login(nina)
    assert client.get(reverse("entries:delete", args=[entry.pk])).status_code == 200
    assert Entry.objects.filter(pk=entry.pk).exists()


def test_deleting_removes_it_and_its_orphaned_tags(client, nina):
    entry, _ = save_entry(nina, url="https://example.com/watch", tag_names=["watches"])
    client.force_login(nina)
    response = client.post(reverse("entries:delete", args=[entry.pk]))
    assert response.status_code == 302
    assert not Entry.objects.filter(pk=entry.pk).exists()
    assert not Tag.objects.filter(owner=nina).exists()


def test_deleting_somebody_elses_entry_is_a_404(client, nina):
    marko = _person("marko@example.com")
    theirs, _ = save_entry(marko, url="https://example.com/theirs")
    client.force_login(nina)
    assert client.post(reverse("entries:delete", args=[theirs.pk])).status_code == 404
    assert Entry.objects.filter(pk=theirs.pk).exists()


def test_delete_returns_to_next(client, nina):
    entry, _ = save_entry(nina, url="https://example.com/watch")
    client.force_login(nina)
    response = client.post(
        reverse("entries:delete", args=[entry.pk]), {"next": "/entries/?page=2"}
    )
    assert response["Location"] == "/entries/?page=2"


def test_delete_ignores_an_off_site_next(client, nina):
    entry, _ = save_entry(nina, url="https://example.com/watch")
    client.force_login(nina)
    response = client.post(
        reverse("entries:delete", args=[entry.pk]),
        {"next": "https://evil.example/"},
    )
    assert response["Location"] == reverse("entries:list")


def test_deleting_the_last_entry_of_the_last_page_still_works(client, nina, settings):
    """Deleting it leaves that page number out of range; the list view
    already copes with that (Paginator.get_page), so returning there
    must not blow up."""
    for n in range(settings.ENTRIES_PER_PAGE + 1):
        save_entry(nina, url=f"https://example.com/{n}")
    client.force_login(nina)
    last = Entry.objects.filter(owner=nina).earliest("created_at", "pk")
    response = client.post(
        reverse("entries:delete", args=[last.pk]),
        {"next": "/entries/?page=2"},
        follow=True,
    )
    assert response.status_code == 200


def test_delete_from_a_filtered_page_2_returns_to_it(client, nina, settings):
    """Not just "the list": the exact page and label filter the
    delete was started from, round-tripped through the rendered
    Delete link and back."""
    for n in range(settings.ENTRIES_PER_PAGE + 1):
        entry = Entry.objects.create(owner=nina, url=f"https://example.com/{n}")
        Tag.set_for(entry, ["watches"])
    client.force_login(nina)
    current = "/entries/?tag=watches&page=2"
    body = client.get(current).text
    oldest = Entry.objects.filter(owner=nina).earliest("created_at", "pk")

    delete_prefix = reverse("entries:delete", args=[oldest.pk]) + "?next="
    start = body.index(delete_prefix) + len(delete_prefix)
    next_value = unquote(body[start : body.index('"', start)])
    assert next_value == current

    response = client.post(
        reverse("entries:delete", args=[oldest.pk]), {"next": next_value}
    )
    assert response["Location"] == current


def test_deleting_the_last_entry_of_a_filtered_label_returns_to_all_entries(
    client, nina
):
    """Deleting it prunes the label, and a label nothing carries has no
    page: going back there would be a 404."""
    entry, _ = save_entry(nina, url="https://example.com/rare", tag_names=["rare"])
    client.force_login(nina)
    response = client.post(
        reverse("entries:delete", args=[entry.pk]), {"next": "/entries/?tag=Rare "}
    )
    assert response["Location"] == reverse("entries:list")
    assert client.get(response["Location"]).status_code == 200


def test_deleting_one_of_several_entries_of_a_label_returns_to_its_page(client, nina):
    entry, _ = save_entry(nina, url="https://example.com/rare", tag_names=["rare"])
    save_entry(nina, url="https://example.com/also-rare", tag_names=["rare"])
    client.force_login(nina)
    response = client.post(
        reverse("entries:delete", args=[entry.pk]), {"next": "/entries/?tag=rare"}
    )
    assert response["Location"] == "/entries/?tag=rare"


def test_the_delete_confirmation_keeps_the_way_back(client, nina):
    entry, _ = save_entry(nina, url="https://example.com/watch")
    client.force_login(nina)
    body = client.get(
        reverse("entries:delete", args=[entry.pk]), {"next": "/entries/?page=2"}
    ).text
    assert '<input type="hidden" name="next" value="/entries/?page=2">' in body
    assert 'href="/entries/?page=2"' in body


def _edit_page(client, owner):
    entry = Entry.objects.create(owner=owner, url="https://example.com/e")
    client.force_login(owner)
    return entry, client.get(reverse("entries:edit", args=[entry.pk])).text


def test_leaving_without_saving_sits_beside_save(client, nina):
    """Save and its way out are one decision, so they share a row."""
    _entry, body = _edit_page(client, nina)
    start = body.index('<div class="actions">')
    actions = body[start : body.index("</div>", start)]
    assert '<button type="submit">' in actions
    assert f'href="{reverse("entries:list")}"' in actions


def test_deleting_is_set_well_apart_from_saving(client, nina):
    """A delete link just under Save is one slip away from losing an
    entry. It lives in its own section after the form, not among the
    form's actions."""
    entry, body = _edit_page(client, nina)
    delete = f'href="{reverse("entries:delete", args=[entry.pk])}"'
    assert body.index("</form>") < body.index('<section class="danger-zone"')
    zone = body[body.index('<section class="danger-zone"') :]
    assert delete in zone[: zone.index("</section>")]
    assert body.count(delete) == 1


def test_a_new_entry_has_nothing_to_delete(client, nina):
    client.force_login(nina)
    assert "danger-zone" not in client.get(reverse("entries:create")).text


def _form_tag(body):
    start = body.index('<form method="post" enctype="multipart/form-data"')
    return body[start : body.index(">", start) + 1]


def test_the_entry_form_is_guarded_against_leaving_unsaved(client, nina):
    """unsaved.js asks before anybody leaves a changed form."""
    client.force_login(nina)
    body = client.get(reverse("entries:create")).text
    assert "data-guard-unsaved" in _form_tag(body)
    assert 'data-unsaved="true"' not in _form_tag(body)
    assert 'src="/static/js/unsaved.js" defer' in body


def test_a_form_sent_back_with_errors_counts_as_unsaved(client, nina):
    """What was typed is on the page but not saved anywhere; leaving
    would lose it just as surely as leaving a freshly edited form."""
    client.force_login(nina)
    body = client.post(
        reverse("entries:create"), {"url": "not an address", "notes": "Typed."}
    ).text
    assert 'data-unsaved="true"' in _form_tag(body)


def _following(owner, tag_name, name="Wants"):
    return Collection.objects.create(
        owner=owner,
        name=name,
        kind=Collection.BY_LABEL,
        label=Tag.objects.get(owner=owner, name=tag_name),
    )


def _says_emptied(body, collection):
    return (
        f"“{collection.name}” has nothing in it now." in body
        and reverse("collections:delete", args=[collection.pk]) in body
    )


def test_taking_the_last_label_off_offers_to_delete_its_collection(client, nina):
    entry, _ = save_entry(nina, url="https://example.com/w", tag_names=["want"])
    wants = _following(nina, "want")
    client.force_login(nina)
    response = client.post(
        reverse("entries:edit", args=[entry.pk]),
        {"url": entry.url, "title": "", "notes": "", "tags": ""},
        follow=True,
    )
    assert _says_emptied(response.content.decode(), wants)
    assert Collection.objects.filter(pk=wants.pk).exists()


def test_deleting_the_last_entry_offers_it_too(client, nina):
    entry, _ = save_entry(nina, url="https://example.com/w", tag_names=["want"])
    wants = _following(nina, "want")
    client.force_login(nina)
    response = client.post(reverse("entries:delete", args=[entry.pk]), follow=True)
    assert _says_emptied(response.content.decode(), wants)
    assert Collection.objects.filter(pk=wants.pk).exists()


def _htmx_post(client, url, data=None):
    return client.post(url, data or {}, headers={"HX-Request": "true"})


def test_deleting_with_htmx_does_not_redirect(client, nina):
    """In place: 200 with a fragment, not the usual 302 to `next`."""
    entry, _ = save_entry(nina, url="https://example.com/watch")
    client.force_login(nina)
    response = _htmx_post(client, reverse("entries:delete", args=[entry.pk]))
    assert response.status_code == 200
    assert "Location" not in response
    assert not Entry.objects.filter(pk=entry.pk).exists()


def test_deleting_with_htmx_announces_the_title_out_of_band(client, nina):
    entry, _ = save_entry(nina, url="https://example.com/watch", title="A watch")
    client.force_login(nina)
    body = _htmx_post(client, reverse("entries:delete", args=[entry.pk])).text
    assert 'id="status"' in body
    assert 'hx-swap-oob="true"' in body
    assert "Deleted “A watch”." in body


def test_deleting_the_only_entry_with_htmx_says_nothing_saved_yet(client, nina):
    entry, _ = save_entry(nina, url="https://example.com/watch")
    client.force_login(nina)
    body = _htmx_post(client, reverse("entries:delete", args=[entry.pk])).text
    assert 'id="entries-list"' in body
    assert "Nothing saved yet." in body


def test_deleting_with_entries_still_left_says_nothing_about_the_list(client, nina):
    entry, _ = save_entry(nina, url="https://example.com/watch")
    save_entry(nina, url="https://example.com/kept")
    client.force_login(nina)
    body = _htmx_post(client, reverse("entries:delete", args=[entry.pk])).text
    assert "entries-list" not in body


def test_deleting_the_last_entry_of_a_filtered_label_with_htmx_redirects(client, nina):
    """Pruning the filtered label leaves no fragment to swap, so this is
    a full navigation, same as `still_there` sends the plain path to."""
    entry, _ = save_entry(nina, url="https://example.com/rare", tag_names=["rare"])
    save_entry(nina, url="https://example.com/common", tag_names=["common"])
    client.force_login(nina)
    response = _htmx_post(
        client,
        reverse("entries:delete", args=[entry.pk]),
        {"next": "/entries/?tag=rare"},
    )
    assert response.status_code == 200
    assert response["HX-Redirect"] == reverse("entries:list")
    assert "entries-list" not in response.text


def test_the_page_an_htmx_delete_redirects_to_confirms_the_delete(client, nina):
    """The navigation replaces the page the status would have been
    written to, so the confirmation travels as a message instead."""
    entry, _ = save_entry(
        nina, url="https://example.com/rare", title="Rare", tag_names=["rare"]
    )
    save_entry(nina, url="https://example.com/common", tag_names=["common"])
    client.force_login(nina)
    _htmx_post(
        client,
        reverse("entries:delete", args=[entry.pk]),
        {"next": "/entries/?tag=rare"},
    )
    page = client.get(reverse("entries:list"))
    assert [str(m) for m in page.context["messages"]] == ["Deleted “Rare”."]


def test_deleting_one_of_several_tagged_entries_with_htmx_stays_in_place(client, nina):
    """The label survives this delete, so there is still a page to
    update in place — no redirect."""
    entry, _ = save_entry(nina, url="https://example.com/rare", tag_names=["rare"])
    save_entry(nina, url="https://example.com/also-rare", tag_names=["rare"])
    client.force_login(nina)
    response = _htmx_post(
        client,
        reverse("entries:delete", args=[entry.pk]),
        {"next": "/entries/?tag=rare"},
    )
    assert response.status_code == 200
    assert "HX-Redirect" not in response
    assert "entries-list" not in response.text


def test_deleting_with_htmx_swaps_the_emptied_collection_notice_in(client, nina):
    """The link has nowhere sensible to live but the messages list, so
    it is drained from the queue and shown now, not left for later."""
    entry, _ = save_entry(nina, url="https://example.com/w", tag_names=["want"])
    wants = _following(nina, "want")
    client.force_login(nina)
    response = _htmx_post(client, reverse("entries:delete", args=[entry.pk]))
    body = response.text
    assert 'id="messages"' in body
    assert "has nothing in it now" in body
    assert reverse("collections:delete", args=[wants.pk]) in body
    # And the status text, link-free, says so briefly too.
    assert "nothing in it" in body.split('id="status"')[1].split("</div>")[0]

    # Nothing left queued for the next page to show again.
    later = client.get(reverse("entries:list"))
    assert "has nothing in it now" not in later.content.decode()


def test_deleting_with_htmx_refreshes_a_pruned_tags_sidebar(client, nina):
    """A secondary label this delete empties is gone from the owner's
    tags too; the sidebar on screen must stop offering it."""
    entry, _ = save_entry(
        nina, url="https://example.com/both", tag_names=["kept", "rare"]
    )
    save_entry(nina, url="https://example.com/other", tag_names=["kept"])
    client.force_login(nina)
    body = _htmx_post(
        client,
        reverse("entries:delete", args=[entry.pk]),
        {"next": "/entries/?tag=kept"},
    ).text
    assert 'id="tags-sidebar"' in body
    assert 'href="?tag=kept"' in body
    assert "rare" not in body


def test_deleting_with_htmx_leaves_an_unrelated_tags_sidebar_alone(client, nina):
    entry, _ = save_entry(nina, url="https://example.com/a", tag_names=["kept"])
    save_entry(nina, url="https://example.com/b", tag_names=["kept"])
    client.force_login(nina)
    body = _htmx_post(client, reverse("entries:delete", args=[entry.pk])).text
    assert "tags-sidebar" not in body


def test_re_saving_by_address_on_the_new_form_offers_it_too(client, nina):
    save_entry(nina, url="https://example.com/w", tag_names=["want"])
    wants = _following(nina, "want")
    client.force_login(nina)
    response = client.post(
        reverse("entries:create"),
        {"url": "https://example.com/w", "title": "", "notes": "", "tags": ""},
        follow=True,
    )
    assert _says_emptied(response.content.decode(), wants)


def test_a_label_still_carried_elsewhere_says_nothing(client, nina):
    entry, _ = save_entry(nina, url="https://example.com/w", tag_names=["want"])
    save_entry(nina, url="https://example.com/other", tag_names=["want"])
    _following(nina, "want")
    client.force_login(nina)
    response = client.post(
        reverse("entries:edit", args=[entry.pk]),
        {"url": entry.url, "title": "", "notes": "", "tags": ""},
        follow=True,
    )
    assert "has nothing in it now" not in response.content.decode()


def test_a_collection_already_empty_is_not_mentioned_again(client, nina):
    save_entry(nina, url="https://example.com/w", tag_names=["want"])
    entry, _ = save_entry(nina, url="https://example.com/x", tag_names=["other"])
    wants = _following(nina, "want")
    Entry.objects.get(url="https://example.com/w").delete()
    client.force_login(nina)
    response = client.post(
        reverse("entries:edit", args=[entry.pk]),
        {"url": entry.url, "title": "", "notes": "", "tags": "other"},
        follow=True,
    )
    assert f"“{wants.name}”" not in response.content.decode()


def test_the_collection_name_is_escaped_in_the_notice(client, nina):
    entry, _ = save_entry(nina, url="https://example.com/w", tag_names=["want"])
    _following(nina, "want", name="<b>Wants</b>")
    client.force_login(nina)
    body = client.post(
        reverse("entries:edit", args=[entry.pk]),
        {"url": entry.url, "title": "", "notes": "", "tags": ""},
        follow=True,
    ).content.decode()
    assert "&lt;b&gt;Wants&lt;/b&gt;" in body
    assert "<b>Wants</b>" not in body


def test_saved_comes_before_the_emptied_notice(client, nina):
    entry, _ = save_entry(nina, url="https://example.com/w", tag_names=["want"])
    _following(nina, "want")
    client.force_login(nina)
    body = client.post(
        reverse("entries:edit", args=[entry.pk]),
        {"url": entry.url, "title": "", "notes": "", "tags": ""},
        follow=True,
    ).content.decode()
    assert body.index("Saved.") < body.index("has nothing in it now")


def _label_wish_list(owner, tag_name="want"):
    tag, _ = Tag.objects.get_or_create(owner=owner, name=tag_name)
    return Collection.objects.create(
        owner=owner,
        name="Wants",
        kind=Collection.BY_LABEL,
        label=tag,
        visibility=Collection.UNLISTED,
        is_wish_list=True,
    )


def _got(wishes, entry):
    GotIt.objects.create(
        collection=wishes, entry=entry, got_by=_person("ana@example.com")
    )


def _says_already_got(body, wishes, entry):
    return (
        "Somebody has already got this for “Wants”." in body
        and f"/collections/{wishes.pk}/?back={entry.pk}" in body
    )


def test_relabelling_an_item_already_got_says_so(client, nina):
    entry, _ = save_entry(nina, url="https://example.com/w", tag_names=["want"])
    wishes = _label_wish_list(nina)
    _got(wishes, entry)
    save_entry(nina, url="https://example.com/keep", tag_names=["want"])
    entry.tags.clear()
    client.force_login(nina)
    body = client.post(
        reverse("entries:edit", args=[entry.pk]),
        {"url": entry.url, "title": "", "notes": "", "tags": "want"},
        follow=True,
    ).content.decode()
    assert _says_already_got(body, wishes, entry)
    assert "ana@example.com" not in body


def test_saving_an_item_that_stays_on_the_list_says_nothing(client, nina):
    entry, _ = save_entry(nina, url="https://example.com/w", tag_names=["want"])
    wishes = _label_wish_list(nina)
    _got(wishes, entry)
    client.force_login(nina)
    body = client.post(
        reverse("entries:edit", args=[entry.pk]),
        {"url": entry.url, "title": "Renamed", "notes": "", "tags": "want"},
        follow=True,
    ).content.decode()
    assert "already got" not in body


def test_re_adding_by_address_on_the_new_form_says_so_too(client, nina):
    entry, _ = save_entry(nina, url="https://example.com/w", tag_names=["want"])
    wishes = _label_wish_list(nina)
    _got(wishes, entry)
    save_entry(nina, url="https://example.com/w", tag_names=[])
    client.force_login(nina)
    body = client.post(
        reverse("entries:create"),
        {"url": "https://example.com/w", "title": "", "notes": "", "tags": "want"},
        follow=True,
    ).content.decode()
    assert _says_already_got(body, wishes, entry)
