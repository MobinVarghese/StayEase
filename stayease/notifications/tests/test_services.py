"""
Tests for the notification service layer.

Covers:
- Notification creation
- Correct recipient for booking events
- Read/unread state management
- Unauthorized access prevention
- Query helpers
"""

from __future__ import annotations

import pytest

from stayease.bookings.models import BookingStatus
from stayease.bookings.tests.factories import BookingFactory
from stayease.notifications.models import Notification
from stayease.notifications.services import (
    create_notification,
    get_unread_count,
    get_user_notifications,
    mark_all_read,
    mark_notification_read,
    notify_booking_approved,
    notify_booking_rejected,
    notify_booking_requested,
    notify_payment_successful,
)
from stayease.notifications.tests.factories import NotificationFactory
from stayease.users.models import UserRole
from stayease.users.tests.factories import UserFactory

pytestmark = pytest.mark.django_db


# ======================================================================
# create_notification
# ======================================================================


class TestCreateNotification:
    def test_creates_notification(self):
        user = UserFactory()
        n = create_notification(recipient=user, message="Hello")
        assert n.pk is not None
        assert n.recipient == user
        assert n.message == "Hello"
        assert n.is_read is False
        assert n.booking is None

    def test_creates_notification_with_booking(self):
        booking = BookingFactory()
        n = create_notification(
            recipient=booking.tenant,
            message="Test",
            booking=booking,
        )
        assert n.booking == booking


# ======================================================================
# Booking-event notification helpers
# ======================================================================


class TestNotifyBookingRequested:
    def test_notifies_owner(self):
        booking = BookingFactory()
        owner = booking.bed.room.pg.owner
        n = notify_booking_requested(booking)
        assert n.recipient == owner
        assert n.booking == booking
        assert booking.bed.label in n.message
        assert booking.bed.room.pg.name in n.message

    def test_does_not_notify_tenant(self):
        booking = BookingFactory()
        n = notify_booking_requested(booking)
        assert n.recipient != booking.tenant


class TestNotifyBookingApproved:
    def test_notifies_tenant(self):
        booking = BookingFactory(status=BookingStatus.APPROVED)
        n = notify_booking_approved(booking)
        assert n.recipient == booking.tenant
        assert n.booking == booking
        assert "approved" in n.message.lower()

    def test_message_contains_pg_name(self):
        booking = BookingFactory(status=BookingStatus.APPROVED)
        n = notify_booking_approved(booking)
        assert booking.bed.room.pg.name in n.message


class TestNotifyBookingRejected:
    def test_notifies_tenant(self):
        booking = BookingFactory(status=BookingStatus.REJECTED)
        n = notify_booking_rejected(booking)
        assert n.recipient == booking.tenant
        assert "rejected" in n.message.lower()


class TestNotifyPaymentSuccessful:
    def test_notifies_tenant(self):
        booking = BookingFactory(status=BookingStatus.CONFIRMED)
        n = notify_payment_successful(booking)
        assert n.recipient == booking.tenant
        assert "confirmed" in n.message.lower()


# ======================================================================
# Query helpers
# ======================================================================


class TestGetUserNotifications:
    def test_returns_only_users_notifications(self):
        user1 = UserFactory()
        user2 = UserFactory()
        NotificationFactory(recipient=user1)
        NotificationFactory(recipient=user1)
        NotificationFactory(recipient=user2)

        qs = get_user_notifications(user1)
        assert qs.count() == 2
        assert all(n.recipient == user1 for n in qs)

    def test_returns_newest_first(self):
        user = UserFactory()
        n1 = NotificationFactory(recipient=user)
        n2 = NotificationFactory(recipient=user)

        qs = list(get_user_notifications(user))
        assert qs[0].pk == n2.pk
        assert qs[1].pk == n1.pk


class TestGetUnreadCount:
    def test_counts_unread_only(self):
        user = UserFactory()
        NotificationFactory(recipient=user, is_read=False)
        NotificationFactory(recipient=user, is_read=False)
        NotificationFactory(recipient=user, is_read=True)

        assert get_unread_count(user) == 2

    def test_returns_zero_when_all_read(self):
        user = UserFactory()
        NotificationFactory(recipient=user, is_read=True)
        assert get_unread_count(user) == 0

    def test_returns_zero_when_no_notifications(self):
        user = UserFactory()
        assert get_unread_count(user) == 0


# ======================================================================
# Read-state management
# ======================================================================


class TestMarkNotificationRead:
    def test_marks_as_read(self):
        user = UserFactory()
        n = NotificationFactory(recipient=user, is_read=False)
        result = mark_notification_read(n, user)
        n.refresh_from_db()
        assert n.is_read is True
        assert result.is_read is True

    def test_idempotent_when_already_read(self):
        user = UserFactory()
        n = NotificationFactory(recipient=user, is_read=True)
        result = mark_notification_read(n, user)
        n.refresh_from_db()
        assert n.is_read is True
        assert result.is_read is True

    def test_rejects_wrong_user(self):
        user1 = UserFactory()
        user2 = UserFactory()
        n = NotificationFactory(recipient=user1, is_read=False)
        with pytest.raises(PermissionError):
            mark_notification_read(n, user2)
        n.refresh_from_db()
        assert n.is_read is False


class TestMarkAllRead:
    def test_marks_all_unread_as_read(self):
        user = UserFactory()
        NotificationFactory(recipient=user, is_read=False)
        NotificationFactory(recipient=user, is_read=False)
        NotificationFactory(recipient=user, is_read=True)

        count = mark_all_read(user)
        assert count == 2
        assert Notification.objects.filter(recipient=user, is_read=False).count() == 0

    def test_does_not_affect_other_users(self):
        user1 = UserFactory()
        user2 = UserFactory()
        NotificationFactory(recipient=user1, is_read=False)
        NotificationFactory(recipient=user2, is_read=False)

        mark_all_read(user1)
        assert Notification.objects.filter(recipient=user2, is_read=False).count() == 1

    def test_returns_zero_when_nothing_to_mark(self):
        user = UserFactory()
        assert mark_all_read(user) == 0
