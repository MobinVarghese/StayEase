"""
Tests for Verified Tenant Reviews and Ratings.

Verifies:
- Only verified tenants with COMPLETED bookings can submit a review.
- Exactly one review allowed per booking.
- Rating must be an integer between 1 and 5.
- Tenant display name protects privacy (e.g. 'Rahul S.' or fallback, no email exposure).
- Uncompleted bookings (PENDING, APPROVED, CONFIRMED, REJECTED) cannot be reviewed.
- Unauthorized tenants cannot review another tenant's booking.
- Reviews appear on homepage via get_homepage_reviews and HomeView.
- Clean empty state rendered on homepage when no reviews exist.
"""

from __future__ import annotations

from django.core.exceptions import PermissionDenied
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from stayease.bookings.models import Booking
from stayease.bookings.models import BookingStatus
from stayease.bookings.tests.factories import BookingFactory
from stayease.properties.models import Review
from stayease.properties.services import create_review
from stayease.properties.services import get_homepage_reviews
from stayease.properties.tests.factories import BedFactory
from stayease.properties.tests.factories import PGFactory
from stayease.properties.tests.factories import RoomFactory
from stayease.users.models import UserRole
from stayease.users.tests.factories import UserFactory


class ReviewModelAndServiceTests(TestCase):
    """Unit tests for Review model validation and create_review service."""

    def setUp(self):
        self.owner = UserFactory(role=UserRole.OWNER)
        self.tenant = UserFactory(
            role=UserRole.TENANT,
            first_name="Priya",
            last_name="Nair",
            email="priya.nair@example.com",
        )
        self.other_tenant = UserFactory(role=UserRole.TENANT, email="other@example.com")
        self.pg = PGFactory(owner=self.owner, name="Greenfield Residency", city="Bengaluru")
        self.room = RoomFactory(pg=self.pg, room_number="201", capacity=1, room_type="Single")
        self.bed = BedFactory(room=self.room, is_available=True)

        # Completed booking for tenant
        self.completed_booking = BookingFactory(
            tenant=self.tenant,
            bed=self.bed,
            status=BookingStatus.COMPLETED,
            checked_out_at=timezone.now(),
        )

    def test_create_review_success(self):
        """Verified tenant with completed booking can successfully create a review."""
        review = create_review(
            booking=self.completed_booking,
            tenant=self.tenant,
            rating=5,
            comment="Excellent stay, super fast Wi-Fi and clean room!",
        )

        self.assertIsNotNone(review.pk)
        self.assertEqual(review.booking, self.completed_booking)
        self.assertEqual(review.room, self.room)
        self.assertEqual(review.tenant, self.tenant)
        self.assertEqual(review.rating, 5)
        self.assertEqual(review.comment, "Excellent stay, super fast Wi-Fi and clean room!")
        self.assertEqual(review.tenant_display_name, "Priya N.")
        self.assertEqual(review.pg.name, "Greenfield Residency")

    def test_tenant_display_name_privacy(self):
        """Review display name never exposes the full email address."""
        review = create_review(
            booking=self.completed_booking,
            tenant=self.tenant,
            rating=4,
            comment="Pleasant stay.",
        )
        # First name + last initial
        self.assertEqual(review.tenant_display_name, "Priya N.")
        self.assertNotIn("priya.nair@example.com", review.tenant_display_name)

        # Single word first name only
        single_name_user = UserFactory(role=UserRole.TENANT, first_name="Karan", last_name="")
        booking_single = BookingFactory(tenant=single_name_user, bed=self.bed, status=BookingStatus.COMPLETED)
        review_single = create_review(
            booking=booking_single,
            tenant=single_name_user,
            rating=4,
            comment="Good experience.",
        )
        self.assertEqual(review_single.tenant_display_name, "Karan")

    def test_rating_out_of_range_rejected(self):
        """Rating < 1 or > 5 raises ValidationError."""
        for invalid_rating in [0, 6, -1, 10]:
            with self.assertRaises(ValidationError) as ctx:
                create_review(
                    booking=self.completed_booking,
                    tenant=self.tenant,
                    rating=invalid_rating,
                    comment="Invalid rating test",
                )
            self.assertIn("Rating must be between 1 and 5 stars", str(ctx.exception))

    def test_cannot_review_uncompleted_booking(self):
        """Tenant cannot review a booking that is not COMPLETED."""
        for uncompleted_status in [
            BookingStatus.PENDING,
            BookingStatus.APPROVED,
            BookingStatus.PAYMENT_PENDING,
            BookingStatus.CONFIRMED,
            BookingStatus.REJECTED,
        ]:
            bed = BedFactory(room=self.room)
            booking = BookingFactory(
                tenant=self.tenant,
                bed=bed,
                status=uncompleted_status,
            )
            with self.assertRaises(ValidationError) as ctx:
                create_review(
                    booking=booking,
                    tenant=self.tenant,
                    rating=5,
                    comment="Tried to review prematurely",
                )
            self.assertIn("completing your stay", str(ctx.exception))

    def test_other_tenant_cannot_review_booking(self):
        """A tenant cannot review a booking made by someone else."""
        with self.assertRaises(PermissionDenied):
            create_review(
                booking=self.completed_booking,
                tenant=self.other_tenant,
                rating=5,
                comment="Impersonator review",
            )

    def test_duplicate_review_on_same_booking_rejected(self):
        """A booking can only have exactly one review (OneToOne constraint)."""
        create_review(
            booking=self.completed_booking,
            tenant=self.tenant,
            rating=5,
            comment="First review",
        )

        with self.assertRaises(ValidationError) as ctx:
            create_review(
                booking=self.completed_booking,
                tenant=self.tenant,
                rating=4,
                comment="Second review on same stay",
            )
        self.assertIn("already submitted a review", str(ctx.exception))

    def test_get_homepage_reviews(self):
        """get_homepage_reviews returns only reviews for COMPLETED bookings ordered by -created_at."""
        review1 = create_review(
            booking=self.completed_booking,
            tenant=self.tenant,
            rating=5,
            comment="First stay",
        )

        tenant2 = UserFactory(role=UserRole.TENANT, first_name="Rohan", last_name="Sharma")
        room2 = RoomFactory(pg=self.pg, room_number="202", capacity=1)
        bed2 = BedFactory(room=room2)
        booking2 = BookingFactory(tenant=tenant2, bed=bed2, status=BookingStatus.COMPLETED)
        review2 = create_review(
            booking=booking2,
            tenant=tenant2,
            rating=4,
            comment="Second stay",
        )

        reviews = list(get_homepage_reviews(limit=6))
        self.assertEqual(len(reviews), 2)
        # Most recent first
        self.assertEqual(reviews[0].pk, review2.pk)
        self.assertEqual(reviews[1].pk, review1.pk)


class BookingReviewViewTests(TestCase):
    """Integration tests for BookingReviewCreateView and HomeView."""

    def setUp(self):
        self.owner = UserFactory(role=UserRole.OWNER)
        self.tenant = UserFactory(
            role=UserRole.TENANT,
            first_name="Ananya",
            last_name="Sen",
            email="ananya.sen@example.com",
        )
        self.other_tenant = UserFactory(role=UserRole.TENANT)
        self.pg = PGFactory(owner=self.owner, name="Urban Hive PG", city="Pune")
        self.room = RoomFactory(pg=self.pg, room_number="104", capacity=1, room_type="Single")
        self.bed = BedFactory(room=self.room, is_available=True)
        self.completed_booking = BookingFactory(
            tenant=self.tenant,
            bed=self.bed,
            status=BookingStatus.COMPLETED,
            checked_out_at=timezone.now(),
        )
        self.review_url = reverse("bookings:booking_review", kwargs={"pk": self.completed_booking.pk})

    def test_tenant_post_review_success(self):
        """Verified tenant POSTs a review, gets redirected with success message."""
        self.client.force_login(self.tenant)
        response = self.client.post(
            self.review_url,
            data={
                "rating": 5,
                "comment": "Had a wonderful, peaceful stay during my internship!",
            },
        )
        self.assertRedirects(
            response,
            reverse("bookings:booking_detail", kwargs={"pk": self.completed_booking.pk}),
        )

        review = Review.objects.get(booking=self.completed_booking)
        self.assertEqual(review.rating, 5)
        self.assertEqual(review.comment, "Had a wonderful, peaceful stay during my internship!")
        self.assertEqual(review.tenant, self.tenant)

    def test_tenant_post_review_invalid_rating(self):
        """Submitting an invalid rating reloads detail page with error message."""
        self.client.force_login(self.tenant)
        response = self.client.post(
            self.review_url,
            data={
                "rating": 10,  # Invalid
                "comment": "Bad rating value",
            },
        )
        self.assertRedirects(
            response,
            reverse("bookings:booking_detail", kwargs={"pk": self.completed_booking.pk}),
        )
        self.assertFalse(Review.objects.filter(booking=self.completed_booking).exists())

    def test_other_tenant_cannot_post_review(self):
        """Another tenant cannot review someone else's completed booking."""
        self.client.force_login(self.other_tenant)
        response = self.client.post(
            self.review_url,
            data={"rating": 5, "comment": "Impersonation attempt"},
        )
        self.assertRedirects(
            response,
            reverse("bookings:booking_list"),
        )
        self.assertFalse(Review.objects.filter(booking=self.completed_booking).exists())

    def test_anonymous_user_redirected_to_login(self):
        """Unauthenticated user is redirected to login."""
        response = self.client.post(self.review_url, data={"rating": 5, "comment": "Anon"})
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response["Location"])

    def test_home_view_renders_reviews(self):
        """Home page displays verified review comments, star ratings, and privacy-safe tenant names."""
        create_review(
            booking=self.completed_booking,
            tenant=self.tenant,
            rating=5,
            comment="Awesome stay with great power backup!",
        )

        response = self.client.get(reverse("home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Awesome stay with great power backup!")
        self.assertContains(response, "Ananya S.")
        self.assertContains(response, "Urban Hive PG")
        self.assertContains(response, "Pune")
        self.assertContains(response, "Verified Resident")
        # Ensure private email is NOT rendered on the public page
        self.assertNotContains(response, "ananya.sen@example.com")

    def test_home_view_empty_state_without_reviews(self):
        """Home page renders clean empty state when no reviews exist."""
        response = self.client.get(reverse("home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Verified Resident Reviews")
