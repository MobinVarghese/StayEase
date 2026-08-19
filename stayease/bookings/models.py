from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


class BookingStatus(models.TextChoices):
    """
    Canonical booking lifecycle states.

    This is the single source of truth for booking status values.
    All members should import this enum rather than defining their
    own status strings.

    Lifecycle:
        PENDING
           ├──> REJECTED
           └──> APPROVED
                  └──> PAYMENT_PENDING
                          └──> CONFIRMED
    """

    PENDING = "PENDING", _("Pending")
    APPROVED = "APPROVED", _("Approved")
    PAYMENT_PENDING = "PAYMENT_PENDING", _("Payment Pending")
    REJECTED = "REJECTED", _("Rejected")
    CONFIRMED = "CONFIRMED", _("Confirmed")


class Booking(models.Model):
    """
    A tenant's request to reserve a bed.

    A tenant can create multiple bookings (one per bed).
    Business rules — state transitions, concurrency, validation — are
    owned by Member 4.  Member 5 consumes booking events for
    notifications and payment.

    Relationships:
        Tenant (User with role=TENANT) 1──N Booking
        Bed 1──N Booking
    """

    tenant = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="bookings",
        verbose_name=_("tenant"),
        help_text=_("The tenant who requested this booking."),
    )
    bed = models.ForeignKey(
        "properties.Bed",
        on_delete=models.CASCADE,
        related_name="bookings",
        verbose_name=_("bed"),
        help_text=_("The bed being booked."),
    )
    status = models.CharField(
        _("status"),
        max_length=20,
        choices=BookingStatus.choices,
        default=BookingStatus.PENDING,
    )
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)
    updated_at = models.DateTimeField(_("updated at"), auto_now=True)
    approved_at = models.DateTimeField(_("approved at"), null=True, blank=True)
    rejected_at = models.DateTimeField(_("rejected at"), null=True, blank=True)
    confirmed_at = models.DateTimeField(_("confirmed at"), null=True, blank=True)

    class Meta:
        verbose_name = _("Booking")
        verbose_name_plural = _("Bookings")
        ordering = ["-created_at"]

    def __str__(self):
        return f"Booking #{self.pk} - {self.tenant} -> {self.bed} [{self.status}]"
