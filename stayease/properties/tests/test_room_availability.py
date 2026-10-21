"""
Tests for dynamic Room and Bed availability and occupancy derivation.

Covers:
1. Room with all beds available -> "Active / Available"
2. Room with one confirmed bed and one available bed -> "Active / Partially occupied"
3. Room with all beds occupied -> "Full / Unavailable"
4. Cancelled / rejected booking releases the bed -> becomes Available again
5. Rejected booking does not keep the bed occupied
6. Owner dashboard reflects current room/bed occupancy and status dynamically
7. Tenant discovery / booking flow uses the same availability logic
8. One owner's room/bed state cannot affect another owner's dashboard
"""

from decimal import Decimal

import pytest
from django.urls import reverse

from stayease.bookings.models import Booking
from stayease.bookings.models import BookingStatus
from stayease.bookings.services import reject_booking
from stayease.discovery.services import get_rooms_with_availability
from stayease.properties.models import Bed
from stayease.properties.models import PG
from stayease.properties.models import Room
from stayease.properties.tests.factories import BedFactory
from stayease.properties.tests.factories import PGFactory
from stayease.properties.tests.factories import RoomFactory
from stayease.users.models import UserRole
from stayease.users.tests.factories import UserFactory


pytestmark = pytest.mark.django_db


class TestRoomAvailabilityModelLogic:
    def test_room_with_all_beds_available_is_active(self):
        """1. Room with all beds available -> Active / Available."""
        room = RoomFactory(capacity=2)
        BedFactory(room=room, label="Bed A", is_available=True)
        BedFactory(room=room, label="Bed B", is_available=True)

        stats = room.get_availability_stats()
        assert stats["total"] == 2
        assert stats["occupied"] == 0
        assert stats["available"] == 2
        assert stats["status"] == "Active / Available"
        assert stats["status_code"] == "AVAILABLE"
        assert room.availability_status == "Active / Available"
        assert room.is_bookable is True

    def test_room_with_one_confirmed_bed_is_partially_occupied(self):
        """2. Room with one confirmed bed and one available bed -> Active / Partially occupied."""
        tenant = UserFactory(role=UserRole.TENANT)
        room = RoomFactory(capacity=2)
        bed_a = BedFactory(room=room, label="Bed A", is_available=True)
        bed_b = BedFactory(room=room, label="Bed B", is_available=True)

        # Confirm booking on Bed A
        Booking.objects.create(tenant=tenant, bed=bed_a, status=BookingStatus.CONFIRMED)

        stats = room.get_availability_stats()
        assert stats["total"] == 2
        assert stats["occupied"] == 1
        assert stats["available"] == 1
        assert stats["status"] == "Active / Partially occupied"
        assert stats["status_code"] == "PARTIALLY_OCCUPIED"
        assert room.availability_status == "Active / Partially occupied"
        assert room.is_bookable is True

        assert bed_a.is_occupied is True
        assert bed_a.is_bookable is False
        assert bed_b.is_occupied is False
        assert bed_b.is_bookable is True

    def test_room_with_all_beds_occupied_is_full(self):
        """3. Room with all beds occupied -> Full / Unavailable."""
        tenant1 = UserFactory(role=UserRole.TENANT)
        tenant2 = UserFactory(role=UserRole.TENANT)
        room = RoomFactory(capacity=2)
        bed_a = BedFactory(room=room, label="Bed A", is_available=True)
        bed_b = BedFactory(room=room, label="Bed B", is_available=True)

        Booking.objects.create(tenant=tenant1, bed=bed_a, status=BookingStatus.CONFIRMED)
        Booking.objects.create(tenant=tenant2, bed=bed_b, status=BookingStatus.CONFIRMED)

        stats = room.get_availability_stats()
        assert stats["total"] == 2
        assert stats["occupied"] == 2
        assert stats["available"] == 0
        assert stats["status"] == "Full / Unavailable"
        assert stats["status_code"] == "FULL"
        assert room.availability_status == "Full / Unavailable"
        assert room.is_bookable is False

    def test_cancelled_or_rejected_booking_releases_bed(self):
        """4 & 5. Rejecting or cancelling a booking releases the bed back to available."""
        owner = UserFactory(role=UserRole.OWNER)
        tenant = UserFactory(role=UserRole.TENANT)
        pg = PGFactory(owner=owner)
        room = RoomFactory(pg=pg, capacity=1)
        bed = BedFactory(room=room, label="Bed A", is_available=True)

        # Pending booking -> occupied
        booking = Booking.objects.create(tenant=tenant, bed=bed, status=BookingStatus.PENDING)
        assert bed.is_occupied is True
        assert bed.is_bookable is False
        assert room.availability_status == "Full / Unavailable"

        # Owner rejects booking
        reject_booking(booking=booking, owner=owner)
        booking.refresh_from_db()
        assert booking.status == BookingStatus.REJECTED

        # Bed is now released and room is Active / Available
        assert bed.is_occupied is False
        assert bed.is_bookable is True
        assert room.availability_status == "Active / Available"

    def test_manually_disabled_room_or_bed_is_respected(self):
        """Owner deactivating room or bed manually is respected."""
        room = RoomFactory(capacity=1, is_active=False)
        BedFactory(room=room, label="Bed A", is_available=True)
        assert room.availability_status == "Inactive"
        assert room.is_bookable is False

        # Active room with owner-disabled bed
        room2 = RoomFactory(capacity=1, is_active=True)
        bed2 = BedFactory(room=room2, label="Bed B", is_available=False)
        assert bed2.is_bookable is False
        assert room2.availability_status == "Full / Unavailable"


class TestOwnerDashboardRoomIntegration:
    def test_owner_dashboard_reflects_room_status_and_occupancy(self, client):
        """6. Owner dashboard reflects current room/bed state every time page loads."""
        owner = UserFactory(role=UserRole.OWNER)
        tenant = UserFactory(role=UserRole.TENANT)
        pg = PGFactory(owner=owner, name="Sunrise PG")
        room1 = RoomFactory(pg=pg, room_number="101", capacity=2)
        bed1_a = BedFactory(room=room1, label="Bed 101-A", is_available=True)
        bed1_b = BedFactory(room=room1, label="Bed 101-B", is_available=True)

        client.force_login(owner)
        url = reverse("users:dashboard_owner")

        # Initial state: 0 occupied, 2 available -> Active / Available
        resp1 = client.get(url)
        assert resp1.status_code == 200
        content1 = resp1.content.decode("utf-8")
        assert "Sunrise PG" in content1
        assert "Room 101" in content1
        assert "Active / Available" in content1

        # Tenant confirms Bed 101-A
        Booking.objects.create(tenant=tenant, bed=bed1_a, status=BookingStatus.CONFIRMED)

        # Refresh dashboard: Room 101 is now Partially occupied
        resp2 = client.get(url)
        assert resp2.status_code == 200
        content2 = resp2.content.decode("utf-8")
        assert "1 occupied" in content2
        assert "1 available" in content2
        assert "Active / Partially occupied" in content2

        # Tenant confirms Bed 101-B: Room 101 is now Full / Unavailable
        Booking.objects.create(tenant=tenant, bed=bed1_b, status=BookingStatus.CONFIRMED)
        resp3 = client.get(url)
        assert resp3.status_code == 200
        content3 = resp3.content.decode("utf-8")
        assert "2 occupied" in content3
        assert "0 available" in content3
        assert "Full / Unavailable" in content3

    def test_owner_data_isolation_between_owners(self, client):
        """8. One owner's room/bed state cannot affect another owner's dashboard."""
        owner1 = UserFactory(role=UserRole.OWNER, first_name="OwnerOne")
        owner2 = UserFactory(role=UserRole.OWNER, first_name="OwnerTwo")
        tenant = UserFactory(role=UserRole.TENANT)

        pg1 = PGFactory(owner=owner1, name="Owner One PG")
        room1 = RoomFactory(pg=pg1, room_number="101", capacity=2)
        bed1 = BedFactory(room=room1, label="Bed 1", is_available=True)

        pg2 = PGFactory(owner=owner2, name="Owner Two PG")
        room2 = RoomFactory(pg=pg2, room_number="201", capacity=1)
        bed2 = BedFactory(room=room2, label="Bed 2", is_available=True)

        # Confirm booking on Owner 2's bed
        Booking.objects.create(tenant=tenant, bed=bed2, status=BookingStatus.CONFIRMED)

        # Check Owner 1 dashboard: must not show room2 or Owner 2 PG or the booking
        client.force_login(owner1)
        resp = client.get(reverse("users:dashboard_owner"))
        assert resp.status_code == 200
        content = resp.content.decode("utf-8")

        assert "Owner One PG" in content
        assert "Room 101" in content
        assert "Owner Two PG" not in content
        assert "Room 201" not in content
        assert resp.context["available_beds_count"] == 1


class TestTenantDiscoveryConsistency:
    def test_discovery_uses_same_availability_logic(self):
        """7. Tenant discovery uses same availability: occupied beds cannot be booked."""
        owner = UserFactory(role=UserRole.OWNER)
        tenant = UserFactory(role=UserRole.TENANT)
        pg = PGFactory(owner=owner)
        room = RoomFactory(pg=pg, room_number="301", capacity=2)
        bed_a = BedFactory(room=room, label="Bed A", is_available=True)
        bed_b = BedFactory(room=room, label="Bed B", is_available=True)

        # Confirm booking on Bed A
        Booking.objects.create(tenant=tenant, bed=bed_a, status=BookingStatus.CONFIRMED)

        rooms_data = get_rooms_with_availability(pg)
        assert len(rooms_data) == 1
        room_data = rooms_data[0]
        assert room_data["available_count"] == 1
        assert room_data["total_active_count"] == 2

        beds = room_data["beds"]
        bed_a_info = next(b for b in beds if b["bed"].pk == bed_a.pk)
        bed_b_info = next(b for b in beds if b["bed"].pk == bed_b.pk)

        assert bed_a_info["is_bookable"] is False
        assert bed_a_info["is_occupied"] is True
        assert bed_b_info["is_bookable"] is True
        assert bed_b_info["is_occupied"] is False
