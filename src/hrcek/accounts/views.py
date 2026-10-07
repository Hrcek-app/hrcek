from __future__ import annotations

from typing import Any, cast

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views.decorators.http import require_http_methods

from hrcek.accounts import allowlist
from hrcek.accounts.allowlist import is_signup_allowed
from hrcek.accounts.errors import (
    CONFIRMATION_INVALID,
    EMAIL_ALREADY_IN_USE,
    EMAIL_CHANGE_INVALID,
    INVITATION_INVALID,
    SIGNUP_NOT_ALLOWED,
)
from hrcek.accounts.forms import (
    ConfirmedUserAuthenticationForm,
    DisplayNameForm,
    EmailChangeForm,
    InvitationAcceptForm,
    PublicNameForm,
    SignupForm,
    TokenForm,
)
from hrcek.accounts.mail import absolute_url, send_email
from hrcek.accounts.models import ApiToken, Invitation, User
from hrcek.accounts.tokens import (
    make_confirmation_token,
    make_email_change_token,
    read_confirmation_token,
    read_email_change_token,
)
from hrcek.core.errors import ErrorCode


def _error_page(request: HttpRequest, code: ErrorCode, hint: str = "") -> HttpResponse:
    """Render a failure with the same code and status the API would use."""
    return render(
        request,
        "accounts/message.html",
        {"code": code.code, "message": str(code.message), "hint": hint},
        status=code.http_status,
    )


@login_required
def account(request: HttpRequest) -> HttpResponse:
    return render_account(request)


def render_account(request: HttpRequest, **overrides: Any) -> HttpResponse:
    """Render the hub, letting one caller substitute a bound form.

    Each form on the page posts to its own URL. When one fails
    validation its view re-renders this page with its own form bound, so
    the person sees a single page while each view keeps one
    responsibility.
    """
    # Imported here, not at module level: accounts must not depend on
    # collections when Django loads it, or the two apps import each
    # other in a circle.
    from hrcek.collections.models import Collection  # noqa: PLC0415

    # login_required guarantees a real User; the annotation does not.
    user = cast("User", request.user)
    context: dict[str, Any] = {
        "display_name_form": DisplayNameForm(instance=user),
        "public_name_form": PublicNameForm(instance=user),
        # Only warn about breaking links when there are links to break.
        "has_public_collections": Collection.objects.filter(
            owner=user, visibility=Collection.PUBLIC
        ).exists(),
        "email_change_form": EmailChangeForm(user),
    }
    context.update(overrides)
    return render(request, "accounts/account.html", context)


@login_required
def clients(request: HttpRequest) -> HttpResponse:
    return render_clients(request)


def render_clients(request: HttpRequest, **overrides: Any) -> HttpResponse:
    """Render the clients page; same substitution pattern as the hub."""
    user = cast("User", request.user)
    context: dict[str, Any] = {
        # Queried directly rather than through the reverse accessor:
        # ty does not run the django-stubs plugin, so it cannot see
        # related_name attributes.
        "tokens": ApiToken.objects.filter(user=user),
        "token_form": TokenForm(),
    }
    context.update(overrides)
    return render(request, "accounts/clients.html", context)


@require_http_methods(["POST"])
@login_required
def public_name(request: HttpRequest) -> HttpResponse:
    form = PublicNameForm(request.POST, instance=cast("User", request.user))
    if not form.is_valid():
        return render_account(request, public_name_form=form)
    form.save()
    messages.success(request, _("Your public name has been updated."))
    return redirect("accounts:account")


@require_http_methods(["POST"])
@login_required
def display_name(request: HttpRequest) -> HttpResponse:
    form = DisplayNameForm(request.POST, instance=cast("User", request.user))
    if not form.is_valid():
        return render_account(request, display_name_form=form)
    form.save()
    messages.success(request, _("Your display name has been updated."))
    return redirect("accounts:account")


def invitation_accept(request: HttpRequest, token: str) -> HttpResponse:
    invitation = Invitation.find_pending(token)
    if invitation is None:
        return _error_page(
            request,
            INVITATION_INVALID,
            _("Ask whoever invited you to send a new invitation."),
        )

    if request.method == "POST":
        form = InvitationAcceptForm(request.POST)
        if form.is_valid():
            user = User.objects.create_user(
                email=invitation.email,
                password=form.cleaned_data["password1"],
                display_name=form.cleaned_data["display_name"],
                # The link proved control of the inbox; a second
                # confirmation round would be theatre.
                email_verified_at=timezone.now(),
            )
            invitation.accepted_at = timezone.now()
            invitation.save(update_fields=["accepted_at"])
            login(request, user)
            return redirect("accounts:account")
    else:
        form = InvitationAcceptForm()

    return render(
        request,
        "accounts/invitation_accept.html",
        {"form": form, "email": invitation.email},
    )


def signup(request: HttpRequest) -> HttpResponse:
    if request.method != "POST":
        return render(request, "accounts/signup.html", {"form": SignupForm()})

    form = SignupForm(request.POST)
    if not form.is_valid():
        return render(request, "accounts/signup.html", {"form": form})

    email = form.cleaned_data["email"]
    if not is_signup_allowed(email):
        # A refusal the visitor cannot remedy, so it gets its own page
        # and a truthful status rather than a redisplayed form.
        return _error_page(request, SIGNUP_NOT_ALLOWED)

    existing = User.objects.filter(email__iexact=email).first()
    if existing is not None:
        # Same page, different email. Anything else would turn this form
        # into a way to discover who has an account.
        send_email(
            "signup_existing_account",
            email,
            {"reset_url": absolute_url(reverse("accounts:password_reset"))},
        )
    else:
        user = User.objects.create_user(
            email=email,
            password=form.cleaned_data["password1"],
            display_name=form.cleaned_data["display_name"],
        )
        send_email(
            "email_confirmation",
            email,
            {
                "confirm_url": absolute_url(
                    reverse("accounts:confirm", args=[make_confirmation_token(user)])
                ),
                "expires_hours": settings.HRCEK_EMAIL_CONFIRMATION_EXPIRY_HOURS,
            },
        )

    # No context: the page must not vary with what we just discovered.
    return render(request, "accounts/signup_done.html")


def confirm(request: HttpRequest, token: str) -> HttpResponse:
    user = read_confirmation_token(token)
    if user is None:
        return _error_page(
            request,
            CONFIRMATION_INVALID,
            _("Sign up again to get a fresh link."),
        )
    if not user.is_email_confirmed:
        user.email_verified_at = timezone.now()
        user.save(update_fields=["email_verified_at"])
    login(request, user)
    return redirect("accounts:account")


# The landing page is the login page. redirect_authenticated_user sends
# anyone already signed in to LOGIN_REDIRECT_URL instead.
class LandingView(LoginView):
    template_name = "accounts/landing.html"
    authentication_form = ConfirmedUserAuthenticationForm
    redirect_authenticated_user = True

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        # Offered only when somebody could get through: a link to a
        # form that refuses every visitor would be a dead end.
        context["signup_open"] = allowlist.is_open()
        return context


landing = LandingView.as_view()


@require_http_methods(["POST"])
@login_required
def email_change(request: HttpRequest) -> HttpResponse:
    user = cast("User", request.user)
    form = EmailChangeForm(user, request.POST)
    if not form.is_valid():
        return render_account(request, email_change_form=form)

    new_email = form.cleaned_data["new_email"]
    user.pending_email = new_email
    user.save(update_fields=["pending_email"])

    send_email(
        "email_change",
        new_email,
        {
            "confirm_url": absolute_url(
                reverse(
                    "accounts:email_change_confirm",
                    args=[make_email_change_token(user, new_email)],
                )
            ),
            "expires_hours": settings.HRCEK_EMAIL_CONFIRMATION_EXPIRY_HOURS,
        },
    )
    # To the address being left behind: if this was not them, this is how
    # they find out, while that address still works.
    send_email(
        "email_change_notice",
        user.email,
        {
            "new_email": new_email,
            "account_url": absolute_url(reverse("accounts:account")),
        },
    )
    messages.success(
        request,
        _(
            "Check %(email)s for a confirmation link. Until you follow it, "
            "your current address keeps working."
        )
        % {"email": new_email},
    )
    return redirect("accounts:account")


def email_change_confirm(request: HttpRequest, token: str) -> HttpResponse:
    # No login required: the link arrives in the new inbox, which may be
    # open on another device, and the signed token is the authorisation.
    result = read_email_change_token(token)
    if result is None:
        return _error_page(
            request,
            EMAIL_CHANGE_INVALID,
            _("Ask for the change again from your account page."),
        )

    user, new_email = result
    if (user.pending_email or "").lower() != new_email.lower():
        # Cancelled, already applied, or superseded by a later request.
        return _error_page(
            request,
            EMAIL_CHANGE_INVALID,
            _("Ask for the change again from your account page."),
        )
    if User.objects.filter(email__iexact=new_email).exclude(pk=user.pk).exists():
        return _error_page(request, EMAIL_ALREADY_IN_USE)

    user.email = new_email
    user.pending_email = None
    user.email_verified_at = timezone.now()
    user.save(update_fields=["email", "pending_email", "email_verified_at"])
    return render(request, "accounts/email_change_done.html", {"email": new_email})


@require_http_methods(["POST"])
@login_required
def email_change_cancel(request: HttpRequest) -> HttpResponse:
    user = cast("User", request.user)
    user.pending_email = None
    user.save(update_fields=["pending_email"])
    messages.success(request, _("The pending email change has been cancelled."))
    return redirect("accounts:account")


@require_http_methods(["POST"])
@login_required
def token_create(request: HttpRequest) -> HttpResponse:
    form = TokenForm(request.POST)
    if not form.is_valid():
        return render_clients(request, token_form=form)

    user = cast("User", request.user)
    _token, raw = ApiToken.issue(user, name=form.cleaned_data["name"])
    # The only moment this value will ever be visible.
    messages.warning(
        request,
        _("Copy this token now, it will not be shown again: %(token)s")
        % {"token": raw},
    )
    return redirect("accounts:clients")


@require_http_methods(["POST"])
@login_required
def token_delete(request: HttpRequest, pk: int) -> HttpResponse:
    # Scoped to the owner, so somebody else's id is simply not found.
    # A 403 would confirm that it exists.
    token = get_object_or_404(ApiToken, pk=pk, user=request.user)
    token.delete()
    messages.success(request, _("The token has been deleted."))
    return redirect("accounts:clients")
