from __future__ import annotations

import secrets
from typing import Any, ClassVar

from django.conf import settings
from django.db import models
from django.db.models import Q
from django.db.models.functions import Lower
from django.urls import reverse
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _

from hrcek.entries.models import Entry


def _new_secret() -> str:
    """The unguessable part of an unlisted collection's address.

    A callable default, so adding the column gives every existing row
    its own value instead of asking for one to share.
    """
    return secrets.token_urlsafe(16)


class Collection(models.Model):
    """A named set of somebody's entries.

    Membership is decided one way or the other and never both: either
    the owner picks the entries, or the collection names a label and
    holds whatever carries it. The kind is fixed at creation, because
    changing it would either discard hand-picked membership or swallow
    a label's entries whole — both are surprises worth refusing.
    """

    MANUAL = "manual"
    BY_LABEL = "label"
    KINDS: ClassVar[list[tuple[str, Any]]] = [
        (MANUAL, _("chosen by hand")),
        (BY_LABEL, _("everything with a label")),
    ]

    PRIVATE = "private"
    UNLISTED = "unlisted"
    PUBLIC = "public"
    VISIBILITIES: ClassVar[list[tuple[str, Any]]] = [
        (PRIVATE, _("Private")),
        (UNLISTED, _("Anyone with the link")),
        (PUBLIC, _("Public")),
    ]

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="collections",
        verbose_name=_("owner"),
    )
    name = models.CharField(_("name"), max_length=100)
    description = models.TextField(_("description"), blank=True)
    kind = models.CharField(_("kind"), max_length=10, choices=KINDS, default=MANUAL)
    label = models.ForeignKey(
        "entries.Tag",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="collections",
        verbose_name=_("label"),
    )
    visibility = models.CharField(
        _("visibility"), max_length=10, choices=VISIBILITIES, default=PRIVATE
    )
    slug = models.SlugField(_("address"), max_length=120, blank=True)
    # Made once and kept for the collection's life, so a link already
    # shared keeps working across a change of mind about visibility.
    secret = models.CharField(max_length=32, unique=True, editable=False)
    show_notes = models.BooleanField(_("show notes"), default=False)
    show_tags = models.BooleanField(_("show labels"), default=False)
    show_images = models.BooleanField(_("show pictures"), default=False)
    visible_fields = models.ManyToManyField(
        "entries.FieldDefinition",
        blank=True,
        related_name="collections",
        verbose_name=_("visible fields"),
    )
    # Not fixed like `kind`: switching it off only stops marks applying,
    # so switching it back on finds them where they were.
    is_wish_list = models.BooleanField(_("wish list"), default=False)
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)
    updated_at = models.DateTimeField(_("changed at"), auto_now=True)

    class Meta:
        verbose_name = _("collection")
        verbose_name_plural = _("collections")
        ordering = ("name",)
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.UniqueConstraint(
                "owner", Lower("name"), name="unique_collection_per_owner_ci"
            ),
            # A label collection names exactly one label; a manual one
            # names none. The database refuses the other two shapes,
            # because a collection in either of them has no meaning.
            models.CheckConstraint(
                condition=(
                    Q(kind="label", label__isnull=False)
                    | Q(kind="manual", label__isnull=True)
                ),
                name="label_set_exactly_when_kind_is_label",
            ),
            models.UniqueConstraint(
                fields=["owner", "slug"],
                condition=~Q(slug=""),
                name="unique_public_slug_per_owner",
            ),
        ]

    def __str__(self) -> str:
        return self.name

    def save(self, *args: Any, **kwargs: Any) -> None:
        if not self.secret:
            self.secret = secrets.token_urlsafe(16)
        if self.visibility == self.PUBLIC:
            self.slug = self._unique_slug()
        super().save(*args, **kwargs)

    def _unique_slug(self) -> str:
        """A slug of the name, made unique within this account.

        Regenerated whenever a public collection is saved, so renaming
        one moves it — which is why the form warns about that.
        """
        base = slugify(self.name) or "collection"
        candidate, suffix = base, 1
        siblings = Collection.objects.filter(owner=self.owner).exclude(pk=self.pk)
        while siblings.filter(slug=candidate).exists():
            suffix += 1
            candidate = f"{base}-{suffix}"
        return candidate

    def public_url(self) -> str:
        return reverse(
            "shared:public",
            kwargs={"namespace": self.owner.namespace, "slug": self.slug},
        )

    def unlisted_url(self) -> str:
        return reverse("shared:unlisted", kwargs={"secret": self.secret})

    def shared_url(self) -> str:
        """Whichever address this collection is shared at."""
        if self.visibility == self.PUBLIC:
            return self.public_url()
        return self.unlisted_url()

    def is_shared(self) -> bool:
        return self.visibility in (self.UNLISTED, self.PUBLIC)

    def entries(self) -> models.QuerySet[Entry]:
        """This collection's entries, newest first.

        The two kinds order by different clocks: a manual collection by
        when the entry was put into it, a label collection by when the
        entry was saved, because there is no moment of adding. One
        method, so pages, feeds and tests cannot drift apart.
        """
        if self.kind == self.BY_LABEL:
            return (
                Entry.objects.filter(owner=self.owner, tags=self.label)
                .order_by("-created_at", "-pk")
                .distinct()
            )
        return Entry.objects.filter(collection_memberships__collection=self).order_by(
            "-collection_memberships__added_at",
            "-collection_memberships__pk",
        )


class CollectionEntry(models.Model):
    """One entry's place in one manual collection.

    `added_at` is what orders a manual collection, which is why this is
    a model of its own rather than a plain many-to-many.
    """

    collection = models.ForeignKey(
        Collection,
        on_delete=models.CASCADE,
        related_name="memberships",
        verbose_name=_("collection"),
    )
    entry = models.ForeignKey(
        "entries.Entry",
        on_delete=models.CASCADE,
        related_name="collection_memberships",
        verbose_name=_("entry"),
    )
    added_at = models.DateTimeField(_("added at"), auto_now_add=True)

    class Meta:
        verbose_name = _("collection entry")
        verbose_name_plural = _("collection entries")
        ordering = ("-added_at", "-pk")
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.UniqueConstraint(
                fields=["collection", "entry"], name="unique_entry_per_collection"
            )
        ]

    def __str__(self) -> str:
        return f"{self.entry} in {self.collection}"


class GotIt(models.Model):
    """Somebody has got one item on one wish list for its owner.

    Read only through `Collection.entries()`, so a mark on an item that
    has left the list does nothing until the item returns — and needs
    no cleanup in between.
    """

    collection = models.ForeignKey(
        Collection,
        on_delete=models.CASCADE,
        related_name="got_its",
        verbose_name=_("collection"),
    )
    entry = models.ForeignKey(
        "entries.Entry",
        on_delete=models.CASCADE,
        related_name="got_its",
        verbose_name=_("entry"),
    )
    # Never shown to the owner; it is what lets the giver undo.
    got_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="+",
        verbose_name=_("got by"),
    )
    got_at = models.DateTimeField(_("got at"), auto_now_add=True)

    class Meta:
        verbose_name = _("got it")
        verbose_name_plural = _("got its")
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.UniqueConstraint(
                fields=["collection", "entry"], name="one_got_it_per_list_entry"
            )
        ]

    def __str__(self) -> str:
        return f"{self.entry} got for {self.collection}"
