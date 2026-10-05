from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from typing import Any, ClassVar
from urllib.parse import urlsplit, urlunsplit

from django.conf import settings
from django.db import models
from django.db.models import Q
from django.db.models.functions import Lower
from django.utils.translation import gettext_lazy as _

from hrcek.entries import imaging


class Tag(models.Model):
    """A label, belonging to one person.

    Nina's "watches" and Marko's "watches" are unrelated rows; neither
    can see the other's.
    """

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="tags",
        verbose_name=_("owner"),
    )
    name = models.CharField(_("name"), max_length=50)

    class Meta:
        verbose_name = _("tag")
        verbose_name_plural = _("tags")
        ordering = ("name",)
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.UniqueConstraint(
                "owner", Lower("name"), name="unique_tag_per_owner_ci"
            )
        ]

    def __str__(self) -> str:
        return self.name

    @staticmethod
    def parse_names(raw: str) -> list[str]:
        """Split a comma-separated field, keeping the first casing seen."""
        seen: set[str] = set()
        names: list[str] = []
        for part in (raw or "").split(","):
            name = part.strip()
            if not name or name.lower() in seen:
                continue
            seen.add(name.lower())
            names.append(name)
        return names

    @classmethod
    def set_for(cls, entry: Entry, names: list[str]) -> None:
        tags = []
        for name in names:
            tag = cls.objects.filter(owner=entry.owner, name__iexact=name).first()
            if tag is None:
                tag = cls.objects.create(owner=entry.owner, name=name)
            tags.append(tag)
        entry.tags.set(tags)
        cls.prune_orphans(entry.owner)

    @classmethod
    def prune_orphans(cls, owner: object) -> None:
        """Remove this owner's tags that no entry uses any more.

        Otherwise every typo lives in the tag list forever. A tag a
        collection follows is spared: deleting it would take the
        collection with it, shared link and all, and that is the
        owner's decision rather than a side effect of relabelling.
        Written as string lookups rather than through reverse
        accessors, which ty cannot see.
        """
        cls.objects.filter(
            owner=owner, entries__isnull=True, collections__isnull=True
        ).delete()

    @classmethod
    def in_use(cls, owner: object) -> models.QuerySet[Tag]:
        """This owner's tags that at least one entry carries.

        What anybody is shown as "your labels": a tag kept only because
        a collection follows it has nothing to list.
        """
        return cls.objects.filter(owner=owner, entries__isnull=False).distinct()


class Entry(models.Model):
    """Something somebody found worth keeping."""

    URL_MAX_LENGTH = 2000

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="entries",
        verbose_name=_("owner"),
    )
    url = models.URLField(_("address"), max_length=URL_MAX_LENGTH)
    title = models.CharField(_("title"), max_length=300, blank=True)
    notes = models.TextField(_("notes"), blank=True)
    tags = models.ManyToManyField(
        Tag, related_name="entries", blank=True, verbose_name=_("tags")
    )
    created_at = models.DateTimeField(_("saved at"), auto_now_add=True)
    updated_at = models.DateTimeField(_("changed at"), auto_now=True)

    class Meta:
        verbose_name = _("entry")
        verbose_name_plural = _("entries")
        # -pk as well as -created_at: entries saved in one batch can share
        # a timestamp, and without a tiebreaker pagination can repeat or
        # skip a row.
        ordering = ("-created_at", "-pk")
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.UniqueConstraint(
                fields=["owner", "url"], name="unique_entry_url_per_owner"
            )
        ]

    def __str__(self) -> str:
        return self.display_title

    @property
    def display_title(self) -> str:
        return self.title or self.url

    def is_publicly_visible(self) -> bool:
        """Is this entry's picture readable by anybody at all?

        True when the entry is in at least one collection that is
        shared — by link or in the open — and that shows pictures.
        Both kinds of collection count: a label collection reaches its
        entries through the label rather than through membership rows.

        Imported here rather than at module level: entries must not
        depend on collections while Django is loading the apps, or the
        two import each other in a circle.
        """
        from hrcek.collections.models import Collection  # noqa: PLC0415

        return Collection.objects.filter(
            Q(memberships__entry=self)
            | Q(kind=Collection.BY_LABEL, label__in=self.tags.all()),
            owner=self.owner,
            show_images=True,
            visibility__in=(Collection.UNLISTED, Collection.PUBLIC),
        ).exists()

    @staticmethod
    def normalise_url(value: str) -> str:
        """Trim, and lowercase the scheme and host. Nothing else.

        Fuller normalisation — trailing slashes, www., stripping utm_* —
        is a rabbit hole where every rule is wrong for some site, and its
        failure mode is silent: two different pages merge into one entry
        and one is lost. This way the failure mode is a visible duplicate
        the person can fix.
        """
        parts = urlsplit((value or "").strip())
        return urlunsplit(
            (
                parts.scheme.lower(),
                parts.netloc.lower(),
                parts.path,
                parts.query,
                parts.fragment,
            )
        )


class EntryImage(models.Model):
    """The picture belonging to one entry.

    Its own table rather than columns on `Entry`: SQLite keeps a row's
    blobs inline, so listing entries would drag every image off disk for
    no reason. Nothing joins this table unless a page actually wants a
    picture.

    Two copies are kept. `original` is exactly what arrived and is never
    served — it is the source from which any future rendition is made.
    `display` is re-encoded, capped, and stripped of metadata; that is
    what a browser receives.
    """

    entry = models.OneToOneField(
        "entries.Entry",
        on_delete=models.CASCADE,
        related_name="image",
        verbose_name=_("entry"),
    )
    original = models.BinaryField(_("original"), editable=False)
    original_content_type = models.CharField(_("original type"), max_length=60)
    display = models.BinaryField(_("display copy"), editable=False)
    width = models.PositiveIntegerField(_("width"))
    height = models.PositiveIntegerField(_("height"))
    checksum = models.CharField(_("checksum"), max_length=64)
    byte_size = models.PositiveIntegerField(_("size in bytes"))
    # Empty when the person uploaded the file themselves.
    source_url = models.URLField(_("source address"), max_length=2000, blank=True)
    created_at = models.DateTimeField(_("added at"), auto_now_add=True)

    class Meta:
        verbose_name = _("image")
        verbose_name_plural = _("images")

    def __str__(self) -> str:
        return f"{self.entry.display_title} ({self.width}x{self.height})"

    @classmethod
    def attach(cls, entry: Entry, data: bytes, *, source_url: str = "") -> EntryImage:
        """Validate `data` and make it this entry's one image.

        Replaces whatever was there: an entry has at most one picture.
        """
        prepared = imaging.prepare(data)
        image, _created = cls.objects.update_or_create(
            entry=entry,
            defaults={
                "original": prepared.original,
                "original_content_type": prepared.original_content_type,
                "display": prepared.display,
                "width": prepared.width,
                "height": prepared.height,
                "checksum": prepared.checksum,
                "byte_size": prepared.byte_size,
                "source_url": source_url,
            },
        )
        image.rendition(imaging.DISPLAY_FORMAT)
        return image

    def cached_path(self, fmt: str) -> Path:
        """Where this rendition lives on disk.

        Content-addressed: the same bytes always land in the same place,
        and a replaced image never collides with the one before it.
        """
        root = Path(settings.MEDIA_ROOT)
        return root / "images" / self.checksum[:2] / f"{self.checksum}.{fmt}"

    def rendition(self, fmt: str) -> bytes:
        """The bytes to serve, writing the disk cache if it is missing.

        The cache is disposable. Delete the directory and the next
        request rebuilds it from the database.
        """
        path = self.cached_path(fmt)
        if path.exists():
            return path.read_bytes()

        if fmt == imaging.DISPLAY_FORMAT:
            data = bytes(self.display)
        else:
            data = imaging.render(bytes(self.original), fmt=fmt)

        path.parent.mkdir(parents=True, exist_ok=True)
        # Written beside the target and moved into place, so a reader
        # never sees a half-written file.
        temporary = path.with_suffix(f".{fmt}.part")
        temporary.write_bytes(data)
        temporary.replace(path)
        return data


class FieldDefinition(models.Model):
    """A field somebody has decided their entries should carry.

    Every account starts with Price and Priority, but nothing marks them
    as special: they can be renamed or deleted like any other.
    """

    TEXT = "text"
    NUMBER = "number"
    CHOICE = "choice"

    KINDS: ClassVar[list[tuple[str, Any]]] = [
        (TEXT, _("text")),
        (NUMBER, _("number")),
        (CHOICE, _("choice")),
    ]

    # A choice field needs options, and there is no interface for editing
    # them. It exists for the seeded priority and nothing else.
    CREATABLE_KINDS = (TEXT, NUMBER)

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="field_definitions",
        verbose_name=_("owner"),
    )
    name = models.CharField(_("name"), max_length=50)
    kind = models.CharField(_("kind"), max_length=10, choices=KINDS, default=TEXT)
    options = models.JSONField(_("options"), default=list, blank=True)
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)

    class Meta:
        verbose_name = _("field")
        verbose_name_plural = _("fields")
        ordering = ("name",)
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.UniqueConstraint(
                "owner", Lower("name"), name="unique_field_per_owner_ci"
            )
        ]

    def __str__(self) -> str:
        return self.name


class FieldValue(models.Model):
    """What one entry holds for one field.

    Values live in a column matching their type rather than in one text
    column, so that numbers sort and compare as numbers.
    """

    entry = models.ForeignKey(
        Entry,
        on_delete=models.CASCADE,
        related_name="field_values",
        verbose_name=_("entry"),
    )
    definition = models.ForeignKey(
        FieldDefinition,
        on_delete=models.CASCADE,
        related_name="values",
        verbose_name=_("field"),
    )
    value_text = models.TextField(_("text value"), blank=True)
    value_number = models.DecimalField(
        _("number value"), max_digits=20, decimal_places=6, null=True, blank=True
    )

    class Meta:
        verbose_name = _("field value")
        verbose_name_plural = _("field values")
        ordering = ("definition__name",)
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.UniqueConstraint(
                fields=["entry", "definition"], name="unique_value_per_field_per_entry"
            )
        ]

    def __str__(self) -> str:
        return f"{self.definition}: {self.value}"

    @staticmethod
    def format_number(number: Decimal) -> str:
        """Render a stored number the way it was most likely typed.

        The column keeps six decimal places, so 129 comes back as
        129.000000. `normalize` strips the zeros but turns round numbers
        into exponent form — 1000 becomes 1E+3 — so those are quantized
        back to an integer.
        """
        trimmed = number.normalize()
        if trimmed == trimmed.to_integral_value():
            trimmed = trimmed.quantize(Decimal(1))
        return str(trimmed)

    @property
    def value(self) -> str:
        if self.definition.kind == FieldDefinition.NUMBER:
            if self.value_number is None:
                return ""
            return self.format_number(self.value_number)
        return self.value_text

    @value.setter
    def value(self, raw: str) -> None:
        if self.definition.kind == FieldDefinition.NUMBER:
            self.value_number = Decimal(raw) if raw else None
            self.value_text = ""
        else:
            self.value_text = raw
            self.value_number = None
