from __future__ import annotations

from typing import Any, ClassVar

from django import forms
from django.utils.translation import gettext_lazy as _

from hrcek.accounts.models import User
from hrcek.collections.models import Collection
from hrcek.entries.models import FieldDefinition, Tag


class CollectionForm(forms.ModelForm):
    class Meta:
        model = Collection
        fields = (
            "name",
            "description",
            "kind",
            "label",
            "visibility",
            "is_wish_list",
            "show_notes",
            "show_tags",
            "show_images",
            "visible_fields",
        )
        help_texts: ClassVar[dict[str, Any]] = {
            "description": _(
                "Optional. Anyone who can see this collection sees its description too."
            ),
            "kind": _(
                "Choose entries by hand, or let the collection hold "
                "everything carrying one label. This cannot be changed "
                "afterwards."
            ),
            "label": _("Only needed for a collection that follows a label."),
            # The request asked for this to be unmistakable, so each
            # choice states its consequence rather than naming itself.
            "visibility": _(
                "Private — only you can see this collection. There is no "
                "address to share. "
                "Anyone with the link — anyone who has the link can see "
                "this collection and everything you have chosen to show. "
                "The link is hard to guess, but it is not a password: "
                "whoever you send it to can pass it on. "
                "Public — anyone can see this collection, and it can be "
                "found by search engines. Its address contains your "
                "public name."
            ),
            "is_wish_list": _(
                "People you share this with can say “Got it” for "
                "anything they have got you. It then disappears for "
                "everybody else, and you keep seeing the whole list, so "
                "you are still surprised."
            ),
            "show_notes": _(
                "Shown to everyone who can see the page. Anything you "
                "leave unticked stays private."
            ),
            "show_images": _(
                "A picture you show here can be opened by anyone who can "
                "see this page, even outside it."
            ),
            "visible_fields": _(
                "Only the fields you tick are shown. The address and the "
                "title of each entry are always shown."
            ),
        }

    def __init__(self, owner: User, *args: Any, **kwargs: Any) -> None:
        self.owner = owner
        super().__init__(*args, **kwargs)
        # Only this person's labels, so somebody else's tag cannot be
        # named by submitting its id.
        self.fields["label"].queryset = Tag.objects.filter(  # ty: ignore[unresolved-attribute]
            owner=owner
        )
        self.fields["label"].required = False
        # The picker is only of use to a collection that follows a
        # label. These mark the two inputs so the page can reveal it
        # when one is chosen; the value is the kind that needs it, so
        # no script has to hardcode the constant.
        self.fields["kind"].widget.attrs["data-kind-select"] = ""
        self.fields["label"].widget.attrs["data-label-field"] = Collection.BY_LABEL
        self.fields["visible_fields"].queryset = (  # ty: ignore[unresolved-attribute]
            FieldDefinition.objects.filter(owner=owner)
        )
        # Not required, and absent means private: a submission that
        # somehow omits it must never publish anything by accident.
        self.fields["visibility"].required = False
        if self.instance.pk:
            # Fixed once the collection exists: switching would either
            # discard what was chosen by hand or swallow a label's
            # entries whole. Deleting and making another is honest.
            del self.fields["kind"]
            del self.fields["label"]

    def clean(self) -> dict[str, Any]:
        cleaned = super().clean() or {}
        if not cleaned.get("visibility"):
            cleaned["visibility"] = Collection.PRIVATE
        if cleaned.get("visibility") == Collection.PUBLIC and not self.owner.namespace:
            # A public address needs a public name to put in it.
            self.add_error(
                "visibility",
                _(
                    "Choose a public name on your account page before "
                    "making a collection public."
                ),
            )
        if "kind" not in self.fields:
            return cleaned
        if cleaned.get("kind") == Collection.BY_LABEL and not cleaned.get("label"):
            self.add_error("label", _("Choose the label this collection follows."))
        if cleaned.get("kind") == Collection.MANUAL and cleaned.get("label"):
            # Not silently dropped: the picker is hidden for a manual
            # collection, so a label arriving here means the two halves
            # of the submission disagree, and saying so beats accepting
            # it and discarding one of them.
            self.add_error(
                "label",
                _("A collection chosen by hand does not follow a label."),
            )
        return cleaned
