"""
Tests for booking confirmation email notifications.

Covers:
- Sending multi-part (HTML + text) booking confirmation email
- Subject and body content validation
- State validation: refusing non-CONFIRMED bookings
- Payment validation: refusing non-SUCCESS payments
- Duplicate-send prevention via cache
- Integration with process_dummy_payment flow
"""

from __future__ import annotations

import pytest
from django.core import mail
from django.core.cache import cache

from stayease.bookings.models import BookingStatus
from stayease.bookings.tests.factories import BookingFactory
from stayease.notifications.services import send_booking_confirmation_email
from stayease.payments.models import PaymentStatus
from stayease.payments.services import initiate_payment
from stayease.payments.services import process_dummy_payment
from stayease.payments.tests.factories import PaymentFactory

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.fixture(autouse=True)
def _clear_cache_and_outbox():
    """Ensure clean cache and email outbox for each test."""
    cache.clear()
    mail.outbox.clear()
    yield
    cache.clear()
    mail.outbox.clear()


class TestBookingConfirmationEmail:
    """Test send_booking_confirmation_email service."""

    def test_send_booking_confirmation_email_success(self):
        """Confirmed booking with successful payment sends a rich email."""
        booking = BookingFactory(status=BookingStatus.CONFIRMED)
        payment = PaymentFactory(
            booking=booking,
            amount=booking.bed.rent_per_month,
            status=PaymentStatus.SUCCESS,
            transaction_ref="TXN-DEMO-12345",
        )

        success = send_booking_confirmation_email(booking)
        assert success is True

        # Check outbox
        assert len(mail.outbox) == 1
        email = mail.outbox[0]

        # Recipient & Subject
        assert email.to == [booking.tenant.email]
        assert "Booking Confirmed" in email.subject
        assert booking.bed.room.pg.name in email.subject
        assert f"#{booking.id}" in email.subject

        # Plain text content
        assert str(booking.id) in email.body
        assert booking.bed.room.pg.name in email.body
        assert booking.bed.label in email.body
        assert str(booking.bed.room.room_number) in email.body
        assert f"₹{payment.amount}" in email.body
        assert "TXN-DEMO-12345" in email.body
        assert booking.bed.room.pg.owner.email in email.body

        # HTML alternative
        alternatives = getattr(email, "alternatives", [])
        assert len(alternatives) == 1
        html_content, mime_type = alternatives[0]
        assert mime_type == "text/html"
        html_str = str(html_content)
        assert "StayEase" in html_str
        assert booking.bed.room.pg.name in html_str
        assert "Booking Reference" in html_str
        assert f"#{booking.id}" in html_str

    def test_refuses_non_confirmed_booking(self):
        """Booking in PENDING status must NOT trigger a confirmation email."""
        booking = BookingFactory(status=BookingStatus.PENDING)
        PaymentFactory(booking=booking, status=PaymentStatus.SUCCESS)

        success = send_booking_confirmation_email(booking)
        assert success is False
        assert len(mail.outbox) == 0

    def test_refuses_failed_payment(self):
        """Booking with failed payment must NOT trigger a confirmation email."""
        booking = BookingFactory(status=BookingStatus.CONFIRMED)
        PaymentFactory(booking=booking, status=PaymentStatus.FAILED)

        success = send_booking_confirmation_email(booking)
        assert success is False
        assert len(mail.outbox) == 0

    def test_duplicate_send_prevention(self):
        """Calling send_booking_confirmation_email twice skips the second send."""
        booking = BookingFactory(status=BookingStatus.CONFIRMED)
        PaymentFactory(booking=booking, status=PaymentStatus.SUCCESS)

        # First call succeeds
        assert send_booking_confirmation_email(booking) is True
        assert len(mail.outbox) == 1

        # Second call is prevented by duplicate guard
        assert send_booking_confirmation_email(booking) is False
        assert len(mail.outbox) == 1


class TestPaymentIntegrationEmailTrigger:
    """Test process_dummy_payment triggers confirmation email on success."""

    def test_successful_payment_sends_email(self):
        """Successful payment initiates booking confirmation and sends email."""
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

        # Email should have been sent via transaction.on_commit
        assert len(mail.outbox) == 1
        email = mail.outbox[0]
        assert email.to == [tenant.email]
        assert "Booking Confirmed" in email.subject

    def test_failed_payment_does_not_send_email(self):
        """Failed payment must NOT send confirmation email."""
        booking = BookingFactory(status=BookingStatus.APPROVED)
        tenant = booking.tenant

        payment = initiate_payment(booking=booking, user=tenant)
        result = process_dummy_payment(
            payment=payment,
            user=tenant,
            simulate_success=False,
        )

        assert result.status == PaymentStatus.FAILED
        assert len(mail.outbox) == 0
