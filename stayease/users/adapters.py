from __future__ import annotations

import typing

from allauth.account.adapter import DefaultAccountAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.conf import settings

from django.urls import reverse

if typing.TYPE_CHECKING:
    from allauth.account.models import EmailConfirmation
    from allauth.socialaccount.models import SocialLogin
    from django.http import HttpRequest

    from stayease.users.models import User


def get_canonical_public_url() -> str:
    """Return the normalized canonical public origin for StayEase."""
    url = getattr(settings, "STAYEASE_PUBLIC_URL", None) or getattr(settings, "SITE_URL", "http://localhost:8000")
    return url.strip().rstrip("/")


class AccountAdapter(DefaultAccountAdapter):
    def is_open_for_signup(self, request: HttpRequest) -> bool:
        return getattr(settings, "ACCOUNT_ALLOW_REGISTRATION", True)

    def is_email_verified(self, request: HttpRequest, email: str) -> bool:
        """
        Email verification is disabled on StayEase.
        All user emails are treated as verified so that users are never blocked
        or prompted to verify when signing in or signing up.
        """
        return True

    def send_confirmation_mail(
        self, request: HttpRequest, emailconfirmation: EmailConfirmation, signup: bool
    ) -> None:
        """
        Email verification is disabled; do not send verification emails.
        """
        pass

    def save_user(
        self,
        request: HttpRequest,
        user: User,
        form: typing.Any,
        commit: bool = True,
    ) -> User:
        """
        Save user and ensure the associated EmailAddress record is verified.
        """
        user = super().save_user(request, user, form, commit=commit)
        from allauth.account.models import EmailAddress

        EmailAddress.objects.filter(user=user).update(verified=True)
        return user

    def get_email_confirmation_url(
        self, request: HttpRequest | None, emailconfirmation: EmailConfirmation
    ) -> str:
        """
        Construct the email confirmation (activation) URL using the configured
        canonical public URL (STAYEASE_PUBLIC_URL).
        """
        path = reverse("account_confirm_email", args=[emailconfirmation.key])
        base_url = get_canonical_public_url()
        return f"{base_url}{path}"

    def get_reset_password_from_key_url(self, key: str) -> str:
        """
        Construct password reset URL using canonical public URL.
        """
        path = reverse("account_reset_password_from_key", kwargs={"key": key})
        base_url = get_canonical_public_url()
        return f"{base_url}{path}"


class SocialAccountAdapter(DefaultSocialAccountAdapter):
    def is_open_for_signup(
        self,
        request: HttpRequest,
        sociallogin: SocialLogin,
    ) -> bool:
        return getattr(settings, "ACCOUNT_ALLOW_REGISTRATION", True)

    def populate_user(
        self,
        request: HttpRequest,
        sociallogin: SocialLogin,
        data: dict[str, typing.Any],
    ) -> User:
        """
        Populates user information from social provider info.

        See: https://docs.allauth.org/en/latest/socialaccount/advanced.html#creating-and-populating-user-instances
        """
        user = super().populate_user(request, sociallogin, data)
        if not user.first_name:
            if name := data.get("name"):
                parts = name.split(" ", 1)
                user.first_name = parts[0]
                user.last_name = parts[1] if len(parts) > 1 else ""
            elif first_name := data.get("first_name"):
                user.first_name = first_name
                user.last_name = data.get("last_name", "")
        return user
