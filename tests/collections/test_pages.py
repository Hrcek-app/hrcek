import pytest
from django.urls import NoReverseMatch, reverse
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


def test_an_entry_can_be_removed(signed_in, nina):
    collection = Collection.objects.create(owner=nina, name="Watches")
    entry = Entry.objects.create(owner=nina, url="https://example.com/1")
    CollectionEntry.objects.create(collection=collection, entry=entry)

    signed_in.post(reverse("collections:remove_entry", args=[collection.pk, entry.pk]))
    assert collection.entries().count() == 0


def test_a_collection_page_has_no_add_form(signed_in, nina):
    """Entries join a manual collection from the entry's own edit page
    now, not from here, so the collection page offers no form for it."""
    collection = Collection.objects.create(owner=nina, name="Watches")
    body = signed_in.get(reverse("collections:detail", args=[collection.pk])).text
    assert "<select" not in body
    assert "Add an entry" not in body


def test_the_add_entry_address_is_gone(signed_in, nina):
    collection = Collection.objects.create(owner=nina, name="Watches")
    with pytest.raises(NoReverseMatch):
        reverse("collections:add_entry", args=[collection.pk])


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


def test_the_page_offers_edit_but_not_your_collections(signed_in, nina):
    """Edit sits by the heading now; the old link row naming "Your
    collections" (reachable already from the header nav) is gone."""
    collection = Collection.objects.create(owner=nina, name="Watches")
    body = signed_in.get(reverse("collections:detail", args=[collection.pk])).text
    assert reverse("collections:edit", args=[collection.pk]) in body
    assert "Your collections" not in body


def test_the_heading_holds_only_the_name_and_edit_sits_beside_it(signed_in, nina):
    """The page's one <h1> must read as the collection's name alone —
    a link inside it would join "Edit" to the heading's accessible
    name. Edit is a sibling of the h1 instead, inside the heading
    row base.html wraps both of them in."""
    collection = Collection.objects.create(owner=nina, name="Watches")
    body = signed_in.get(reverse("collections:detail", args=[collection.pk])).text

    h1_start = body.index("<h1")
    h1_open_end = body.index(">", h1_start) + 1
    h1_close = body.index("</h1>", h1_open_end)
    h1_text = body[h1_open_end:h1_close]
    assert h1_text.strip() == "Watches"
    assert "<a" not in h1_text

    heading_row_start = body.rindex("<div", 0, h1_start)
    heading_row_open_end = body.index(">", heading_row_start) + 1
    assert "heading-row" in body[heading_row_start:heading_row_open_end]
    heading_row_close = body.index("</div>", h1_close)
    aside = body[h1_close + len("</h1>") : heading_row_close]
    assert reverse("collections:edit", args=[collection.pk]) in aside


@pytest.mark.parametrize(
    "visibility",
    [Collection.PRIVATE, Collection.UNLISTED, Collection.PUBLIC],
)
def test_the_feed_is_offered_with_the_address(signed_in, nina, visibility):
    """Whichever feed matches the collection's visibility is offered
    inside the same paragraph as the visibility sentence — the owner's
    own feed for a private collection, the shared one otherwise."""
    nina.namespace = "nina"
    nina.save()
    collection = Collection.objects.create(
        owner=nina, name="Watches", visibility=visibility
    )
    if visibility == Collection.PRIVATE:
        feed_url = reverse("collections:feed", args=[collection.pk])
    elif visibility == Collection.UNLISTED:
        feed_url = reverse("shared:unlisted_feed", kwargs={"secret": collection.secret})
    else:
        feed_url = reverse(
            "shared:public_feed",
            kwargs={"namespace": "nina", "slug": collection.slug},
        )

    body = signed_in.get(reverse("collections:detail", args=[collection.pk])).text
    # Only the <main> content, not the <head>'s own alternate link,
    # which points at the same address.
    main = body[body.index("<main") :]
    start = main.rindex("<p", 0, main.index(feed_url))
    end = main.index("</p>", start)
    paragraph = main[start:end]
    assert feed_url in paragraph
    assert 'class="meta"' in paragraph, (
        "the visibility sentence is explanatory text, not content"
    )
    if visibility == Collection.PRIVATE:
        assert "Private." in paragraph
    elif visibility == Collection.UNLISTED:
        assert "Anyone with this link" in paragraph
    else:
        assert "Public." in paragraph

    # The Atom <link> in <head> points at the same address.
    head = body[: body.index("<main")]
    assert feed_url in head


def test_the_description_is_a_distinct_content_block(signed_in, nina):
    """The description is somebody's own writing, not interface text:
    larger, in full ink, set in its own component class."""
    collection = Collection.objects.create(
        owner=nina, name="Watches", description="Found on a walk."
    )
    body = signed_in.get(reverse("collections:detail", args=[collection.pk])).text
    assert '<p class="content-lead">Found on a walk.</p>' in body


def test_a_collection_with_no_description_has_no_content_lead(signed_in, nina):
    collection = Collection.objects.create(owner=nina, name="Watches")
    body = signed_in.get(reverse("collections:detail", args=[collection.pk])).text
    assert "content-lead" not in body


def test_how_a_manual_collection_fills_is_explanatory_text(signed_in, nina):
    collection = Collection.objects.create(owner=nina, name="Watches")
    body = signed_in.get(reverse("collections:detail", args=[collection.pk])).text
    sentence = "Tick this collection on an entry's own edit page to put it here."
    start = body.rindex("<p", 0, body.index(sentence))
    end = body.index("</p>", start)
    assert 'class="meta"' in body[start:end]


def test_how_a_label_collection_fills_is_explanatory_text(signed_in, nina):
    tag = Tag.objects.create(owner=nina, name="watches")
    collection = Collection.objects.create(
        owner=nina, name="Watches", kind=Collection.BY_LABEL, label=tag
    )
    body = signed_in.get(reverse("collections:detail", args=[collection.pk])).text
    start = body.rindex("<p", 0, body.index("This collection holds every entry"))
    end = body.index("</p>", start)
    assert 'class="meta"' in body[start:end]


def test_the_wish_list_line_holds_only_wish_list_controls(signed_in, nina):
    """The wish-list row (its tag, and show/hide) is the only ul.row
    left on the page — Edit and the feed moved elsewhere."""
    collection = Collection.objects.create(owner=nina, name="Books", is_wish_list=True)
    body = signed_in.get(reverse("collections:detail", args=[collection.pk])).text
    start = body.index('<ul class="row">')
    end = body.index("</ul>", start)
    row = body[start:end]
    assert "Wish list" in row
    assert "Show what has been got" in row
    assert "Edit" not in row
    assert "feed" not in row.lower()
    # And it is the only such row on this (entry-less) page.
    assert body.count('<ul class="row">') == 1


def test_make_a_collection_is_a_button_link_apart_from_the_list(signed_in, nina):
    Collection.objects.create(owner=nina, name="Watches")
    body = signed_in.get(reverse("collections:list")).text
    button_html = f'<a class="button" href="{reverse("collections:create")}">'
    assert button_html in body
    assert body.index(button_html) < body.index('<ul class="stacked">')


def test_each_collection_shows_kind_and_visibility(signed_in, nina):
    Collection.objects.create(
        owner=nina,
        name="Watches",
        kind=Collection.MANUAL,
        visibility=Collection.PUBLIC,
    )
    body = signed_in.get(reverse("collections:list")).text
    assert '<p class="meta">Chosen by hand · Public</p>' in body, (
        "kind and visibility are explanatory text, not content"
    )


def test_a_collections_description_on_the_list_is_a_content_block(signed_in, nina):
    Collection.objects.create(
        owner=nina, name="Watches", description="Found on a walk."
    )
    body = signed_in.get(reverse("collections:list")).text
    assert '<p class="content-lead">Found on a walk.</p>' in body


def test_a_collection_entrys_text_is_kept_together(signed_in, nina):
    """An entry lays out as its text beside an optional picture, so
    everything but the picture must sit inside the text block, or the
    title, notes and tags end up side by side."""
    entry = Entry.objects.create(
        owner=nina, url="https://example.com/w", notes="Some notes."
    )
    Tag.set_for(entry, ["watches"])
    collection = Collection.objects.create(owner=nina, name="Mine", kind="manual")
    CollectionEntry.objects.create(collection=collection, entry=entry)
    body = signed_in.get(reverse("collections:detail", args=[collection.pk])).text
    article = body[body.index("<article>") : body.index("</article>")]
    assert article.split(">", 1)[1].lstrip().startswith('<div class="entry-text">')
    assert article.rstrip().endswith("</div>")
