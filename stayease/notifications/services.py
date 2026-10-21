"""
Notification service layer.

All notification operations go through this module. Views and other
consumers call these functions rather than manipulating the Notification
model directly.

Business logic ownership: Member 5
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from django.conf import settings
from django.core.cache import cache
from django.core.mail import EmailMultiAlternatives
from django.db.models import QuerySet
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from stayease.notifications.models import Notification

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from stayease.bookings.models import Booking
    from stayease.users.models import User


# ======================================================================
# Notification creation
# ======================================================================


def create_notification(
    *,
    recipient: User,
    message: str,
    booking: Booking | None = None,
) -> Notification:
    """
    Create a new notification for *recipient*.

    Parameters
    ----------
    recipient
        The user who will see this notification.
    message
        Human-readable notification text.
    booking
        Optional booking this notification relates to.

    Returns
    -------
    Notification
        The newly created notification (unread by default).
    """
    return Notification.objects.create(
        recipient=recipient,
        message=message,
        booking=booking,
    )


# ======================================================================
# Booking-event notification helpers
# ======================================================================


def notify_booking_requested(booking: Booking) -> Notification:
    """
    Notify the PG owner that a tenant has requested a booking.

    Called after ``create_booking_request()`` succeeds.
    """
    owner = booking.bed.room.pg.owner
    message = (
        f"{booking.tenant.name or booking.tenant.email} requested "
        f"{booking.bed.label} in Room {booking.bed.room.room_number} "
        f"at {booking.bed.room.pg.name}."
    )
    return create_notification(
        recipient=owner,
        message=message,
        booking=booking,
    )


def notify_booking_approved(booking: Booking) -> Notification:
    """
    Notify the tenant that their booking request has been approved.

    Called after ``approve_booking()`` succeeds.
    """
    message = (
        f"Your booking request for {booking.bed.label} in "
        f"Room {booking.bed.room.room_number} at "
        f"{booking.bed.room.pg.name} has been approved. "
        f"Please proceed to payment."
    )
    return create_notification(
        recipient=booking.tenant,
        message=message,
        booking=booking,
    )


def notify_booking_rejected(booking: Booking) -> Notification:
    """
    Notify the tenant that their booking request has been rejected.

    Called after ``reject_booking()`` succeeds.
    """
    message = (
        f"Your booking request for {booking.bed.label} in "
        f"Room {booking.bed.room.room_number} at "
        f"{booking.bed.room.pg.name} has been rejected."
    )
    return create_notification(
        recipient=booking.tenant,
        message=message,
        booking=booking,
    )


def notify_payment_successful(booking: Booking) -> Notification:
    """
    Notify the tenant that their payment was successful and booking is confirmed.

    Called after ``confirm_booking()`` succeeds.
    """
    message = (
        f"Payment successful! Your booking for {booking.bed.label} in "
        f"Room {booking.bed.room.room_number} at "
        f"{booking.bed.room.pg.name} is now confirmed."
    )
    return create_notification(
        recipient=booking.tenant,
        message=message,
        booking=booking,
    )


def notify_checkout_completed(booking: Booking) -> Notification:
    """
    Notify the tenant that their stay has been completed and they are checked out.

    Called after ``checkout_booking()`` succeeds.
    """
    message = (
        f"You have been successfully checked out of {booking.bed.label} in "
        f"Room {booking.bed.room.room_number} at "
        f"{booking.bed.room.pg.name}. You can now leave a review of your stay!"
    )
    return create_notification(
        recipient=booking.tenant,
        message=message,
        booking=booking,
    )


def send_booking_confirmation_email(booking: Booking) -> bool:
    """
    Send a confirmation email to the tenant after their booking is confirmed.

    Validates that:
    1. The booking status is CONFIRMED.
    2. The payment has succeeded.
    3. Duplicate sends are prevented via atomic cache lock.

    Returns True if email was sent successfully, False otherwise.
    """
    from stayease.bookings.models import Booking as BookingModel
    from stayease.bookings.models import BookingStatus
    from stayease.payments.models import PaymentStatus

    # Reload booking to ensure fresh database state and pre-fetch relations
    try:
        fresh_booking = (
            BookingModel.objects.select_related(
                "tenant",
                "bed__room__pg__owner",
                "payment",
            ).get(pk=booking.pk)
        )
    except BookingModel.DoesNotExist:
        logger.error(
            "Booking %s not found when attempting to send confirmation email.",
            getattr(booking, "pk", None),
        )
        return False

    # 1. State validation: booking must be CONFIRMED
    if fresh_booking.status != BookingStatus.CONFIRMED:
        logger.warning(
            "Refusing to send confirmation email for booking %s: status is '%s', expected CONFIRMED.",
            fresh_booking.pk,
            fresh_booking.status,
        )
        return False

    # 2. Payment validation: payment must be SUCCESS
    payment = getattr(fresh_booking, "payment", None)
    if payment and payment.status != PaymentStatus.SUCCESS:
        logger.warning(
            "Refusing to send confirmation email for booking %s: payment status is '%s', expected SUCCESS.",
            fresh_booking.pk,
            payment.status,
        )
        return False

    # 3. Duplicate prevention: atomic cache key
    lock_key = f"booking_confirmation_email_sent_{fresh_booking.pk}"
    if not cache.add(lock_key, True, timeout=60 * 60 * 24 * 30):
        logger.info(
            "Booking confirmation email already sent for booking %s. Skipping duplicate.",
            fresh_booking.pk,
        )
        return False

    # 4. Context preparation
    tenant = fresh_booking.tenant
    pg = fresh_booking.bed.room.pg
    owner = pg.owner

    site_url = getattr(settings, "STAYEASE_PUBLIC_URL", getattr(settings, "SITE_URL", "http://localhost:8000")).rstrip("/")
    booking_detail_path = reverse("bookings:booking_detail", kwargs={"pk": fresh_booking.pk})
    booking_url = f"{site_url}{booking_detail_path}"

    tenant_name = tenant.name or tenant.first_name or tenant.email
    owner_name = owner.name or owner.first_name or owner.email
    bed_rent = getattr(fresh_booking.bed, "rent_per_month", "")
    payment_amount = payment.amount if payment else bed_rent
    transaction_ref = getattr(payment, "transaction_ref", "")

    context = {
        "booking": fresh_booking,
        "tenant_name": tenant_name,
        "pg": pg,
        "owner_name": owner_name,
        "owner_phone": getattr(owner, "phone_number", ""),
        "owner_email": owner.email,
        "payment_amount": payment_amount,
        "transaction_ref": transaction_ref,
        "booking_url": booking_url,
    }

    # 5. Render email templates
    subject_raw = render_to_string(
        "bookings/emails/booking_confirmation_subject.txt", context
    )
    subject = " ".join(subject_raw.splitlines()).strip()
    text_content = render_to_string(
        "bookings/emails/booking_confirmation_message.txt", context
    )
    html_content = render_to_string(
        "bookings/emails/booking_confirmation_message.html", context
    )

    from_email = getattr(settings, "DEFAULT_FROM_EMAIL", "StayEase <noreply@stayease.in>")

    # 6. Send email
    msg = EmailMultiAlternatives(
        subject=subject,
        body=text_content,
        from_email=from_email,
        to=[tenant.email],
    )
    msg.attach_alternative(html_content, "text/html")
    msg.send(fail_silently=False)

    logger.info(
        "Booking confirmation email sent to %s for booking %s.",
        tenant.email,
        fresh_booking.pk,
    )
    return True


# ======================================================================
# Query helpers
# ======================================================================


def get_user_notifications(user: User) -> QuerySet[Notification]:
    """
    Return the queryset of notifications for *user*,
    ordered newest-first with related booking pre-fetched.
    """
    return (
        Notification.objects.filter(recipient=user)
        .select_related("booking")
        .order_by("-created_at")
    )


def get_unread_count(user: User) -> int:
    """Return the count of unread notifications for *user*."""
    return Notification.objects.filter(
        recipient=user,
        is_read=False,
    ).count()


# ======================================================================
# Read-state management
# ======================================================================


def mark_notification_read(notification: Notification, user: User) -> Notification:
    """
    Mark a single notification as read.

    Only the notification's recipient may mark it as read.

    Raises
    ------
    PermissionError
        If *user* is not the notification's recipient.
    """
    if notification.recipient != user:
        raise PermissionError(
            _("You do not have permission to modify this notification.")
        )
    if not notification.is_read:
        notification.is_read = True
        notification.save(update_fields=["is_read"])
    return notification


def mark_all_read(user: User) -> int:
    """
    Mark all unread notifications for *user* as read.

    Returns the number of notifications updated.
    """
    return Notification.objects.filter(
        recipient=user,
        is_read=False,
    ).update(is_read=True)
