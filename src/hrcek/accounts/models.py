from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Any, ClassVar

from django.conf import settings
from django.contrib.auth.base_user import AbstractBaseUser
from django.contrib.auth.models import PermissionsMixin
from django.db import models
from django.db.models.functions import Lower
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from hrcek.accounts.managers import UserManager
from hrcek.accounts.validators import (
    validate_display_name,
    validate_domain,
    validate_namespace,
)
from hrcek.core.listing import LIST, VIEWS


class User(AbstractBaseUser, PermissionsMixin):
    """Someone who uses Hrcek.

    ``password`` (the hash) and ``last_login`` come from
    ``AbstractBaseUser``; ``is_superuser``, ``groups`` and
    ``user_permissions`` from ``PermissionsMixin``.

    ``is_active`` is redeclared here deliberately: the base class defines
    it as a plain class attribute fixed at ``True``, and only a real
    field can be switched off from the admin.
    """

    email = models.EmailField(_("email address"), max_length=254, unique=True)
    # Set while a change awaits confirmation from the new address.
    # `email` is not touched until then, so the old address keeps
    # working, which is the whole point of the pending field.
    # DJ001 is wrong here for the same reason as display_name: NULL means
    # "no change pending", and an empty string would be a second falsy
    # value meaning the same thing.
    pending_email = models.EmailField(  # noqa: DJ001
        _("pending email address"), max_length=254, null=True, blank=True
    )
    # null=True is deliberate and DJ001 is wrong here: NULL means "no
    # display name", and SQL treats NULLs in a unique index as distinct,
    # which is exactly what lets many users have none while set names
    # stay unique. An empty string would collide with itself.
    display_name = models.CharField(  # noqa: DJ001
        _("display name"),
        max_length=50,
        blank=True,
        null=True,
        validators=[validate_display_name],
        help_text=_("Optional. Can be used to sign in instead of the email."),
    )
    # Null until somebody publishes something. It becomes part of the
    # address of every public collection, which is why the character
    # set is narrow and why changing it is warned about rather than
    # done quietly. NULL, like display_name, so many accounts can have
    # none while the ones that are set stay unique.
    namespace = models.CharField(  # noqa: DJ001
        _("public name"),
        max_length=50,
        blank=True,
        null=True,
        validators=[validate_namespace],
        help_text=_(
            "Only needed if you make a collection public. It appears in "
            "the address of every public collection you have, like "
            "/u/your-name/watches/."
        ),
    )
    email_verified_at = models.DateTimeField(
        _("email confirmed at"), null=True, blank=True
    )
    # How the entries page shows entries: whichever was picked last.
    entry_view = models.CharField(
        _("entry view"), max_length=10, choices=VIEWS, default=LIST
    )
    is_active = models.BooleanField(_("active"), default=True)
    is_staff = models.BooleanField(_("staff status"), default=False)
    date_joined = models.DateTimeField(_("date joined"), default=timezone.now)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS: ClassVar[list[str]] = []

    class Meta:
        verbose_name = _("user")
        verbose_name_plural = _("users")
        constraints: ClassVar[list[models.BaseConstraint]] = [
            # unique=True on email already satisfies Django's auth.E003
            # check; these add the case-insensitive guarantee. NULL
            # display names never collide, because SQL treats NULLs in a
            # unique index as distinct.
            models.UniqueConstraint(Lower("email"), name="user_email_ci_unique"),
            models.UniqueConstraint(
                Lower("display_name"), name="user_display_name_ci_unique"
            ),
            models.UniqueConstraint(
                Lower("namespace"), name="user_namespace_ci_unique"
            ),
        ]

    def __str__(self) -> str:
        return self.display_name or self.email

    def normalise(self) -> None:
        self.email = self.email.strip().lower()
        if self.display_name is not None:
            self.display_name = self.display_name.strip() or None
        if self.namespace is not None:
            self.namespace = self.namespace.strip() or None

    def clean(self) -> None:
        self.normalise()
        super().clean()

    def save(self, **kwargs: Any) -> None:
        self.normalise()
        super().save(**kwargs)

    @property
    def is_email_confirmed(self) -> bool:
        return self.email_verified_at is not None


class ApiToken(models.Model):
    """A bearer credential for non-browser clients.

    Only the hash is stored. The raw value exists once, at creation, and
    is shown to the person who made it and never again.
    """

    # Not a secret: a public marker so secret scanners can spot the
    # tokens that follow it.
    TOKEN_PREFIX = "hrcek_"  # noqa: S105
    # Named, so the API's check and the column cannot drift apart.
    NAME_MAX_LENGTH = 50
    # Writing last_used_at on every request would turn reads into SQLite
    # writes for no benefit; a minute's resolution is plenty.
    TOUCH_INTERVAL = timedelta(minutes=1)

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="api_tokens",
        verbose_name=_("user"),
    )
    name = models.CharField(_("name"), max_length=NAME_MAX_LENGTH)
    token_hash = models.CharField(max_length=64, unique=True, editable=False)
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)
    last_used_at = models.DateTimeField(
        _("last used at"), null=True, blank=True, editable=False
    )
    expires_at = models.DateTimeField(_("expires at"), null=True, blank=True)
    revoked_at = models.DateTimeField(_("revoked at"), null=True, blank=True)

    class Meta:
        verbose_name = _("API token")
        verbose_name_plural = _("API tokens")
        ordering = ("-created_at",)

    def __str__(self) -> str:
        return f"{self.name} ({self.user})"

    @classmethod
    def new_raw_token(cls) -> str:
        # The prefix makes the string recognisable to secret scanners.
        return f"{cls.TOKEN_PREFIX}{secrets.token_urlsafe(32)}"

    @staticmethod
    def hash_token(raw: str) -> str:
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    @classmethod
    def issue(
        cls, user: User, name: str, expires_at: datetime | None = None
    ) -> tuple[ApiToken, str]:
        raw = cls.new_raw_token()
        token = cls.objects.create(
            user=user,
            name=name,
            token_hash=cls.hash_token(raw),
            expires_at=expires_at,
        )
        return token, raw

    @property
    def is_usable(self) -> bool:
        if self.revoked_at is not None:
            return False
        return self.expires_at is None or self.expires_at > timezone.now()

    def touch(self) -> None:
        now = timezone.now()
        if (
            self.last_used_at is not None
            and now - self.last_used_at < self.TOUCH_INTERVAL
        ):
            return
        ApiToken.objects.filter(pk=self.pk).update(last_used_at=now)
        self.last_used_at = now


class AllowedEmail(models.Model):
    """One address permitted to register without an invitation."""

    email = models.EmailField(_("email address"), max_length=254, unique=True)
    note = models.CharField(_("note"), max_length=200, blank=True)
    created_at = models.DateTimeField(_("added at"), auto_now_add=True)

    class Meta:
        verbose_name = _("allowed email address")
        verbose_name_plural = _("allowed email addresses")
        ordering = ("email",)

    def __str__(self) -> str:
        return self.email

    def save(self, **kwargs: Any) -> None:
        self.email = self.email.strip().lower()
        super().save(**kwargs)


class AllowedDomain(models.Model):
    """Every address on this domain may register without an invitation."""

    domain = models.CharField(
        _("domain"), max_length=255, unique=True, validators=[validate_domain]
    )
    note = models.CharField(_("note"), max_length=200, blank=True)
    created_at = models.DateTimeField(_("added at"), auto_now_add=True)

    class Meta:
        verbose_name = _("allowed domain")
        verbose_name_plural = _("allowed domains")
        ordering = ("domain",)

    def __str__(self) -> str:
        return self.domain

    def save(self, **kwargs: Any) -> None:
        self.domain = self.domain.strip().lower().lstrip("@")
        super().save(**kwargs)


class Invitation(models.Model):
    """An admin's offer of an account, redeemable once.

    Only the hash of the token is stored, so a leaked database backup
    yields no usable invitations. The raw token exists in exactly one
    place: the link in the email.
    """

    email = models.EmailField(_("email address"), max_length=254)
    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="invitations_sent",
        verbose_name=_("invited by"),
    )
    token_hash = models.CharField(max_length=64, unique=True, editable=False)
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)
    expires_at = models.DateTimeField(_("expires at"))
    accepted_at = models.DateTimeField(_("accepted at"), null=True, blank=True)
    revoked_at = models.DateTimeField(_("revoked at"), null=True, blank=True)

    class Meta:
        verbose_name = _("invitation")
        verbose_name_plural = _("invitations")
        ordering = ("-created_at",)
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.UniqueConstraint(
                Lower("email"),
                condition=models.Q(accepted_at__isnull=True, revoked_at__isnull=True),
                name="one_pending_invitation_per_email",
            )
        ]

    def __str__(self) -> str:
        return self.email

    @property
    def is_pending(self) -> bool:
        return (
            self.accepted_at is None
            and self.revoked_at is None
            and self.expires_at > timezone.now()
        )

    @classmethod
    def issue(cls, email: str, invited_by: User) -> tuple[Invitation, str]:
        """Create or refresh a pending invitation and send the email."""
        # Imported here, not at module level: mail reads settings, which
        # import models, so a top-level import would be circular.
        from hrcek.accounts.mail import absolute_url, send_email  # noqa: PLC0415

        address = email.strip().lower()
        raw = ApiToken.new_raw_token()
        expires_at = timezone.now() + timedelta(
            days=settings.HRCEK_INVITATION_EXPIRY_DAYS
        )
        invitation, _created = cls.objects.update_or_create(
            email=address,
            accepted_at=None,
            revoked_at=None,
            defaults={
                "invited_by": invited_by,
                "token_hash": ApiToken.hash_token(raw),
                "expires_at": expires_at,
            },
        )
        send_email(
            "invitation",
            address,
            {
                "invited_by": str(invited_by),
                "accept_url": absolute_url(f"/accounts/invitation/{raw}/"),
                "expires_at": expires_at.date().isoformat(),
            },
        )
        return invitation, raw

    @classmethod
    def find_pending(cls, raw_token: str) -> Invitation | None:
        invitation = cls.objects.filter(
            token_hash=ApiToken.hash_token(raw_token)
        ).first()
        return invitation if invitation is not None and invitation.is_pending else None
