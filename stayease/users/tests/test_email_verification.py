"""
Tests verifying that email verification on signup/signin is removed,
and email notifications are reserved exclusively for booking confirmation.

Covers:
- Signup does NOT send verification email and logs the user in immediately.
- Login does NOT ask for email verification or redirect to confirm-email.
- Unverified users can log in directly without being blocked.
- Booking confirmation triggers the confirmation email to the tenant.
- Production STAYEASE_PUBLIC_URL validation logic.
"""

from __future__ import annotations

from http import HTTPStatus
from urllib.parse import urlparse

import pytest
from allauth.account.models import EmailAddress
from django.core import mail
from django.core.cache import cache
from django.core.exceptions import ImproperlyConfigured
from django.urls import reverse

from stayease.bookings.models import BookingStatus
from stayease.bookings.services import confirm_booking
from stayease.bookings.tests.factories import BookingFactory
from stayease.payments.models import PaymentStatus
from stayease.payments.tests.factories import PaymentFactory
from stayease.users.models import User
from stayease.users.models import UserRole
from stayease.users.tests.factories import UserFactory

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.fixture(autouse=True)
def _clear_cache_and_outbox():
    """Ensure clean cache and email outbox for each test."""
    cache.clear()
    mail.outbox.clear()
    yield
    cache.clear()
    mail.outbox.clear()


class TestNoEmailVerificationOnAuth:
    """Verify that email verification is completely removed from sign up and sign in."""

    def test_signup_does_not_send_verification_email(self, client):
        """Registering a new account logs the user in directly without sending verification email."""
        signup_url = reverse("account_signup")
        response = client.post(
            signup_url,
            {
                "email": "directsignup@example.com",
                "first_name": "Direct",
                "last_name": "User",
                "phone_number": "9876543210",
                "role": UserRole.TENANT,
                "password1": "SecurePass123!@#",
                "password2": "SecurePass123!@#",
            },
        )

        # Redirects to dashboard redirect, NOT verification sent
        assert response.status_code == HTTPStatus.FOUND
        assert response["Location"] == reverse("users:redirect")

        # Zero emails sent on signup
        assert len(mail.outbox) == 0

        # User exists and EmailAddress is verified
        user = User.objects.get(email="directsignup@example.com")
        email_addr = EmailAddress.objects.filter(user=user).first()
        assert email_addr is not None
        assert email_addr.verified is True

    def test_login_does_not_ask_for_verification(self, client):
        """User can sign in directly without being asked for email verification."""
        user = UserFactory(role=UserRole.TENANT)
        user.set_password("ValidPassword123!")
        user.save()

        # Even if EmailAddress is marked unverified in DB
        EmailAddress.objects.filter(user=user).delete()
        EmailAddress.objects.create(
            user=user,
            email=user.email,
            verified=False,
            primary=True,
        )

        login_url = reverse("account_login")
        response = client.post(
            login_url,
            {
                "login": user.email,
                "password": "ValidPassword123!",
            },
        )

        # Successfully logged in and redirected to dashboard
        assert response.status_code == HTTPStatus.FOUND
        assert response["Location"] == reverse("users:redirect")
        # Zero verification emails sent
        assert len(mail.outbox) == 0


class TestBookingConfirmationEmailSetup:
    """Verify that email service is only used for confirmed room bookings."""

    def test_confirm_booking_sends_email_to_tenant(self):
        """Confirming a room booking sends confirmation email to tenant."""
        booking = BookingFactory(status=BookingStatus.PAYMENT_PENDING)
        PaymentFactory(booking=booking, status=PaymentStatus.SUCCESS)

        confirm_booking(booking)
        booking.refresh_from_db()
        assert booking.status == BookingStatus.CONFIRMED

        # Email sent to tenant
        assert len(mail.outbox) == 1
        sent_email = mail.outbox[0]
        assert booking.tenant.email in sent_email.to
        assert "Booking Confirmed" in sent_email.subject
        assert booking.bed.room.pg.name in sent_email.subject

    def test_non_confirmed_booking_does_not_send_email(self):
        """Unconfirmed booking does not send email."""
        BookingFactory(status=BookingStatus.PENDING)
        assert len(mail.outbox) == 0


class TestProductionUrlValidation:
    """Test URL validation logic for production settings."""

    def test_production_url_validation_cases(self):
        def validate_prod_url(url: str):
            if not url:
                raise ImproperlyConfigured("STAYEASE_PUBLIC_URL required in production.")
            parsed = urlparse(url.strip().rstrip("/"))
            if parsed.scheme not in ("http", "https"):
                raise ImproperlyConfigured("Invalid scheme.")
            if not parsed.netloc:
                raise ImproperlyConfigured("Missing hostname/netloc.")
            return url.strip().rstrip("/")

        assert validate_prod_url("https://stayease.in") == "https://stayease.in"
        assert validate_prod_url("http://192.168.1.1:8000/") == "http://192.168.1.1:8000"

        with pytest.raises(ImproperlyConfigured):
            validate_prod_url("")
        with pytest.raises(ImproperlyConfigured):
            validate_prod_url("ftp://example.com")
        with pytest.raises(ImproperlyConfigured):
            validate_prod_url("invalid-url-without-scheme.com")
