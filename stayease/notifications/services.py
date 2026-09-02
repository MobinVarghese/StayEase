"""
Notification service layer.

All notification operations go through this module. Views and other
consumers call these functions rather than manipulating the Notification
model directly.

Business logic ownership: Member 5
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.db.models import QuerySet
from django.utils.translation import gettext_lazy as _

from stayease.notifications.models import Notification

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
    if notification.recipient_id != user.pk:
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
