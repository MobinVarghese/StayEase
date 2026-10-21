"""
Tests for Post-Checkout Availability Management.

Verifies:
- Only owners of the PG can check out tenants.
- Only CONFIRMED bookings can be checked out.
- Checkout transitions booking status to COMPLETED and sets checked_out_at.
- Bed is_available is restored to True and bed is no longer occupied.
- Multi-bed rooms isolate occupancy correctly (other beds remain occupied).
- Bed can be re-booked by a new tenant after checkout.
- Cannot check out already completed, pending, approved, or rejected bookings.
- Tenant and unauthorized owner cannot perform checkout.
"""

from __future__ import annotations

from django.core.exceptions import PermissionDenied
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from stayease.bookings.models import Booking
from stayease.bookings.models import BookingStatus
from stayease.bookings.services import checkout_booking
from stayease.bookings.tests.factories import BookingFactory
from stayease.properties.tests.factories import BedFactory
from stayease.properties.tests.factories import PGFactory
from stayease.properties.tests.factories import RoomFactory
from stayease.users.models import UserRole
from stayease.users.tests.factories import UserFactory


class CheckoutServiceTests(TestCase):
    """Unit tests for checkout_booking service function."""

    def setUp(self):
        self.owner = UserFactory(role=UserRole.OWNER)
        self.other_owner = UserFactory(role=UserRole.OWNER)
        self.tenant = UserFactory(role=UserRole.TENANT, first_name="Aarav", last_name="Kumar")
        self.pg = PGFactory(owner=self.owner)
        self.room = RoomFactory(pg=self.pg, capacity=2, room_type="Double")
        self.bed_a = BedFactory(room=self.room, label="Bed A", is_available=False)
        self.bed_b = BedFactory(room=self.room, label="Bed B", is_available=False)

        # Confirmed booking for tenant on bed_a
        self.booking = BookingFactory(
            tenant=self.tenant,
            bed=self.bed_a,
            status=BookingStatus.CONFIRMED,
            confirmed_at=timezone.now(),
        )

    def test_owner_checkout_success(self):
        """PG owner can successfully check out a confirmed tenant."""
        self.assertTrue(self.bed_a.is_occupied)
        self.assertFalse(self.bed_a.is_available)
        self.assertIsNone(self.booking.checked_out_at)

        completed_booking = checkout_booking(booking=self.booking, owner=self.owner)

        self.assertEqual(completed_booking.status, BookingStatus.COMPLETED)
        self.assertIsNotNone(completed_booking.checked_out_at)
        self.assertTrue(completed_booking.is_completed)
        self.assertTrue(completed_booking.can_be_reviewed)

        # Bed availability restored
        self.bed_a.refresh_from_db()
        self.assertTrue(self.bed_a.is_available)
        self.assertFalse(self.bed_a.is_occupied)

    def test_multi_bed_room_isolation_on_checkout(self):
        """Checking out Bed A frees Bed A while Bed B remains occupied."""
        tenant_b = UserFactory(role=UserRole.TENANT)
        booking_b = BookingFactory(
            tenant=tenant_b,
            bed=self.bed_b,
            status=BookingStatus.CONFIRMED,
            confirmed_at=timezone.now(),
        )

        self.assertTrue(self.bed_a.is_occupied)
        self.assertTrue(self.bed_b.is_occupied)

        # Check out Bed A
        checkout_booking(booking=self.booking, owner=self.owner)

        self.bed_a.refresh_from_db()
        self.bed_b.refresh_from_db()

        # Bed A is now available and unoccupied
        self.assertTrue(self.bed_a.is_available)
        self.assertFalse(self.bed_a.is_occupied)

        # Bed B is still occupied and unavailable
        self.assertFalse(self.bed_b.is_available)
        self.assertTrue(self.bed_b.is_occupied)

    def test_bed_can_be_rebooked_after_checkout(self):
        """After checkout, a new tenant can book the newly freed bed."""
        checkout_booking(booking=self.booking, owner=self.owner)

        new_tenant = UserFactory(role=UserRole.TENANT)
        new_booking = BookingFactory(
            tenant=new_tenant,
            bed=self.bed_a,
            status=BookingStatus.PENDING,
        )
        self.assertEqual(new_booking.bed, self.bed_a)
        self.assertEqual(new_booking.status, BookingStatus.PENDING)

    def test_unauthorized_owner_cannot_checkout(self):
        """Another owner cannot check out a booking in a PG they do not own."""
        with self.assertRaises(PermissionDenied):
            checkout_booking(booking=self.booking, owner=self.other_owner)

        self.booking.refresh_from_db()
        self.assertEqual(self.booking.status, BookingStatus.CONFIRMED)

    def test_tenant_cannot_checkout_self(self):
        """Tenants cannot check themselves out via the service."""
        with self.assertRaises(PermissionDenied):
            checkout_booking(booking=self.booking, owner=self.tenant)

    def test_cannot_checkout_non_confirmed_booking(self):
        """Bookings in PENDING, APPROVED, or REJECTED status cannot be checked out."""
        for invalid_status in [
            BookingStatus.PENDING,
            BookingStatus.APPROVED,
            BookingStatus.PAYMENT_PENDING,
            BookingStatus.REJECTED,
        ]:
            bed = BedFactory(room=self.room)
            b = BookingFactory(
                tenant=self.tenant,
                bed=bed,
                status=invalid_status,
            )
            with self.assertRaises(ValidationError) as ctx:
                checkout_booking(booking=b, owner=self.owner)
            self.assertIn("Only confirmed bookings can be checked out", str(ctx.exception))

    def test_cannot_checkout_already_completed_booking(self):
        """Repeated checkout on an already COMPLETED booking raises ValidationError."""
        checkout_booking(booking=self.booking, owner=self.owner)
        self.booking.refresh_from_db()

        with self.assertRaises(ValidationError) as ctx:
            checkout_booking(booking=self.booking, owner=self.owner)
        self.assertIn("already been checked out", str(ctx.exception))


class BookingCheckoutViewTests(TestCase):
    """Integration tests for BookingCheckoutView HTTP endpoint."""

    def setUp(self):
        self.owner = UserFactory(role=UserRole.OWNER)
        self.other_owner = UserFactory(role=UserRole.OWNER)
        self.tenant = UserFactory(role=UserRole.TENANT)
        self.pg = PGFactory(owner=self.owner)
        self.room = RoomFactory(pg=self.pg, capacity=1, room_type="Single")
        self.bed = BedFactory(room=self.room, is_available=False)
        self.booking = BookingFactory(
            tenant=self.tenant,
            bed=self.bed,
            status=BookingStatus.CONFIRMED,
            confirmed_at=timezone.now(),
        )
        self.checkout_url = reverse("bookings:booking_checkout", kwargs={"pk": self.booking.pk})

    def test_owner_post_checkout_success(self):
        """Owner POST successfully checks out tenant and redirects to detail view."""
        self.client.force_login(self.owner)
        response = self.client.post(self.checkout_url)

        self.assertRedirects(
            response,
            reverse("bookings:booking_detail", kwargs={"pk": self.booking.pk}),
        )

        self.booking.refresh_from_db()
        self.bed.refresh_from_db()
        self.assertEqual(self.booking.status, BookingStatus.COMPLETED)
        self.assertTrue(self.bed.is_available)
        self.assertFalse(self.bed.is_occupied)

    def test_other_owner_post_checkout_forbidden(self):
        """Another owner POSTing checkout is redirected with error."""
        self.client.force_login(self.other_owner)
        response = self.client.post(self.checkout_url)

        self.assertRedirects(response, reverse("bookings:owner_booking_list"))
        self.booking.refresh_from_db()
        self.assertEqual(self.booking.status, BookingStatus.CONFIRMED)

    def test_tenant_cannot_post_checkout(self):
        """Tenant cannot POST checkout (requires OWNER role)."""
        self.client.force_login(self.tenant)
        response = self.client.post(self.checkout_url)
        # OwnerRequiredMixin redirects or returns 403
        self.assertNotEqual(response.status_code, 200)
        self.booking.refresh_from_db()
        self.assertEqual(self.booking.status, BookingStatus.CONFIRMED)

    def test_anonymous_user_redirected_to_login(self):
        """Unauthenticated user is redirected to login."""
        response = self.client.post(self.checkout_url)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response["Location"])

    def test_get_method_not_allowed(self):
        """GET request to checkout view returns 405 Method Not Allowed."""
        self.client.force_login(self.owner)
        response = self.client.get(self.checkout_url)
        self.assertEqual(response.status_code, 405)
