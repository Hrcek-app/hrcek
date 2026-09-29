from __future__ import annotations

from typing import Any

from django import forms
from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils.translation import gettext_lazy as _

from hrcek.accounts.models import User
from hrcek.core.errors import HrcekError
from hrcek.entries import fetching, imaging
from hrcek.entries.models import Entry, FieldDefinition, FieldValue, Tag
from hrcek.entries.services import validate_field_value


class EntryForm(forms.ModelForm):
    tags = forms.CharField(
        label=_("Tags"),
        required=False,
        help_text=_("Separated by commas."),
    )
    # The picture's inputs sit together under a "Picture" heading on the
    # form, so their labels say only where the picture comes from.
    image_file = forms.ImageField(
        label=_("From this device"),
        required=False,
    )
    image_url = forms.URLField(
        label=_("Or from the web"),
        required=False,
        max_length=Entry.URL_MAX_LENGTH,
        help_text=_("The address of the picture itself, not of the page it is on."),
    )
    remove_image = forms.BooleanField(
        label=_("Remove the picture"),
        # The box sits before its label; a colon would point at nothing.
        label_suffix="",
        required=False,
    )

    class Meta:
        model = Entry
        fields = ("url", "title", "notes")

    def __init__(self, owner: User, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        # Set by clean(): the bytes to attach, and where they came from.
        self.picture: bytes | None = None
        self.picture_source = ""
        if self.instance.pk:
            self.initial["tags"] = ", ".join(t.name for t in self.instance.tags.all())

        # One input per field this person has defined. The form is built
        # from their rows, so a name they do not own cannot be submitted.
        self.definitions = list(FieldDefinition.objects.filter(owner=owner))
        existing = (
            {
                value.definition.pk: value.value
                for value in FieldValue.objects.filter(
                    entry=self.instance
                ).select_related("definition")
            }
            if self.instance.pk
            else {}
        )
        for definition in self.definitions:
            key = f"field_{definition.pk}"
            if definition.kind == FieldDefinition.CHOICE:
                self.fields[key] = forms.ChoiceField(
                    label=definition.name,
                    required=False,
                    choices=[("", "—"), *((o, o) for o in definition.options)],
                )
            else:
                self.fields[key] = forms.CharField(
                    label=definition.name, required=False
                )
            self.initial[key] = existing.get(definition.pk, "")

    def entry_fields(self) -> list[forms.BoundField]:
        """The entry itself: address, title, notes and tags."""
        return [self[name] for name in ("url", "title", "notes", "tags")]

    def custom_fields(self) -> list[forms.BoundField]:
        """One input per field this person has defined."""
        return [self[f"field_{d.pk}"] for d in self.definitions]

    def clean_url(self) -> str:
        return Entry.normalise_url(self.cleaned_data["url"])

    def clean(self) -> dict[str, Any]:
        cleaned = super().clean() or {}
        self._clean_picture(cleaned)
        for definition in self.definitions:
            key = f"field_{definition.pk}"
            raw = (cleaned.get(key) or "").strip()
            if not raw:
                continue
            try:
                validate_field_value(definition, raw)
            except DjangoValidationError as exc:
                # The service keys its message by the field's name, which
                # is not this form's input name, so pass the text along.
                self.add_error(key, list(exc.messages))
        return cleaned

    def _clean_picture(self, cleaned: dict[str, Any]) -> None:
        """Settle where the picture comes from, and read it.

        The bytes are validated here rather than in the view, so a bad
        picture comes back as a message beside the input like any other
        mistake, with the rest of the form still filled in.
        """
        uploaded = cleaned.get("image_file")
        address = (cleaned.get("image_url") or "").strip()

        if uploaded and address:
            self.add_error(
                "image_url",
                _("Give a file or an address, not both."),
            )
            return

        if not uploaded and not address:
            self.picture = None
            return

        try:
            if uploaded:
                # ImageField has already read the file to check it.
                uploaded.seek(0)
                data = uploaded.read()
            else:
                data = fetching.fetch(address)
            imaging.prepare(data)
        except HrcekError as exc:
            # The person sees the sentence, never the code; the code is
            # for clients, and is already in the logs.
            field = "image_file" if uploaded else "image_url"
            self.add_error(field, str(exc.error_code.message))
            return

        self.picture = data
        self.picture_source = "" if uploaded else address

    def tag_names(self) -> list[str]:
        return Tag.parse_names(self.cleaned_data.get("tags", ""))

    def field_values(self) -> dict[str, str]:
        """Every field, so an emptied input clears its value."""
        return {
            definition.name: (
                self.cleaned_data.get(f"field_{definition.pk}") or ""
            ).strip()
            for definition in self.definitions
        }


class FieldDefinitionForm(forms.ModelForm):
    class Meta:
        model = FieldDefinition
        fields = ("name", "kind")

    def __init__(self, owner: User, *args: Any, **kwargs: Any) -> None:
        self.owner = owner
        super().__init__(*args, **kwargs)
        # Only the creatable kinds are offered. A choice field needs
        # options, and there is no interface for editing those.
        self.fields["kind"].choices = [  # ty: ignore[unresolved-attribute]
            (value, label)
            for value, label in FieldDefinition.KINDS
            if value in FieldDefinition.CREATABLE_KINDS
        ]
        if self.instance.pk:
            # An existing value cannot always be reread as another type,
            # so the kind is fixed once the field exists. Silent data
            # loss would be worse than a missing feature.
            del self.fields["kind"]

    def clean_name(self) -> str:
        name = self.cleaned_data["name"].strip()
        clash = FieldDefinition.objects.filter(
            owner=self.owner, name__iexact=name
        ).exclude(pk=self.instance.pk)
        if clash.exists():
            raise forms.ValidationError(
                _("You already have a field with that name."), code="duplicate"
            )
        return name
