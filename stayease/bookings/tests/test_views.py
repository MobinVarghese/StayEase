"""
View-level tests for StayEase bookings.

Covers:
- Unauthenticated access redirection to login
- Role-based forbidden responses (e.g. owners Booking form, tenants Booking Approve)
- Tenant booking creation flow (GET and POST)
- Booking detail authorization checks (Tenant vs PG Owner vs other users)
- Tenant booking history isolation
- Owner booking management history isolation
- Successful Owner approve/reject POST actions
- Forbidden Owner approve/reject actions for unauthorized owners
"""

from __future__ import annotations

import pytest
from django.test import Client
from django.urls import reverse

from stayease.bookings.models import Booking
from stayease.bookings.models import BookingStatus
from stayease.bookings.tests.factories import BookingFactory
from stayease.properties.tests.factories import BedFactory
from stayease.properties.tests.factories import PGFactory
from stayease.users.models import UserRole
from stayease.users.tests.factories import UserFactory

pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _login(client: Client, user):
    client.force_login(user)


def _owner():
    return UserFactory(role=UserRole.OWNER, password="testpass123")


def _tenant():
    return UserFactory(role=UserRole.TENANT, password="testpass123")


# ===========================================================================
# Tenant Booking List View
# ===========================================================================

class TestTenantBookingListView:
    def test_unauthenticated_redirect(self, client):
        url = reverse("bookings:booking_list")
        resp = client.get(url)
        assert resp.status_code == 302
        assert "login" in resp.url or "account" in resp.url

    def test_owner_forbidden(self, client):
        _login(client, _owner())
        resp = client.get(reverse("bookings:booking_list"))
        assert resp.status_code == 403

    def test_tenant_sees_only_own_bookings(self, client):
        tenant_a = _tenant()
        tenant_b = _tenant()
        
        b1 = BookingFactory(tenant=tenant_a)
        b2 = BookingFactory(tenant=tenant_b)

        _login(client, tenant_a)
        resp = client.get(reverse("bookings:booking_list"))
        assert resp.status_code == 200
        
        # Should contain tenant_a's booking but not tenant_b's
        # Since templates output booking IDs, we check for presence/absence
        assert f"{b1.pk}".encode() in resp.content
        assert f"{b2.pk}".encode() not in resp.content


# ===========================================================================
# Booking Create View
# ===========================================================================

class TestBookingCreateView:
    def test_unauthenticated_redirect(self, client):
        bed = BedFactory()
        url = reverse("bookings:booking_create", kwargs={"bed_pk": bed.pk})
        resp = client.get(url)
        assert resp.status_code == 302

    def test_owner_forbidden(self, client):
        _login(client, _owner())
        bed = BedFactory()
        url = reverse("bookings:booking_create", kwargs={"bed_pk": bed.pk})
        resp = client.get(url)
        assert resp.status_code == 403

    def test_booking_create_get(self, client):
        tenant = _tenant()
        _login(client, tenant)
        bed = BedFactory(is_available=True, is_active=True)
        url = reverse("bookings:booking_create", kwargs={"bed_pk": bed.pk})
        resp = client.get(url)
        assert resp.status_code == 200
        assert bed.label.encode() in resp.content

    def test_booking_create_post_success(self, client):
        tenant = _tenant()
        _login(client, tenant)
        bed = BedFactory(is_available=True, is_active=True)
        url = reverse("bookings:booking_create", kwargs={"bed_pk": bed.pk})
        
        # Confirm field in post
        resp = client.post(url, {"confirm": True})
        # Should redirect to detail view
        assert resp.status_code == 302
        
        # Verify Booking model entry exists
        booking = Booking.objects.get(tenant=tenant, bed=bed)
        assert booking.status == BookingStatus.PENDING
        assert reverse("bookings:booking_detail", kwargs={"pk": booking.pk}) in resp.url

    def test_booking_create_post_error_rejection(self, client):
        tenant = _tenant()
        _login(client, tenant)
        # Bed is unavailable
        bed = BedFactory(is_available=False, is_active=True)
        url = reverse("bookings:booking_create", kwargs={"bed_pk": bed.pk})
        
        resp = client.post(url, {"confirm": True})
        # Should redirect back to the request form
        assert resp.status_code == 302
        assert url in resp.url
        assert not Booking.objects.filter(tenant=tenant, bed=bed).exists()


# ===========================================================================
# Booking Detail View
# ===========================================================================

class TestBookingDetailView:
    def test_unauthenticated_redirect(self, client):
        booking = BookingFactory()
        url = reverse("bookings:booking_detail", kwargs={"pk": booking.pk})
        resp = client.get(url)
        assert resp.status_code == 302

    def test_tenant_views_own_booking(self, client):
        tenant = _tenant()
        booking = BookingFactory(tenant=tenant)
        _login(client, tenant)
        url = reverse("bookings:booking_detail", kwargs={"pk": booking.pk})
        resp = client.get(url)
        assert resp.status_code == 200

    def test_tenant_cannot_view_others_booking(self, client):
        tenant_a = _tenant()
        booking = BookingFactory()  # different tenant
        _login(client, tenant_a)
        url = reverse("bookings:booking_detail", kwargs={"pk": booking.pk})
        resp = client.get(url)
        assert resp.status_code == 403

    def test_owner_views_tenant_booking_for_their_pg(self, client):
        owner = _owner()
        pg = PGFactory(owner=owner)
        bed = BedFactory(room__pg=pg)
        booking = BookingFactory(bed=bed)
        _login(client, owner)
        url = reverse("bookings:booking_detail", kwargs={"pk": booking.pk})
        resp = client.get(url)
        assert resp.status_code == 200

    def test_owner_cannot_view_booking_for_other_owners_pg(self, client):
        owner = _owner()
        pg = PGFactory()  # owned by other owner
        bed = BedFactory(room__pg=pg)
        booking = BookingFactory(bed=bed)
        _login(client, owner)
        url = reverse("bookings:booking_detail", kwargs={"pk": booking.pk})
        resp = client.get(url)
        assert resp.status_code == 403

    # -----------------------------------------------------------------------
    # Post-confirmation contact sharing tests
    # -----------------------------------------------------------------------

    def test_tenant_cannot_see_owner_phone_for_pending_booking(self, client):
        owner = UserFactory(role=UserRole.OWNER, phone_number="9876543210")
        tenant = UserFactory(role=UserRole.TENANT, phone_number="9123456780")
        pg = PGFactory(owner=owner)
        bed = BedFactory(room__pg=pg)
        booking = BookingFactory(tenant=tenant, bed=bed, status=BookingStatus.PENDING)

        _login(client, tenant)
        resp = client.get(reverse("bookings:booking_detail", kwargs={"pk": booking.pk}))
        assert resp.status_code == 200
        content = resp.content.decode("utf-8")

        assert "9876543210" not in content
        assert "Call Owner" not in content
        assert "Contact details will be available after confirmation." in content

    def test_tenant_cannot_see_owner_phone_for_rejected_booking(self, client):
        owner = UserFactory(role=UserRole.OWNER, phone_number="9876543210")
        tenant = UserFactory(role=UserRole.TENANT, phone_number="9123456780")
        pg = PGFactory(owner=owner)
        bed = BedFactory(room__pg=pg)
        booking = BookingFactory(tenant=tenant, bed=bed, status=BookingStatus.REJECTED)

        _login(client, tenant)
        resp = client.get(reverse("bookings:booking_detail", kwargs={"pk": booking.pk}))
        assert resp.status_code == 200
        content = resp.content.decode("utf-8")

        assert "9876543210" not in content
        assert "Call Owner" not in content

    def test_tenant_can_see_owner_phone_for_confirmed_booking(self, client):
        owner = UserFactory(
            role=UserRole.OWNER,
            first_name="Christopher",
            last_name="Nolan",
            phone_number="9876543210",
        )
        tenant = UserFactory(role=UserRole.TENANT, phone_number="9123456780")
        pg = PGFactory(owner=owner)
        bed = BedFactory(room__pg=pg)
        booking = BookingFactory(tenant=tenant, bed=bed, status=BookingStatus.CONFIRMED)

        _login(client, tenant)
        resp = client.get(reverse("bookings:booking_detail", kwargs={"pk": booking.pk}))
        assert resp.status_code == 200
        content = resp.content.decode("utf-8")

        assert "9876543210" in content
        assert "Christopher" in content
        assert "Call Owner" in content
        assert 'href="tel:9876543210"' in content

    def test_owner_cannot_see_tenant_phone_for_pending_booking(self, client):
        owner = UserFactory(role=UserRole.OWNER, phone_number="9876543210")
        tenant = UserFactory(
            role=UserRole.TENANT,
            first_name="Mobin",
            last_name="Varghese",
            phone_number="9123456780",
        )
        pg = PGFactory(owner=owner)
        bed = BedFactory(room__pg=pg)
        booking = BookingFactory(tenant=tenant, bed=bed, status=BookingStatus.PENDING)

        _login(client, owner)
        resp = client.get(reverse("bookings:booking_detail", kwargs={"pk": booking.pk}))
        assert resp.status_code == 200
        content = resp.content.decode("utf-8")

        assert "9123456780" not in content
        assert "Call Tenant" not in content
        assert "Tenant contact details will be available after confirmation." in content

    def test_owner_cannot_see_tenant_phone_for_rejected_booking(self, client):
        owner = UserFactory(role=UserRole.OWNER, phone_number="9876543210")
        tenant = UserFactory(role=UserRole.TENANT, phone_number="9123456780")
        pg = PGFactory(owner=owner)
        bed = BedFactory(room__pg=pg)
        booking = BookingFactory(tenant=tenant, bed=bed, status=BookingStatus.REJECTED)

        _login(client, owner)
        resp = client.get(reverse("bookings:booking_detail", kwargs={"pk": booking.pk}))
        assert resp.status_code == 200
        content = resp.content.decode("utf-8")

        assert "9123456780" not in content
        assert "Call Tenant" not in content

    def test_owner_can_see_tenant_phone_for_confirmed_booking(self, client):
        owner = UserFactory(role=UserRole.OWNER, phone_number="9876543210")
        tenant = UserFactory(
            role=UserRole.TENANT,
            first_name="Mobin",
            last_name="Varghese",
            phone_number="9123456780",
        )
        pg = PGFactory(owner=owner)
        bed = BedFactory(room__pg=pg)
        booking = BookingFactory(tenant=tenant, bed=bed, status=BookingStatus.CONFIRMED)

        _login(client, owner)
        resp = client.get(reverse("bookings:booking_detail", kwargs={"pk": booking.pk}))
        assert resp.status_code == 200
        content = resp.content.decode("utf-8")

        assert "9123456780" in content
        assert "Mobin Varghese" in content
        assert "Call Tenant" in content
        assert 'href="tel:9123456780"' in content

    def test_direct_url_tampering_rejected_with_403(self, client):
        user_intruder = UserFactory(role=UserRole.TENANT)
        owner = UserFactory(role=UserRole.OWNER, phone_number="9876543210")
        tenant = UserFactory(role=UserRole.TENANT, phone_number="9123456780")
        pg = PGFactory(owner=owner)
        bed = BedFactory(room__pg=pg)
        booking = BookingFactory(tenant=tenant, bed=bed, status=BookingStatus.CONFIRMED)

        _login(client, user_intruder)
        resp = client.get(reverse("bookings:booking_detail", kwargs={"pk": booking.pk}))
        assert resp.status_code == 403

    def test_missing_phone_number_handled_gracefully(self, client):
        owner = UserFactory(role=UserRole.OWNER, phone_number="")
        tenant = UserFactory(role=UserRole.TENANT, phone_number="")
        pg = PGFactory(owner=owner)
        bed = BedFactory(room__pg=pg)
        booking = BookingFactory(tenant=tenant, bed=bed, status=BookingStatus.CONFIRMED)

        _login(client, tenant)
        resp = client.get(reverse("bookings:booking_detail", kwargs={"pk": booking.pk}))
        assert resp.status_code == 200
        content = resp.content.decode("utf-8")
        assert "Not provided" in content
        assert "href=\"tel:" not in content



# ===========================================================================
# Owner Booking List View (Dashboard)
# ===========================================================================

class TestOwnerBookingListView:
    def test_unauthenticated_redirect(self, client):
        url = reverse("bookings:owner_booking_list")
        resp = client.get(url)
        assert resp.status_code == 302

    def test_tenant_forbidden(self, client):
        _login(client, _tenant())
        url = reverse("bookings:owner_booking_list")
        resp = client.get(url)
        assert resp.status_code == 403

    def test_owner_sees_only_own_pg_requests(self, client):
        owner_a = _owner()
        owner_b = _owner()

        pg_a = PGFactory(owner=owner_a)
        pg_b = PGFactory(owner=owner_b)

        bed_a = BedFactory(room__pg=pg_a)
        bed_b = BedFactory(room__pg=pg_b)

        b1 = BookingFactory(bed=bed_a)
        b2 = BookingFactory(bed=bed_b)

        _login(client, owner_a)
        resp = client.get(reverse("bookings:owner_booking_list"))
        assert resp.status_code == 200
        assert f"{b1.pk}".encode() in resp.content
        assert f"{b2.pk}".encode() not in resp.content


# ===========================================================================
# Owner Approve View
# ===========================================================================

class TestBookingApproveView:
    def test_owner_approves_pending_booking(self, client):
        owner = _owner()
        pg = PGFactory(owner=owner)
        bed = BedFactory(room__pg=pg)
        booking = BookingFactory(bed=bed, status=BookingStatus.PENDING)

        _login(client, owner)
        url = reverse("bookings:booking_approve", kwargs={"pk": booking.pk})
        resp = client.post(url)
        
        assert resp.status_code == 302
        booking.refresh_from_db()
        assert booking.status == BookingStatus.APPROVED

    def test_wrong_owner_approve_forbidden(self, client):
        owner_a = _owner()
        owner_b = _owner()
        pg = PGFactory(owner=owner_a)
        bed = BedFactory(room__pg=pg)
        booking = BookingFactory(bed=bed, status=BookingStatus.PENDING)

        _login(client, owner_b)
        url = reverse("bookings:booking_approve", kwargs={"pk": booking.pk})
        resp = client.post(url)
        
        # The view handles PermissionDenied by redirecting or raising 403 depending on implementation.
        # Let's verify status remains PENDING.
        booking.refresh_from_db()
        assert booking.status == BookingStatus.PENDING


# ===========================================================================
# Owner Reject View
# ===========================================================================

class TestBookingRejectView:
    def test_owner_rejects_pending_booking(self, client):
        owner = _owner()
        pg = PGFactory(owner=owner)
        bed = BedFactory(room__pg=pg)
        booking = BookingFactory(bed=bed, status=BookingStatus.PENDING)

        _login(client, owner)
        url = reverse("bookings:booking_reject", kwargs={"pk": booking.pk})
        resp = client.post(url)
        
        assert resp.status_code == 302
        booking.refresh_from_db()
        assert booking.status == BookingStatus.REJECTED

    def test_wrong_owner_reject_forbidden(self, client):
        owner_a = _owner()
        owner_b = _owner()
        pg = PGFactory(owner=owner_a)
        bed = BedFactory(room__pg=pg)
        booking = BookingFactory(bed=bed, status=BookingStatus.PENDING)

        _login(client, owner_b)
        url = reverse("bookings:booking_reject", kwargs={"pk": booking.pk})
        resp = client.post(url)
        
        booking.refresh_from_db()
        assert booking.status == BookingStatus.PENDING
