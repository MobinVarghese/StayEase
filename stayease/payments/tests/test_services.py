"""
Tests for the payment service layer.

Covers:
- Eligible payment initiation
- Wrong tenant rejection
- Non-APPROVED booking rejection
- Duplicate payment prevention
- Successful dummy payment processing
- Failed dummy payment processing
- Booking state transitions
"""

from __future__ import annotations

import pytest
from django.core.exceptions import PermissionDenied
from django.core.exceptions import ValidationError

from stayease.bookings.models import Booking
from stayease.bookings.models import BookingStatus
from stayease.bookings.tests.factories import BookingFactory
from stayease.notifications.models import Notification
from stayease.payments.models import PaymentStatus
from stayease.payments.services import initiate_payment
from stayease.payments.services import process_dummy_payment
from stayease.payments.tests.factories import PaymentFactory
from stayease.users.models import UserRole
from stayease.users.tests.factories import UserFactory

pytestmark = pytest.mark.django_db


# ======================================================================
# initiate_payment
# ======================================================================


class TestInitiatePayment:
    def test_creates_payment_for_approved_booking(self):
        booking = BookingFactory(status=BookingStatus.APPROVED)
        tenant = booking.tenant

        payment = initiate_payment(booking=booking, user=tenant)

        assert payment.pk is not None
        assert payment.booking == booking
        assert payment.amount == booking.bed.rent_per_month
        assert payment.status == PaymentStatus.PENDING
        assert payment.transaction_ref.startswith("TXN-")

        # Booking should now be PAYMENT_PENDING
        booking.refresh_from_db()
        assert booking.status == BookingStatus.PAYMENT_PENDING

    def test_rejects_wrong_tenant(self):
        booking = BookingFactory(status=BookingStatus.APPROVED)
        other_user = UserFactory(role=UserRole.TENANT)

        with pytest.raises(PermissionDenied):
            initiate_payment(booking=booking, user=other_user)

    def test_rejects_non_approved_booking(self):
        booking = BookingFactory(status=BookingStatus.PENDING)
        tenant = booking.tenant

        with pytest.raises(ValidationError, match="approved"):
            initiate_payment(booking=booking, user=tenant)

    def test_rejects_duplicate_payment(self):
        """Once a payment exists for a booking, another cannot be created."""
        booking = BookingFactory(status=BookingStatus.APPROVED)
        tenant = booking.tenant

        # First payment succeeds
        initiate_payment(booking=booking, user=tenant)

        # Refresh to get updated status
        booking.refresh_from_db()

        # Second payment fails
        with pytest.raises(ValidationError, match="already exists"):
            initiate_payment(booking=booking, user=tenant)


# ======================================================================
# process_dummy_payment
# ======================================================================


class TestProcessDummyPaymentSuccess:
    def test_success_confirms_booking(self):
        booking = BookingFactory(status=BookingStatus.APPROVED)
        tenant = booking.tenant

        payment = initiate_payment(booking=booking, user=tenant)

        result = process_dummy_payment(
            payment=payment,
            user=tenant,
            simulate_success=True,
        )

        assert result.status == PaymentStatus.SUCCESS
        booking.refresh_from_db()
        assert booking.status == BookingStatus.CONFIRMED

    def test_success_creates_notification(self):
        booking = BookingFactory(status=BookingStatus.APPROVED)
        tenant = booking.tenant

        payment = initiate_payment(booking=booking, user=tenant)
        process_dummy_payment(
            payment=payment,
            user=tenant,
            simulate_success=True,
        )

        # Should have a notification about successful payment
        assert Notification.objects.filter(
            recipient=tenant,
            booking=booking,
        ).exists()


class TestProcessDummyPaymentFailure:
    def test_failure_marks_payment_failed(self):
        booking = BookingFactory(status=BookingStatus.APPROVED)
        tenant = booking.tenant

        payment = initiate_payment(booking=booking, user=tenant)

        result = process_dummy_payment(
            payment=payment,
            user=tenant,
            simulate_success=False,
        )

        assert result.status == PaymentStatus.FAILED
        # Booking stays PAYMENT_PENDING on failure
        booking.refresh_from_db()
        assert booking.status == BookingStatus.PAYMENT_PENDING

    def test_failure_does_not_create_confirmation_notification(self):
        booking = BookingFactory(status=BookingStatus.APPROVED)
        tenant = booking.tenant

        payment = initiate_payment(booking=booking, user=tenant)
        process_dummy_payment(
            payment=payment,
            user=tenant,
            simulate_success=False,
        )

        # No "confirmed" notification
        notifications = Notification.objects.filter(
            recipient=tenant,
            booking=booking,
        )
        for n in notifications:
            assert "confirmed" not in n.message.lower()


class TestProcessDummyPaymentAuth:
    def test_rejects_wrong_user(self):
        booking = BookingFactory(status=BookingStatus.APPROVED)
        tenant = booking.tenant
        other_user = UserFactory(role=UserRole.TENANT)

        payment = initiate_payment(booking=booking, user=tenant)

        with pytest.raises(PermissionDenied):
            process_dummy_payment(
                payment=payment,
                user=other_user,
                simulate_success=True,
            )

    def test_rejects_already_processed_payment(self):
        booking = BookingFactory(status=BookingStatus.APPROVED)
        tenant = booking.tenant

        payment = initiate_payment(booking=booking, user=tenant)
        process_dummy_payment(
            payment=payment,
            user=tenant,
            simulate_success=True,
        )

        # Second processing attempt should fail
        with pytest.raises(ValidationError, match="already been processed"):
            process_dummy_payment(
                payment=payment,
                user=tenant,
                simulate_success=True,
            )
