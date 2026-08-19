"""
Model-level tests for Booking.

Covers: relationships, __str__, status defaults, helper properties, and
the database-level `unique_active_booking_per_bed` constraint.
"""

from __future__ import annotations

import pytest
from django.db import IntegrityError

from stayease.bookings.models import Booking
from stayease.bookings.models import BookingStatus
from stayease.bookings.tests.factories import BookingFactory
from stayease.properties.tests.factories import BedFactory

pytestmark = pytest.mark.django_db


class TestBookingModel:
    def test_str(self):
        booking = BookingFactory(pk=123, status=BookingStatus.PENDING)
        expected = f"Booking #123 - {booking.tenant} -> {booking.bed} [PENDING]"
        assert str(booking) == expected

    def test_belongs_to_tenant_and_bed(self):
        booking = BookingFactory()
        assert booking.tenant is not None
        assert booking.bed is not None

    def test_status_default_pending(self):
        booking = BookingFactory()
        assert booking.status == BookingStatus.PENDING

    def test_timestamps_and_approval_fields(self):
        booking = BookingFactory()
        assert booking.created_at is not None
        assert booking.updated_at is not None
        assert booking.approved_at is None
        assert booking.rejected_at is None
        assert booking.confirmed_at is None

    def test_is_active_booking_property(self):
        # Active states: PENDING, APPROVED, PAYMENT_PENDING, CONFIRMED
        b1 = BookingFactory(status=BookingStatus.PENDING)
        b2 = BookingFactory(status=BookingStatus.APPROVED)
        b3 = BookingFactory(status=BookingStatus.PAYMENT_PENDING)
        b4 = BookingFactory(status=BookingStatus.CONFIRMED)
        b5 = BookingFactory(status=BookingStatus.REJECTED)

        assert b1.is_active_booking is True
        assert b2.is_active_booking is True
        assert b3.is_active_booking is True
        assert b4.is_active_booking is True
        assert b5.is_active_booking is False

    def test_pg_property(self):
        booking = BookingFactory()
        assert booking.pg == booking.bed.room.pg


class TestBookingConstraints:
    def test_only_one_active_booking_per_bed(self):
        """
        Verify that multiple active bookings (e.g. PENDING) on the same bed 
        raise IntegrityError at the database level.
        """
        bed = BedFactory()
        # First active booking
        BookingFactory(bed=bed, status=BookingStatus.PENDING)

        # Attempt to create second active booking on same bed
        with pytest.raises(IntegrityError):
            Booking.objects.create(
                tenant=BookingFactory().tenant,
                bed=bed,
                status=BookingStatus.PENDING,
            )

    @pytest.mark.parametrize(
        ("status1", "status2"),
        [
            (BookingStatus.PENDING, BookingStatus.APPROVED),
            (BookingStatus.APPROVED, BookingStatus.PAYMENT_PENDING),
            (BookingStatus.PAYMENT_PENDING, BookingStatus.CONFIRMED),
            (BookingStatus.CONFIRMED, BookingStatus.PENDING),
        ],
    )
    def test_active_states_conflict(self, status1, status2):
        """Any mix of active statuses on the same bed must raise IntegrityError."""
        bed = BedFactory()
        BookingFactory(bed=bed, status=status1)

        with pytest.raises(IntegrityError):
            Booking.objects.create(
                tenant=BookingFactory().tenant,
                bed=bed,
                status=status2,
            )

    def test_rejected_booking_does_not_conflict(self):
        """REJECTED bookings are not active, so they do not block new bookings."""
        bed = BedFactory()

        # REJECTED booking doesn't block PENDING booking
        BookingFactory(bed=bed, status=BookingStatus.REJECTED)
        BookingFactory(bed=bed, status=BookingStatus.PENDING)

        # REJECTED booking doesn't block another REJECTED booking
        BookingFactory(bed=bed, status=BookingStatus.REJECTED)
