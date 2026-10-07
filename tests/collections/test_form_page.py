"""The make/edit collection form: the "Show" group of checkboxes."""

from html.parser import HTMLParser

import pytest
from django.urls import reverse
from django.utils import timezone

from hrcek.accounts.models import User
from hrcek.collections.models import Collection
from hrcek.entries.models import FieldDefinition

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


class _ShowGroup(HTMLParser):
    """Structural facts about the "Show" fieldset and its checkboxes.

    Built on the open-element stack, like the other template tests, so
    assertions are about where things sit rather than string order.
    """

    def __init__(self) -> None:
        super().__init__()
        self.stack: list[str] = []
        self.fieldset_attrs: dict[str, str] = {}
        self.in_show = False
        self.show_depth: int | None = None
        self.checkboxes: list[dict[str, str]] = []
        self.label_text: dict[str, str] = {}
        self._current_label_id: str | None = None
        self.helptexts: list[dict[str, str]] = []
        self._current_helptext_id: str | None = None
        self.error_ids: list[str] = []
        # One entry per checkbox or helptext, in document order, so
        # relative position inside the fieldset can be checked.
        self.order: list[tuple[str, str]] = []

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        self.stack.append(tag)
        if tag == "fieldset" and attrs_dict.get("class") == "show":
            self.in_show = True
            self.show_depth = len(self.stack)
            self.fieldset_attrs = attrs_dict
        if not self.in_show:
            return
        if tag == "input" and attrs_dict.get("type") == "checkbox":
            self.checkboxes.append(attrs_dict)
            self.order.append(("checkbox", attrs_dict.get("id", "")))
        if tag == "label":
            self._current_label_id = attrs_dict.get("for", "")
        if tag == "p" and attrs_dict.get("class") == "helptext":
            self._current_helptext_id = attrs_dict.get("id", "")
            self.helptexts.append(attrs_dict)
            self.order.append(("helptext", attrs_dict.get("id", "")))
        if tag == "ul" and "errorlist" in attrs_dict.get("class", "").split():
            error_id = attrs_dict.get("id", "")
            if error_id:
                self.error_ids.append(error_id)

    def handle_data(self, data):
        if self._current_label_id is not None:
            self.label_text[self._current_label_id] = (
                self.label_text.get(self._current_label_id, "") + data
            )

    def handle_endtag(self, tag):
        if tag == "label":
            self._current_label_id = None
        if tag == "p":
            self._current_helptext_id = None
        if self.stack and tag in self.stack:
            while self.stack and self.stack.pop() != tag:
                pass
        if (
            self.in_show
            and self.show_depth is not None
            and len(self.stack) < self.show_depth
        ):
            self.in_show = False


def _show_group(html: str) -> _ShowGroup:
    parser = _ShowGroup()
    parser.feed(html)
    return parser


def test_there_is_no_multiple_select(signed_in):
    page = signed_in.get(reverse("collections:create"))
    html = page.content.decode()
    assert "<select multiple" not in html
    assert '<select name="visible_fields"' not in html


def test_each_field_is_a_checkbox_in_the_show_group(signed_in, nina):
    FieldDefinition.objects.create(owner=nina, name="Price")
    FieldDefinition.objects.create(owner=nina, name="Condition")
    page = signed_in.get(reverse("collections:create"))
    group = _show_group(page.content.decode())
    # show_notes, show_images, show_tags, the seeded "Priority", plus
    # one per FieldDefinition created above.
    assert len(group.checkboxes) == 3 + 1 + 2


def test_checkbox_labels_have_no_colon(signed_in, nina):
    FieldDefinition.objects.create(owner=nina, name="Price")
    page = signed_in.get(reverse("collections:create"))
    html = page.content.decode()
    group = _show_group(html)
    texts = [text.strip() for text in group.label_text.values()]
    for expected in ("Notes", "Pictures", "Labels"):
        assert expected in texts, texts
    for text in texts:
        assert ":" not in text, text
    # Wish list sits outside the fieldset, so it is checked on the
    # whole page rather than inside the show group.
    assert "Wish list</label>" in html
    assert "Wish list:</label>" not in html


def test_the_show_help_follows_the_group_not_notes(signed_in):
    page = signed_in.get(reverse("collections:create"))
    html = page.content.decode()
    group = _show_group(html)
    assert group.order, "no checkboxes or helptexts found in the show group"
    # The group help text is the very last thing in the fieldset, after
    # every checkbox - in particular, after Pictures' own help, which
    # sits right under the Pictures checkbox and not at the end.
    assert group.order[-1][0] == "helptext"
    group_help_id = group.order[-1][1]
    assert "Anything you leave unticked stays private" in html
    other_helptext_ids = [
        helptext_id for kind, helptext_id in group.order[:-1] if kind == "helptext"
    ]
    assert group_help_id not in other_helptext_ids


def test_the_pictures_help_sits_under_pictures_and_is_tied_to_it(signed_in):
    page = signed_in.get(reverse("collections:create"))
    html = page.content.decode()
    group = _show_group(html)
    pictures_id = next(
        label_for
        for label_for, text in group.label_text.items()
        if text.strip() == "Pictures"
    )
    checkbox = next(cb for cb in group.checkboxes if cb.get("id") == pictures_id)
    described_by = checkbox.get("aria-describedby", "").split()
    assert described_by
    helptext_ids = [h.get("id") for h in group.helptexts]
    assert set(described_by) & set(helptext_ids)


def test_the_group_help_is_tied_to_the_fieldset(signed_in):
    page = signed_in.get(reverse("collections:create"))
    group = _show_group(page.content.decode())
    described_by = group.fieldset_attrs.get("aria-describedby", "").split()
    assert described_by
    helptext_ids = [h.get("id") for h in group.helptexts]
    assert set(described_by) & set(helptext_ids)


def test_every_option_saves(signed_in, nina):
    price = FieldDefinition.objects.create(owner=nina, name="Price")
    response = signed_in.post(
        reverse("collections:create"),
        {
            "name": "Watches",
            "description": "",
            "kind": Collection.MANUAL,
            "show_notes": "on",
            "show_images": "on",
            "show_tags": "on",
            "visible_fields": [price.pk],
        },
        follow=True,
    )
    assert response.status_code == 200
    collection = Collection.objects.get(owner=nina, name="Watches")
    assert collection.show_notes
    assert collection.show_images
    assert collection.show_tags
    assert list(collection.visible_fields.all()) == [price]


def test_a_bad_visible_field_choice_is_shown_inside_the_group(signed_in):
    response = signed_in.post(
        reverse("collections:create"),
        {
            "name": "Watches",
            "description": "",
            "kind": Collection.MANUAL,
            "visible_fields": ["999999"],
        },
    )
    assert response.status_code == 200
    html = response.content.decode()
    group = _show_group(html)
    assert group.error_ids, "no error shown inside the show group"
    described_by = group.fieldset_attrs.get("aria-describedby", "").split()
    assert set(described_by) & set(group.error_ids)


class _DangerZone(HTMLParser):
    """Whether the delete link sits inside section.danger-zone."""

    def __init__(self) -> None:
        super().__init__()
        self.stack: list[str] = []
        self.danger_zone_depth: int | None = None
        self.delete_in_danger_zone = False

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        self.stack.append(tag)
        if tag == "section" and attrs_dict.get("class") == "danger-zone":
            self.danger_zone_depth = len(self.stack)
        if (
            tag == "a"
            and "delete" in attrs_dict.get("href", "")
            and self.danger_zone_depth is not None
        ):
            self.delete_in_danger_zone = True

    def handle_endtag(self, tag):
        if self.stack and tag in self.stack:
            while self.stack and self.stack.pop() != tag:
                pass
        if (
            self.danger_zone_depth is not None
            and len(self.stack) < self.danger_zone_depth
        ):
            self.danger_zone_depth = None


def test_delete_is_in_a_danger_zone_and_back_opens_a_new_tab(signed_in, nina):
    collection = Collection.objects.create(owner=nina, name="Watches")
    page = signed_in.get(reverse("collections:edit", args=[collection.pk]))
    html = page.content.decode()

    parser = _DangerZone()
    parser.feed(html)
    assert parser.delete_in_danger_zone

    detail_url = reverse("collections:detail", args=[collection.pk])
    assert f'href="{detail_url}" target="_blank" rel="noopener"' in html


def test_back_from_the_create_form_opens_a_new_tab(signed_in):
    """Whatever has been typed into the new collection stays put."""
    html = signed_in.get(reverse("collections:create")).content.decode()

    list_url = reverse("collections:list")
    assert f'href="{list_url}" target="_blank" rel="noopener"' in html
