import pytest
from django.urls import reverse
from django.utils import timezone

from hrcek.accounts.models import User
from hrcek.collections.models import Collection
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
