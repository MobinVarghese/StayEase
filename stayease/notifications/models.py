from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


class Notification(models.Model):
    """
    A message generated for a user because of an important system event.

    Typically triggered by booking lifecycle changes.
    Business logic ownership: Member 5
    """

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
        verbose_name=_("recipient"),
    )
    booking = models.ForeignKey(
        "bookings.Booking",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="notifications",
        verbose_name=_("booking"),
        help_text=_("The booking this notification is associated with, if any."),
    )
    message = models.TextField(_("message"))
    is_read = models.BooleanField(
        _("read"),
        default=False,
        help_text=_("Whether the recipient has read this notification."),
    )
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)

    class Meta:
        verbose_name = _("Notification")
        verbose_name_plural = _("Notifications")
        ordering = ["-created_at"]

    def __str__(self):
        read_status = "read" if self.is_read else "unread"
        return f"Notification to {self.recipient} ({read_status})"
