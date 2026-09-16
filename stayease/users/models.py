
from typing import ClassVar

from django.contrib.auth.models import AbstractUser
from django.core.validators import RegexValidator
from django.db import models
from django.db.models import CharField
from django.db.models import EmailField
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from .managers import UserManager


class UserRole(models.TextChoices):
    """
    Canonical user roles for the StayEase platform.

    Every member should reference this enum rather than
    hard-coding role strings.
    """

    TENANT = "TENANT", _("Tenant")
    OWNER = "OWNER", _("Owner")
    ADMIN = "ADMIN", _("Admin")


class User(AbstractUser):
    """
    Default custom user model for StayEase.
    If adding fields that need to be filled at user signup,
    check forms.SignupForm and forms.SocialSignupForms accordingly.
    """

    first_name = CharField(_("first name"), max_length=150, blank=False)
    last_name = CharField(_("last name"), max_length=150, blank=False)
    email = EmailField(_("email address"), unique=True)
    username = None  # type: ignore[assignment]
    phone_number = CharField(
        _("phone number"),
        max_length=10,
        blank=False,
        validators=[
            RegexValidator(
                regex=r"^\d{10}$",
                message=_("Phone number must be exactly 10 digits."),
            ),
        ],
        help_text=_("10-digit contact phone number."),
    )
    role = CharField(
        _("role"),
        max_length=20,
        choices=UserRole.choices,
        default=UserRole.TENANT,
        help_text=_(
            "Determines the user's platform permissions: Tenant, Owner, or Admin.",
        ),
    )

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects: ClassVar[UserManager] = UserManager()

    # ------------------------------------------------------------------
    # Convenience helpers
    # ------------------------------------------------------------------

    @property
    def name(self) -> str:
        """Full name — combines first and last for template/display use."""
        return f"{self.first_name} {self.last_name}".strip()

    @property
    def is_tenant(self) -> bool:
        return self.role == UserRole.TENANT

    @property
    def is_owner(self) -> bool:
        return self.role == UserRole.OWNER

    @property
    def is_admin_user(self) -> bool:
        """Named `is_admin_user` to avoid shadowing Django's admin helpers."""
        return self.role == UserRole.ADMIN

    def get_absolute_url(self) -> str:
        """Get URL for user's detail view.

        Returns:
            str: URL for user detail.

        """
        return reverse("users:detail", kwargs={"pk": self.id})
