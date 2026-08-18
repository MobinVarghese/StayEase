from django.db import models
from django.utils.translation import gettext_lazy as _


class PaymentStatus(models.TextChoices):
    """
    Canonical dummy payment statuses.

    All members should import this enum rather than defining their
    own payment status strings.
    """

    PENDING = "PENDING", _("Pending")
    SUCCESS = "SUCCESS", _("Success")
    FAILED = "FAILED", _("Failed")


class Payment(models.Model):
    """
    A dummy payment associated with an approved booking.

    One payment per booking (OneToOneField).
    No real money is processed — this is for project demonstration.

    Business logic ownership: Member 5
    """

    booking_id: int

    booking = models.OneToOneField(
        "bookings.Booking",
        on_delete=models.CASCADE,
        related_name="payment",
        verbose_name=_("booking"),
    )
    amount = models.DecimalField(
        _("amount"),
        max_digits=10,
        decimal_places=2,
    )
    status = models.CharField(
        _("status"),
        max_length=20,
        choices=PaymentStatus.choices,
        default=PaymentStatus.PENDING,
    )
    transaction_ref = models.CharField(
        _("transaction reference"),
        max_length=100,
        blank=True,
        help_text=_("Dummy transaction reference for demonstration."),
    )
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)
    updated_at = models.DateTimeField(_("updated at"), auto_now=True)

    class Meta:
        verbose_name = _("Payment")
        verbose_name_plural = _("Payments")
        ordering = ["-created_at"]

    def __str__(self):
        return f"Payment for Booking #{self.booking_id} [{self.status}]"
