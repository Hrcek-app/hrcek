from decimal import Decimal

import pytest
from django.db.utils import IntegrityError
from django.utils import timezone

from hrcek.accounts.models import User
from hrcek.entries.models import Entry, FieldDefinition, FieldValue
from hrcek.entries.signals import seed_default_fields

pytestmark = pytest.mark.django_db

PASSWORD = "a-long-enough-passphrase"


def _person(email):
    return User.objects.create_user(
        email=email, password=PASSWORD, email_verified_at=timezone.now()
    )


@pytest.fixture
def nina():
    return _person("nina@example.com")


def test_a_new_account_gets_priority_and_nothing_else(nina):
    """Price was seeded here once and is not any more: a price without
    a currency says too little, and a currency needs a field type this
    project does not have."""
    fields = {f.name: f for f in FieldDefinition.objects.filter(owner=nina)}
    assert sorted(fields) == ["Priority"]
    assert fields["Priority"].kind == FieldDefinition.CHOICE
    assert fields["Priority"].options == ["high", "medium", "low"]


def test_seeded_fields_are_ordinary_rows(nina):
    priority = FieldDefinition.objects.get(owner=nina, name="Priority")
    priority.name = "Urgency"
    priority.save()
    priority.delete()
    assert not FieldDefinition.objects.filter(owner=nina, name="Urgency").exists()


def test_seeding_twice_does_not_duplicate(nina):
    seed_default_fields(nina)
    assert FieldDefinition.objects.filter(owner=nina).count() == 1


def test_fields_belong_to_their_owner(nina):
    _person("marko@example.com")
    assert FieldDefinition.objects.filter(owner=nina).count() == 1
    assert FieldDefinition.objects.count() == 2


def test_a_name_is_unique_per_owner_ignoring_case(nina):
    with pytest.raises(IntegrityError):
        FieldDefinition.objects.create(owner=nina, name="priority")


def test_two_people_may_use_the_same_field_name(nina):
    _person("marko@example.com")
    assert FieldDefinition.objects.filter(name="Priority").count() == 2


def test_a_text_value_round_trips(nina):
    entry = Entry.objects.create(owner=nina, url="https://example.com/1")
    definition = FieldDefinition.objects.create(owner=nina, name="Seller")
    value = FieldValue(entry=entry, definition=definition)
    value.value = "Watches Ltd"
    value.save()
    assert FieldValue.objects.get(pk=value.pk).value == "Watches Ltd"


def test_a_number_value_round_trips(nina):
    entry = Entry.objects.create(owner=nina, url="https://example.com/1")
    price = FieldDefinition.objects.create(
        owner=nina, name="Cost", kind=FieldDefinition.NUMBER
    )
    value = FieldValue(entry=entry, definition=price)
    value.value = "129.00"
    value.save()
    stored = FieldValue.objects.get(pk=value.pk)
    assert stored.value_number == Decimal("129.00")
    assert stored.value == "129"


@pytest.mark.parametrize(
    ("given", "shown"),
    [
        ("129.00", "129"),
        ("38.50", "38.5"),
        ("0", "0"),
        ("1000", "1000"),
        ("0.000001", "0.000001"),
    ],
)
def test_numbers_render_without_trailing_zeros(given, shown):
    assert FieldValue.format_number(Decimal(given)) == shown


def test_an_entry_may_have_no_value_for_a_field(nina):
    entry = Entry.objects.create(owner=nina, url="https://example.com/1")
    assert FieldValue.objects.filter(entry=entry).count() == 0


def test_one_value_per_field_per_entry(nina):
    entry = Entry.objects.create(owner=nina, url="https://example.com/1")
    price = FieldDefinition.objects.create(
        owner=nina, name="Cost", kind=FieldDefinition.NUMBER
    )
    FieldValue.objects.create(entry=entry, definition=price, value_number=1)
    with pytest.raises(IntegrityError):
        FieldValue.objects.create(entry=entry, definition=price, value_number=2)


def test_deleting_a_definition_removes_its_values(nina):
    entry = Entry.objects.create(owner=nina, url="https://example.com/1")
    price = FieldDefinition.objects.create(
        owner=nina, name="Cost", kind=FieldDefinition.NUMBER
    )
    FieldValue.objects.create(entry=entry, definition=price, value_number=1)
    price.delete()
    assert FieldValue.objects.filter(entry=entry).count() == 0


def test_deleting_an_entry_removes_its_values(nina):
    entry = Entry.objects.create(owner=nina, url="https://example.com/1")
    price = FieldDefinition.objects.create(
        owner=nina, name="Cost", kind=FieldDefinition.NUMBER
    )
    FieldValue.objects.create(entry=entry, definition=price, value_number=1)
    entry.delete()
    assert FieldValue.objects.count() == 0


def test_every_kind_is_offered_for_new_fields():
    assert FieldDefinition.CREATABLE_KINDS == (
        FieldDefinition.TEXT,
        FieldDefinition.NUMBER,
        FieldDefinition.CHOICE,
    )
