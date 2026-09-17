
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


# ---------------------------------------------------------------------------
# Password-reset workflow models
# ---------------------------------------------------------------------------


class ResetRequestStatus(models.TextChoices):
    """
    Lifecycle states for an admin-mediated password-reset request.

    Allowed transitions (enforced in the admin actions):
        pending  → approved
        pending  → rejected
    Once approved or rejected a request cannot be changed again.
    """

    PENDING = "pending", _("Pending")
    APPROVED = "approved", _("Approved")
    REJECTED = "rejected", _("Rejected")


class PasswordResetRequest(models.Model):
    """
    Represents a user's request for an administrator to reset their password.

    Workflow
    --------
    1. User submits the /forgot-password/ form → record created with status=PENDING.
    2. An admin reviews the request from the admin interface.
    3. On approval, the admin sets a cryptographically secure temporary password,
       calls ``user.set_password(temporary_password)``, and stores it in ``new_password``
       so it can be communicated to the user out-of-band.
    4. The user logs in with the temporary password and changes it via profile settings.
    """

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="password_reset_requests",
        verbose_name=_("user"),
    )
    email = models.EmailField(_("email address"))
    reason = models.TextField(
        _("reason"),
        blank=True,
        null=True,
        help_text=_("Optional note from the user explaining why they need a reset."),
    )
    status = models.CharField(
        _("status"),
        max_length=20,
        choices=ResetRequestStatus.choices,
        default=ResetRequestStatus.PENDING,
        db_index=True,
    )
    admin_notes = models.TextField(
        _("admin notes"),
        blank=True,
        null=True,
        help_text=_("Optional notes recorded by the administrator."),
    )
    processed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="processed_reset_requests",
        verbose_name=_("processed by"),
    )
    # Stores the plain-text temporary password ONLY so the admin can read and
    # communicate it. The actual User.password column stores the secure hash.
    new_password = models.CharField(
        _("temporary password"),
        max_length=128,
        blank=True,
        null=True,
        help_text=_(
            "Plain-text temporary password set by admin on approval. "
            "Share with the user out-of-band."
        ),
    )
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)
    processed_at = models.DateTimeField(_("processed at"), null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = _("Password Reset Request")
        verbose_name_plural = _("Password Reset Requests")

    def __str__(self) -> str:
        return f"{self.user.email} - {self.status} - {self.created_at}"

    @property
    def is_pending(self) -> bool:
        return self.status == ResetRequestStatus.PENDING

    @property
    def is_approved(self) -> bool:
        return self.status == ResetRequestStatus.APPROVED

    @property
    def is_rejected(self) -> bool:
        return self.status == ResetRequestStatus.REJECTED

    @property
    def temp_password(self) -> str | None:
        """Alias for new_password for convenience."""
        return self.new_password
