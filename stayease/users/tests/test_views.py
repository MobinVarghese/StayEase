from __future__ import annotations

from http import HTTPStatus
from typing import TYPE_CHECKING

import pytest
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.models import AnonymousUser
from django.contrib.messages.middleware import MessageMiddleware
from django.contrib.sessions.middleware import SessionMiddleware
from django.http import HttpRequest
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from stayease.users.forms import UserAdminChangeForm
from stayease.users.tests.factories import UserFactory
from stayease.users.views import UserRedirectView
from stayease.users.views import UserUpdateView
from stayease.users.views import user_detail_view

if TYPE_CHECKING:
    from django.test import RequestFactory

    from stayease.users.models import User

pytestmark = pytest.mark.django_db


class TestUserRedirectView:
    def test_get_redirect_url_tenant(self, user: User, rf: RequestFactory):
        view = UserRedirectView()
        request = rf.get("/fake-url")
        user.role = "TENANT"
        request.user = user

        view.request = request
        assert view.get_redirect_url() == reverse("users:dashboard_tenant")

    def test_get_redirect_url_owner(self, user: User, rf: RequestFactory):
        view = UserRedirectView()
        request = rf.get("/fake-url")
        user.role = "OWNER"
        request.user = user

        view.request = request
        assert view.get_redirect_url() == reverse("users:dashboard_owner")


class TestUserProfileView:
    def test_authenticated_access_profile_route(self, client, user: User):
        client.force_login(user)
        response = client.get(reverse("users:profile"))
        assert response.status_code == HTTPStatus.OK
        content = response.content.decode("utf-8")
        assert "My Profile" in content
        assert user.first_name in content
        assert user.last_name in content
        assert user.email in content
        assert user.phone_number in content

    def test_authenticated_access_detail_route(self, client, user: User):
        client.force_login(user)
        response = client.get(reverse("users:detail", kwargs={"pk": user.pk}))
        assert response.status_code == HTTPStatus.OK
        content = response.content.decode("utf-8")
        assert "My Profile" in content
        assert user.email in content

    def test_unauthenticated_access_redirect(self, client, user: User):
        # Profile route
        response = client.get(reverse("users:profile"))
        assert response.status_code == HTTPStatus.FOUND
        assert reverse(settings.LOGIN_URL) in response.url

        # Detail route with pk
        response_detail = client.get(reverse("users:detail", kwargs={"pk": user.pk}))
        assert response_detail.status_code == HTTPStatus.FOUND
        assert reverse(settings.LOGIN_URL) in response_detail.url

    def test_update_first_name(self, client, user: User):
        client.force_login(user)
        data = {
            "first_name": "Updatedfirst",
            "last_name": user.last_name,
            "email": user.email,
            "phone_number": user.phone_number,
        }
        response = client.post(reverse("users:profile"), data)
        assert response.status_code == HTTPStatus.FOUND
        user.refresh_from_db()
        assert user.first_name == "Updatedfirst"

    def test_update_last_name(self, client, user: User):
        client.force_login(user)
        data = {
            "first_name": user.first_name,
            "last_name": "Updatedlast",
            "email": user.email,
            "phone_number": user.phone_number,
        }
        response = client.post(reverse("users:profile"), data)
        assert response.status_code == HTTPStatus.FOUND
        user.refresh_from_db()
        assert user.last_name == "Updatedlast"

    def test_update_email(self, client, user: User):
        client.force_login(user)
        new_email = "brandnewemail@example.com"
        data = {
            "first_name": user.first_name,
            "last_name": user.last_name,
            "email": new_email,
            "phone_number": user.phone_number,
        }
        response = client.post(reverse("users:profile"), data)
        assert response.status_code == HTTPStatus.FOUND
        user.refresh_from_db()
        assert user.email == new_email

        # Also verify allauth EmailAddress sync
        from allauth.account.models import EmailAddress

        email_records = EmailAddress.objects.filter(user=user)
        if email_records.exists():
            primary_record = email_records.get(primary=True)
            assert primary_record.email == new_email

    def test_update_phone_number(self, client, user: User):
        client.force_login(user)
        data = {
            "first_name": user.first_name,
            "last_name": user.last_name,
            "email": user.email,
            "phone_number": "+91 9876543210",
        }
        response = client.post(reverse("users:profile"), data)
        assert response.status_code == HTTPStatus.FOUND
        user.refresh_from_db()
        assert user.phone_number == "9876543210"

    def test_invalid_input_validation_errors(self, client, user: User):
        client.force_login(user)
        other_user = UserFactory.create(email="existing@example.com")

        # 1. Invalid phone number (less than 10 digits)
        invalid_phone_data = {
            "first_name": user.first_name,
            "last_name": user.last_name,
            "email": user.email,
            "phone_number": "12345",
        }
        response = client.post(reverse("users:profile"), invalid_phone_data)
        assert response.status_code == HTTPStatus.OK
        assert "Phone number must be at least 10 digits." in response.content.decode("utf-8")

        # 2. Duplicate email
        duplicate_email_data = {
            "first_name": user.first_name,
            "last_name": user.last_name,
            "email": other_user.email,
            "phone_number": user.phone_number,
        }
        response = client.post(reverse("users:profile"), duplicate_email_data)
        assert response.status_code == HTTPStatus.OK
        assert "This email address is already in use." in response.content.decode("utf-8")

    def test_user_cannot_modify_another_users_profile(self, client):
        user1 = UserFactory.create(first_name="UserOne", email="user1@example.com")
        user2 = UserFactory.create(first_name="UserTwo", email="user2@example.com")

        client.force_login(user1)

        # GET user2's profile URL
        get_response = client.get(reverse("users:detail", kwargs={"pk": user2.pk}))
        assert get_response.status_code == HTTPStatus.FORBIDDEN

        # POST attempt to user2's profile URL
        post_response = client.post(
            reverse("users:detail", kwargs={"pk": user2.pk}),
            {
                "first_name": "HackedName",
                "last_name": "HackedLast",
                "email": "hacked@example.com",
                "phone_number": "9999999999",
            },
        )
        assert post_response.status_code == HTTPStatus.FORBIDDEN

        # Confirm user2 unchanged
        user2.refresh_from_db()
        assert user2.first_name == "UserTwo"
        assert user2.email == "user2@example.com"

    def test_save_changes_persists_to_database_with_success_message(self, client, user: User):
        client.force_login(user)
        post_data = {
            "first_name": "VerifiedFirst",
            "last_name": "VerifiedLast",
            "email": "verified.persisted@example.com",
            "phone_number": "9812345678",
        }
        response = client.post(
            reverse("users:detail", kwargs={"pk": user.pk}),
            post_data,
            follow=True,
        )
        assert response.status_code == HTTPStatus.OK
        content = response.content.decode("utf-8")
        assert "Your profile has been updated successfully." in content

        user.refresh_from_db()
        assert user.first_name == "VerifiedFirst"
        assert user.last_name == "VerifiedLast"
        assert user.email == "verified.persisted@example.com"
        assert user.phone_number == "9812345678"

    def test_mfa_and_allauth_sections_not_rendered(self, client, user: User):
        client.force_login(user)
        response = client.get(reverse("users:profile"))
        assert response.status_code == HTTPStatus.OK
        content = response.content.decode("utf-8")

        assert "mfa_index" not in content
        assert "account_email" not in content
        assert ">MFA<" not in content
        assert ">My Info<" not in content
        assert ">E-Mail<" not in content
        assert "socialaccount" not in content


class TestTenantDashboardView:
    def test_unauthenticated_redirect(self, client):
        url = reverse("users:dashboard_tenant")
        resp = client.get(url)
        assert resp.status_code == 302
        assert "account" in resp.url or "login" in resp.url

    def test_owner_forbidden(self, client):
        owner = UserFactory(role="OWNER")
        client.force_login(owner)
        url = reverse("users:dashboard_tenant")
        resp = client.get(url)
        assert resp.status_code == 403

    def test_tenant_dashboard_empty_state(self, client):
        tenant = UserFactory(role="TENANT", first_name="Alice")
        client.force_login(tenant)
        url = reverse("users:dashboard_tenant")
        resp = client.get(url)
        assert resp.status_code == 200
        content = resp.content.decode("utf-8")
        assert "Find Accommodation" in content
        assert "My Bookings" in content
        assert "Notifications" in content
        assert "Coming soon" not in content
        assert reverse("discovery:pg_list") in content
        assert reverse("bookings:booking_list") in content
        assert reverse("notifications:notification_list") in content
        assert "No bookings yet" in content
        assert "All caught up!" in content

    def test_tenant_dashboard_dynamic_data(self, client):
        from decimal import Decimal
        from stayease.bookings.models import Booking, BookingStatus
        from stayease.notifications.services import create_notification, mark_all_read
        from stayease.properties.tests.factories import BedFactory, PGFactory, RoomFactory

        tenant = UserFactory(role="TENANT", first_name="Bob")
        client.force_login(tenant)

        # Create 2 PGs and beds
        pg1 = PGFactory(name="Green Villa")
        room1 = RoomFactory(pg=pg1, capacity=2)
        bed1 = BedFactory(room=room1, label="B1", rent_per_month=Decimal("4000.00"), is_available=True)
        bed2 = BedFactory(room=room1, label="B2", rent_per_month=Decimal("4500.00"), is_available=True)

        pg2 = PGFactory(name="Blue Haven")
        room2 = RoomFactory(pg=pg2, capacity=1)
        bed3 = BedFactory(room=room2, label="B3", rent_per_month=Decimal("5000.00"), is_available=True)

        # Create bookings for tenant: 1 PENDING, 1 CONFIRMED
        booking1 = Booking.objects.create(tenant=tenant, bed=bed1, status=BookingStatus.PENDING)
        booking2 = Booking.objects.create(tenant=tenant, bed=bed3, status=BookingStatus.CONFIRMED)

        # Create notifications for tenant: 2 unread
        create_notification(recipient=tenant, message="Booking approved", booking=booking1)
        create_notification(recipient=tenant, message="Payment received", booking=booking2)

        url = reverse("users:dashboard_tenant")
        resp = client.get(url)
        assert resp.status_code == 200
        assert resp.context["total_active_pg_count"] == 2
        # Bed 1 and Bed 3 have active bookings, so Bed 2 is the available one
        assert resp.context["available_bed_count"] == 1

        assert resp.context["booking_stats"]["total"] == 2
        assert resp.context["booking_stats"]["pending"] == 1
        assert resp.context["booking_stats"]["confirmed"] == 1
        assert resp.context["unread_notification_count"] == 2

        content = resp.content.decode("utf-8")
        assert "Pending: 1" in content
        assert "Confirmed: 1" in content
        assert "2 unread" in content

        # Now test reactivity: mark all notifications as read and reload
        mark_all_read(tenant)
        resp2 = client.get(url)
        assert resp2.status_code == 200
        assert resp2.context["unread_notification_count"] == 0
        assert "All caught up!" in resp2.content.decode("utf-8")


class TestOwnerDashboardView:
    def test_unauthenticated_redirect(self, client):
        url = reverse("users:dashboard_owner")
        resp = client.get(url)
        assert resp.status_code == 302
        assert "account" in resp.url or "login" in resp.url

    def test_tenant_forbidden(self, client):
        tenant = UserFactory(role="TENANT")
        client.force_login(tenant)
        url = reverse("users:dashboard_owner")
        resp = client.get(url)
        assert resp.status_code == 403

    def test_owner_empty_dashboard(self, client):
        owner = UserFactory(role="OWNER", first_name="Christopher")
        client.force_login(owner)
        url = reverse("users:dashboard_owner")
        resp = client.get(url)
        assert resp.status_code == 200
        content = resp.content.decode("utf-8")

        assert "My Properties" in content
        assert "Booking Requests" in content
        assert "Notifications" in content
        assert "Coming soon" not in content

        # Check existing target links
        assert reverse("properties:pg_list") in content
        assert reverse("bookings:owner_booking_list") in content
        assert reverse("notifications:notification_list") in content

        # Check empty state message
        assert "No pending booking requests" in content
        assert "All caught up!" in content

    def test_owner_data_isolation_and_reactivity(self, client):
        from decimal import Decimal
        from stayease.bookings.models import Booking, BookingStatus
        from stayease.notifications.services import create_notification
        from stayease.properties.tests.factories import BedFactory, PGFactory, RoomFactory

        # Owner A
        owner_a = UserFactory(role="OWNER", first_name="OwnerA")
        # Owner B
        owner_b = UserFactory(role="OWNER", first_name="OwnerB")
        # Tenant
        tenant = UserFactory(role="TENANT", first_name="TenantT")

        # Owner A properties, rooms, beds
        pg_a1 = PGFactory(owner=owner_a, name="Rose Villa")
        room_a1 = RoomFactory(pg=pg_a1, capacity=2)
        bed_a1 = BedFactory(room=room_a1, label="B1", rent_per_month=Decimal("3000.00"), is_available=True)
        bed_a2 = BedFactory(room=room_a1, label="B2", rent_per_month=Decimal("3500.00"), is_available=True)

        pg_a2 = PGFactory(owner=owner_a, name="Green Valley PG")
        room_a2 = RoomFactory(pg=pg_a2, capacity=1)
        bed_a3 = BedFactory(room=room_a2, label="B3", rent_per_month=Decimal("4000.00"), is_available=True)

        # Owner B properties, rooms, beds (MUST NOT LEAK to Owner A)
        pg_b = PGFactory(owner=owner_b, name="Other PG")
        room_b = RoomFactory(pg=pg_b, capacity=5)
        bed_b = BedFactory(room=room_b, label="B_other", rent_per_month=Decimal("6000.00"), is_available=True)
        Booking.objects.create(tenant=tenant, bed=bed_b, status=BookingStatus.PENDING)
        create_notification(recipient=owner_b, message="Booking for Owner B")

        # Login as Owner A
        client.force_login(owner_a)
        url = reverse("users:dashboard_owner")
        resp = client.get(url)
        assert resp.status_code == 200

        # Owner A sees only their 2 properties, 2 rooms, 3 beds, 0 bookings, 0 notifications
        assert resp.context["total_properties_count"] == 2
        assert resp.context["total_rooms_count"] == 2
        assert resp.context["total_beds_count"] == 3
        assert resp.context["available_beds_count"] == 3
        assert resp.context["booking_stats"]["total"] == 0
        assert resp.context["booking_stats"]["pending"] == 0
        assert resp.context["unread_notification_count"] == 0

        # Now Tenant creates a booking request for Owner A's bed
        booking = Booking.objects.create(tenant=tenant, bed=bed_a1, status=BookingStatus.PENDING)
        create_notification(recipient=owner_a, message="Tenant requested Bed B1", booking=booking)

        # Owner A refreshes dashboard -> immediately reflects 1 pending booking and 1 unread notification
        resp2 = client.get(url)
        assert resp2.status_code == 200
        assert resp2.context["booking_stats"]["total"] == 1
        assert resp2.context["booking_stats"]["pending"] == 1
        assert resp2.context["available_beds_count"] == 2  # bed_a1 now has an active booking
        assert resp2.context["unread_notification_count"] == 1

        content2 = resp2.content.decode("utf-8")
        assert "Pending: 1" in content2
        assert "1 unread" in content2
        assert "Rose Villa" in content2

