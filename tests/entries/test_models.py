import pytest
from django.db.utils import IntegrityError
from django.utils import timezone

from hrcek.accounts.models import User
from hrcek.collections.models import Collection
from hrcek.entries.models import Entry, Tag

pytestmark = pytest.mark.django_db

PASSWORD = "a-long-enough-passphrase"


def _person(email):
    return User.objects.create_user(
        email=email, password=PASSWORD, email_verified_at=timezone.now()
    )


@pytest.fixture
def nina():
    return _person("nina@example.com")


@pytest.fixture
def marko():
    return _person("marko@example.com")


def test_an_entry_needs_only_an_owner_and_a_url(nina):
    entry = Entry.objects.create(owner=nina, url="https://example.com/watch")
    assert entry.title == ""
    assert entry.notes == ""
    assert entry.created_at is not None


def test_the_title_falls_back_to_the_url(nina):
    entry = Entry.objects.create(owner=nina, url="https://example.com/watch")
    assert entry.display_title == "https://example.com/watch"
    entry.title = "A watch"
    assert entry.display_title == "A watch"


def test_one_person_cannot_hold_the_same_url_twice(nina):
    Entry.objects.create(owner=nina, url="https://example.com/watch")
    with pytest.raises(IntegrityError):
        Entry.objects.create(owner=nina, url="https://example.com/watch")


def test_two_people_may_hold_the_same_url(nina, marko):
    Entry.objects.create(owner=nina, url="https://example.com/watch")
    Entry.objects.create(owner=marko, url="https://example.com/watch")
    assert Entry.objects.count() == 2


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("  https://Example.COM/Watch  ", "https://example.com/Watch"),
        ("HTTPS://example.com/Watch", "https://example.com/Watch"),
        ("https://example.com/Watch", "https://example.com/Watch"),
    ],
)
def test_url_normalisation_touches_only_scheme_host_and_whitespace(raw, expected):
    assert Entry.normalise_url(raw) == expected


def test_normalisation_leaves_different_pages_different():
    # The failure mode of over-normalising is silently merging two pages.
    assert Entry.normalise_url("https://example.com/a") != Entry.normalise_url(
        "https://example.com/b"
    )
    assert Entry.normalise_url("https://example.com/a/") != Entry.normalise_url(
        "https://example.com/a"
    )


def test_newest_entries_come_first(nina):
    first = Entry.objects.create(owner=nina, url="https://example.com/1")
    second = Entry.objects.create(owner=nina, url="https://example.com/2")
    assert list(Entry.objects.all()) == [second, first]


def test_entries_created_in_the_same_instant_still_order_stably(nina):
    moment = timezone.now()
    first = Entry.objects.create(owner=nina, url="https://example.com/1")
    second = Entry.objects.create(owner=nina, url="https://example.com/2")
    Entry.objects.update(created_at=moment)
    # Without the -pk tiebreaker, pagination can repeat or skip a row.
    assert list(Entry.objects.all()) == [second, first]


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("watches, diving ,  ", ["watches", "diving"]),
        ("watches,Watches,WATCHES", ["watches"]),
        ("", []),
        ("   ", []),
    ],
)
def test_tag_names_are_parsed_trimmed_and_deduplicated(raw, expected):
    assert Tag.parse_names(raw) == expected


def test_tags_belong_to_their_owner(nina, marko):
    Tag.objects.create(owner=nina, name="watches")
    Tag.objects.create(owner=marko, name="watches")
    assert Tag.objects.count() == 2


def test_one_person_cannot_hold_the_same_tag_twice_in_any_casing(nina):
    Tag.objects.create(owner=nina, name="Watches")
    with pytest.raises(IntegrityError):
        Tag.objects.create(owner=nina, name="watches")


def test_setting_tags_creates_them_on_demand(nina):
    entry = Entry.objects.create(owner=nina, url="https://example.com/watch")
    Tag.set_for(entry, ["watches", "diving"])
    assert sorted(t.name for t in entry.tags.all()) == ["diving", "watches"]


def test_setting_tags_reuses_an_existing_one_whatever_its_casing(nina):
    existing = Tag.objects.create(owner=nina, name="Watches")
    entry = Entry.objects.create(owner=nina, url="https://example.com/watch")
    Tag.set_for(entry, ["watches"])
    assert list(entry.tags.all()) == [existing]


def test_a_tag_left_with_no_entries_is_removed(nina):
    entry = Entry.objects.create(owner=nina, url="https://example.com/watch")
    Tag.set_for(entry, ["watches", "diving"])
    Tag.set_for(entry, ["watches"])
    assert [t.name for t in Tag.objects.filter(owner=nina)] == ["watches"]


def test_pruning_leaves_another_persons_tags_alone(nina, marko):
    theirs = Tag.objects.create(owner=marko, name="watches")
    Tag.prune_orphans(nina)
    assert Tag.objects.filter(pk=theirs.pk).exists()


def _follow(owner, tag, name="Wants"):
    return Collection.objects.create(
        owner=owner, name=name, kind=Collection.BY_LABEL, label=tag
    )


def test_a_label_a_collection_follows_outlives_its_last_entry(nina):
    entry = Entry.objects.create(owner=nina, url="https://example.com/watch")
    Tag.set_for(entry, ["want"])
    collection = _follow(nina, Tag.objects.get(owner=nina, name="want"))
    Tag.set_for(entry, [])
    assert Collection.objects.filter(pk=collection.pk).exists()
    assert Tag.objects.filter(owner=nina, name="want").exists()


def test_labelling_again_refills_the_kept_collection(nina):
    entry = Entry.objects.create(owner=nina, url="https://example.com/watch")
    Tag.set_for(entry, ["want"])
    collection = _follow(nina, Tag.objects.get(owner=nina, name="want"))
    Tag.set_for(entry, [])
    Tag.set_for(entry, ["Want"])
    assert list(collection.entries()) == [entry]


def test_only_labels_on_an_entry_are_in_use(nina):
    entry = Entry.objects.create(owner=nina, url="https://example.com/watch")
    Tag.set_for(entry, ["watches"])
    _follow(nina, Tag.objects.create(owner=nina, name="kept"))
    assert [t.name for t in Tag.in_use(nina)] == ["watches"]
