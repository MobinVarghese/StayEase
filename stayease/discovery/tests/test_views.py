"""
Tests for discovery views.

These tests verify the tenant-facing listing and detail pages,
including search, filtering, pagination, booking handoff links,
security (no owner data leaked), and edge cases.

Business logic ownership: Member 3
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from django.test import Client
from django.urls import reverse

from stayease.bookings.models import BookingStatus
from stayease.bookings.tests.factories import BookingFactory
from stayease.properties.tests.factories import BedFactory
from stayease.properties.tests.factories import PGFactory
from stayease.properties.tests.factories import RoomFactory
from stayease.users.models import UserRole
from stayease.users.tests.factories import UserFactory


@pytest.fixture
def client():
    return Client()


def _login(client: Client, user):
    client.force_login(user)


def _tenant():
    return UserFactory(role=UserRole.TENANT, password="testpass123")


def _owner():
    return UserFactory(role=UserRole.OWNER, password="testpass123")


# ======================================================================
# PGDiscoveryListView
# ======================================================================


@pytest.mark.django_db
class TestPGDiscoveryListView:
    """Tests for the PG listing/search page."""

    url = reverse("discovery:pg_list")

    def test_unauthenticated_redirect(self, client):
        """Anonymous users should be redirected to login."""
        response = client.get(self.url)
        assert response.status_code == 302
        assert "login" in response.url or "account" in response.url

    def test_owner_forbidden(self, client):
        """Owners should get 403 when trying to access tenant discovery."""
        owner = _owner()
        _login(client, owner)
        response = client.get(self.url)
        assert response.status_code == 403

    def test_page_loads_200_for_tenant(self, client):
        tenant = _tenant()
        _login(client, tenant)
        response = client.get(self.url)
        assert response.status_code == 200

    def test_displays_active_pgs(self, client):
        tenant = _tenant()
        _login(client, tenant)
        PGFactory(is_active=True, name="Test PG Visible")
        PGFactory(is_active=False, name="Test PG Hidden")
        response = client.get(self.url)
        assert b"Test PG Visible" in response.content
        assert b"Test PG Hidden" not in response.content

    def test_search_by_keyword(self, client):
        tenant = _tenant()
        _login(client, tenant)
        PGFactory(name="Green Valley PG")
        PGFactory(name="Blue Sky PG")
        response = client.get(self.url, {"q": "Green"})
        assert b"Green Valley PG" in response.content
        assert b"Blue Sky PG" not in response.content

    def test_filter_by_city(self, client):
        tenant = _tenant()
        _login(client, tenant)
        PGFactory(name="Mumbai PG", city="Mumbai")
        PGFactory(name="Delhi PG", city="Delhi")
        response = client.get(self.url, {"city": "Mumbai"})
        assert b"Mumbai PG" in response.content
        assert b"Delhi PG" not in response.content

    def test_filter_by_price_range(self, client):
        tenant = _tenant()
        _login(client, tenant)
        PGFactory(name="Cheap PG", rent_per_month=Decimal("3000.00"))
        PGFactory(name="Expensive PG", rent_per_month=Decimal("15000.00"))
        response = client.get(self.url, {"max_price": "5000"})
        assert b"Cheap PG" in response.content
        assert b"Expensive PG" not in response.content

    def test_available_only_filter(self, client):
        tenant = _tenant()
        _login(client, tenant)
        pg_avail = PGFactory(name="Available PG")
        room = RoomFactory(pg=pg_avail, capacity=1)
        BedFactory(room=room, is_available=True, is_active=True)
        PGFactory(name="Empty PG")  # no beds
        response = client.get(self.url, {"available_only": "1"})
        assert b"Available PG" in response.content
        assert b"Empty PG" not in response.content

    def test_empty_results_message(self, client):
        tenant = _tenant()
        _login(client, tenant)
        response = client.get(self.url, {"q": "nonexistent_xyz"})
        assert response.status_code == 200
        assert b"No PG accommodations found" in response.content

    def test_pagination_present_with_many_pgs(self, client):
        tenant = _tenant()
        _login(client, tenant)
        for i in range(15):
            PGFactory(name=f"PG {i}")
        response = client.get(self.url)
        assert response.status_code == 200
        # Page 1 should show 12 items, pagination controls should exist
        assert b"Next" in response.content

    def test_pagination_preserves_filters(self, client):
        tenant = _tenant()
        _login(client, tenant)
        for _ in range(15):
            PGFactory(city="TestCity")
        response = client.get(self.url, {"city": "TestCity"})
        content = response.content.decode()
        # Pagination links should include the filter
        assert "city=TestCity" in content

    def test_search_form_present(self, client):
        tenant = _tenant()
        _login(client, tenant)
        response = client.get(self.url)
        assert b"id_search_q" in response.content
        assert b"id_filter_city" in response.content

    def test_does_not_expose_owner_info(self, client):
        """PG cards must not show owner email/name."""
        tenant = _tenant()
        _login(client, tenant)
        owner = UserFactory(email="secret_owner@example.com", name="Secret Owner")
        PGFactory(owner=owner, name="Public PG")
        response = client.get(self.url)
        assert b"secret_owner@example.com" not in response.content
        assert b"Secret Owner" not in response.content

    def test_link_to_detail_page(self, client):
        tenant = _tenant()
        _login(client, tenant)
        pg = PGFactory()
        response = client.get(self.url)
        detail_url = reverse("discovery:pg_detail", kwargs={"pg_pk": pg.pk})
        assert detail_url.encode() in response.content


# ======================================================================
# PGDiscoveryDetailView
# ======================================================================


@pytest.mark.django_db
class TestPGDiscoveryDetailView:
    """Tests for the PG detail page."""

    def _url(self, pg_pk):
        return reverse("discovery:pg_detail", kwargs={"pg_pk": pg_pk})

    def test_unauthenticated_redirect(self, client):
        """Anonymous users should be redirected to login."""
        pg = PGFactory()
        response = client.get(self._url(pg.pk))
        assert response.status_code == 302
        assert "login" in response.url or "account" in response.url

    def test_owner_forbidden(self, client):
        """Owners should get 403 when trying to access tenant discovery detail."""
        owner = _owner()
        _login(client, owner)
        pg = PGFactory()
        response = client.get(self._url(pg.pk))
        assert response.status_code == 403

    def test_page_loads_200_for_tenant(self, client):
        tenant = _tenant()
        _login(client, tenant)
        pg = PGFactory()
        response = client.get(self._url(pg.pk))
        assert response.status_code == 200

    def test_displays_pg_info(self, client):
        tenant = _tenant()
        _login(client, tenant)
        pg = PGFactory(
            name="Sunshine PG",
            city="Kochi",
            amenities="Wi-Fi, Gym",
        )
        response = client.get(self._url(pg.pk))
        content = response.content.decode()
        assert "Sunshine PG" in content
        assert "Kochi" in content
        assert "Wi-Fi, Gym" in content

    def test_displays_rooms_and_beds(self, client):
        tenant = _tenant()
        _login(client, tenant)
        pg = PGFactory()
        room = RoomFactory(pg=pg, room_number="101", capacity=2)
        BedFactory(room=room, label="Bed A", is_available=True, is_active=True)
        BedFactory(room=room, label="Bed B", is_available=False, is_active=True)
        response = client.get(self._url(pg.pk))
        content = response.content.decode()
        assert "101" in content
        assert "Bed A" in content
        assert "Bed B" in content

    def test_available_bed_has_booking_link(self, client):
        tenant = _tenant()
        _login(client, tenant)
        pg = PGFactory()
        room = RoomFactory(pg=pg, capacity=1)
        bed = BedFactory(room=room, is_available=True, is_active=True)
        response = client.get(self._url(pg.pk))
        booking_url = reverse("bookings:booking_create", kwargs={"bed_pk": bed.pk})
        assert booking_url.encode() in response.content

    def test_unavailable_bed_no_booking_link(self, client):
        tenant = _tenant()
        _login(client, tenant)
        pg = PGFactory()
        room = RoomFactory(pg=pg, capacity=1)
        bed = BedFactory(room=room, is_available=False, is_active=True)
        response = client.get(self._url(pg.pk))
        booking_url = reverse("bookings:booking_create", kwargs={"bed_pk": bed.pk})
        assert booking_url.encode() not in response.content

    def test_booked_bed_not_bookable(self, client):
        tenant = _tenant()
        _login(client, tenant)
        pg = PGFactory()
        room = RoomFactory(pg=pg, capacity=1)
        bed = BedFactory(room=room, is_available=True, is_active=True)
        BookingFactory(bed=bed, status=BookingStatus.CONFIRMED)
        response = client.get(self._url(pg.pk))
        booking_url = reverse("bookings:booking_create", kwargs={"bed_pk": bed.pk})
        assert booking_url.encode() not in response.content

    def test_inactive_pg_returns_404(self, client):
        tenant = _tenant()
        _login(client, tenant)
        pg = PGFactory(is_active=False)
        response = client.get(self._url(pg.pk))
        assert response.status_code == 404

    def test_nonexistent_pg_returns_404(self, client):
        tenant = _tenant()
        _login(client, tenant)
        response = client.get(self._url(99999))
        assert response.status_code == 404

    def test_does_not_expose_owner_info(self, client):
        tenant = _tenant()
        _login(client, tenant)
        owner = UserFactory(email="owner_hidden@example.com", name="Hidden Owner")
        pg = PGFactory(owner=owner)
        response = client.get(self._url(pg.pk))
        assert b"owner_hidden@example.com" not in response.content
        assert b"Hidden Owner" not in response.content

    def test_inactive_rooms_hidden(self, client):
        tenant = _tenant()
        _login(client, tenant)
        pg = PGFactory()
        RoomFactory(pg=pg, room_number="Active", is_active=True, capacity=1)
        RoomFactory(pg=pg, room_number="Inactive", is_active=False, capacity=1)
        response = client.get(self._url(pg.pk))
        content = response.content.decode()
        assert "Active" in content
        assert "Inactive" not in content

    def test_breadcrumb_links(self, client):
        tenant = _tenant()
        _login(client, tenant)
        pg = PGFactory()
        response = client.get(self._url(pg.pk))
        list_url = reverse("discovery:pg_list")
        assert list_url.encode() in response.content

    def test_availability_badges_shown(self, client):
        tenant = _tenant()
        _login(client, tenant)
        pg = PGFactory()
        room = RoomFactory(pg=pg, capacity=2)
        BedFactory(room=room, is_available=True, is_active=True)
        BedFactory(room=room, is_available=True, is_active=True)
        response = client.get(self._url(pg.pk))
        assert b"Available" in response.content
