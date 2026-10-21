"""
Dedicated test suite for the PG -> Room -> Bed -> Booking -> User hierarchy.

Covers:
1. Hierarchy traversal (PG -> Room -> Bed -> Booking -> User)
2. Multiple rooms per PG and multiple beds per room
3. Bed.rent_per_month is required and strictly positive
4. Room.starting_rent calculation based on active bed rents
5. PG.starting_rent calculation based on available/active bed rents across rooms
6. Dynamic updates to PG.starting_rent when beds are added or deactivated
7. Booking targets a specific bed and inherits its details
8. Single active booking per bed concurrency/uniqueness enforcement
9. Payment amount is derived strictly from booking.bed.rent_per_month
10. Discovery search price filtering works with bed-level rents
"""

from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError

from stayease.bookings.models import Booking
from stayease.bookings.models import BookingStatus
from stayease.discovery.services import search_pgs
from stayease.payments.models import Payment
from stayease.payments.models import PaymentStatus
from stayease.payments.services import initiate_payment
from stayease.properties.forms import BedForm
from stayease.properties.models import Bed
from stayease.properties.models import PG
from stayease.properties.models import Room
from stayease.properties.tests.factories import BedFactory
from stayease.properties.tests.factories import PGFactory
from stayease.properties.tests.factories import RoomFactory
from stayease.users.models import UserRole
from stayease.users.tests.factories import UserFactory


pytestmark = pytest.mark.django_db


class TestHierarchyRelationships:
    def test_full_hierarchy_navigation(self):
        """1. Verify full navigation: PG -> Room -> Bed -> Booking -> User."""
        owner = UserFactory(role=UserRole.OWNER)
        tenant = UserFactory(role=UserRole.TENANT)

        pg = PGFactory(owner=owner, name="Skyline PG", city="Bangalore")
        room = RoomFactory(pg=pg, room_number="201", capacity=2)
        bed = BedFactory(room=room, label="Bed 201-A", rent_per_month=Decimal("4500.00"))
        booking = Booking.objects.create(bed=bed, tenant=tenant, status=BookingStatus.PENDING)

        # Downward traversal
        assert room.pg == pg
        assert bed.room == room
        assert booking.bed == bed
        assert booking.tenant == tenant

        # Upward traversal
        assert booking.bed.room.pg == pg
        assert booking.bed.room.pg.owner == owner
        assert bed.room.pg.name == "Skyline PG"

    def test_multiple_rooms_and_beds(self):
        """2. A PG can have multiple rooms, each with multiple beds."""
        owner = UserFactory(role=UserRole.OWNER)
        pg = PGFactory(owner=owner)

        room1 = RoomFactory(pg=pg, room_number="101", capacity=2)
        room2 = RoomFactory(pg=pg, room_number="102", capacity=3)

        b1_1 = BedFactory(room=room1, label="B1", rent_per_month=Decimal("4000.00"))
        b1_2 = BedFactory(room=room1, label="B2", rent_per_month=Decimal("4200.00"))

        b2_1 = BedFactory(room=room2, label="B3", rent_per_month=Decimal("3500.00"))
        b2_2 = BedFactory(room=room2, label="B4", rent_per_month=Decimal("3600.00"))
        b2_3 = BedFactory(room=room2, label="B5", rent_per_month=Decimal("3800.00"))

        assert pg.rooms.count() == 2
        assert room1.beds.count() == 2
        assert room2.beds.count() == 3


class TestBedPricingValidation:
    def test_bed_rent_validation_in_form(self):
        """3. BedForm requires rent_per_month and ensures it is positive."""
        room = RoomFactory(capacity=2)

        # Missing rent
        form_missing = BedForm(data={"label": "Bed 1", "is_available": True}, room=room)
        assert not form_missing.is_valid()
        assert "rent_per_month" in form_missing.errors

        # Zero rent
        form_zero = BedForm(data={"label": "Bed 1", "rent_per_month": "0.00", "is_available": True}, room=room)
        assert not form_zero.is_valid()
        assert "rent_per_month" in form_zero.errors

        # Negative rent
        form_neg = BedForm(data={"label": "Bed 1", "rent_per_month": "-500.00", "is_available": True}, room=room)
        assert not form_neg.is_valid()
        assert "rent_per_month" in form_neg.errors

        # Valid positive rent
        form_valid = BedForm(data={"label": "Bed 1", "rent_per_month": "5500.00", "is_available": True}, room=room)
        assert form_valid.is_valid(), form_valid.errors


class TestStartingRentCalculations:
    def test_room_starting_rent(self):
        """4. Room.starting_rent equals min rent of active beds in the room."""
        room = RoomFactory(capacity=3)
        BedFactory(room=room, label="Bed A", rent_per_month=Decimal("5000.00"), is_active=True)
        BedFactory(room=room, label="Bed B", rent_per_month=Decimal("4200.00"), is_active=True)
        BedFactory(room=room, label="Bed C", rent_per_month=Decimal("4800.00"), is_active=False)  # inactive

        # Inactive bed with cheaper rent should NOT be picked
        assert room.starting_rent == Decimal("4200.00")

    def test_pg_starting_rent_across_rooms(self):
        """5. PG.starting_rent is min of available, active beds across active rooms."""
        pg = PGFactory(rent_per_month=None)
        room1 = RoomFactory(pg=pg, capacity=2, is_active=True)
        room2 = RoomFactory(pg=pg, capacity=2, is_active=True)

        # Room 1 beds: 6000 and 5500
        BedFactory(room=room1, rent_per_month=Decimal("6000.00"), is_available=True, is_active=True)
        BedFactory(room=room1, rent_per_month=Decimal("5500.00"), is_available=True, is_active=True)

        # Room 2 beds: 4800 (available), 4000 (unavailable)
        BedFactory(room=room2, rent_per_month=Decimal("4800.00"), is_available=True, is_active=True)
        BedFactory(room=room2, rent_per_month=Decimal("4000.00"), is_available=False, is_active=True)

        # Starting rent should pick available beds first: min(6000, 5500, 4800) = 4800
        assert pg.starting_rent == Decimal("4800.00")

    def test_dynamic_starting_rent_updates(self):
        """6. PG.starting_rent dynamically updates when cheaper bed is added or removed."""
        pg = PGFactory(rent_per_month=None)
        room = RoomFactory(pg=pg, capacity=3, is_active=True)

        bed1 = BedFactory(room=room, rent_per_month=Decimal("6000.00"), is_available=True, is_active=True)
        assert pg.starting_rent == Decimal("6000.00")

        # Add a cheaper bed
        bed2 = BedFactory(room=room, rent_per_month=Decimal("4500.00"), is_available=True, is_active=True)
        assert pg.starting_rent == Decimal("4500.00")

        # Mark cheaper bed unavailable
        bed2.is_available = False
        bed2.save()
        assert pg.starting_rent == Decimal("6000.00")


class TestBookingAndConcurrency:
    def test_booking_targets_specific_bed(self):
        """7. Booking specifically links to an individual bed."""
        tenant = UserFactory(role=UserRole.TENANT)
        bed = BedFactory(rent_per_month=Decimal("5200.00"))

        booking = Booking.objects.create(bed=bed, tenant=tenant, status=BookingStatus.PENDING)
        assert booking.bed == bed
        assert booking.bed.rent_per_month == Decimal("5200.00")

    def test_single_active_booking_per_bed(self):
        """8. Only one active booking allowed per bed."""
        tenant1 = UserFactory(role=UserRole.TENANT)
        tenant2 = UserFactory(role=UserRole.TENANT)
        bed = BedFactory(rent_per_month=Decimal("5000.00"))

        # First active booking
        Booking.objects.create(bed=bed, tenant=tenant1, status=BookingStatus.PENDING)

        # Second active booking on same bed should violate unique constraint
        with pytest.raises(IntegrityError):
            Booking.objects.create(bed=bed, tenant=tenant2, status=BookingStatus.PENDING)


class TestPaymentIntegration:
    def test_payment_amount_derived_from_bed_rent(self):
        """9. Payment amount is strictly derived from booking.bed.rent_per_month."""
        tenant = UserFactory(role=UserRole.TENANT)
        room = RoomFactory(rent=Decimal("9999.00"))  # Room rent should NOT be used
        bed = BedFactory(room=room, rent_per_month=Decimal("4300.00"))
        booking = Booking.objects.create(bed=bed, tenant=tenant, status=BookingStatus.APPROVED)

        payment = initiate_payment(booking=booking, user=tenant)

        assert payment.amount == Decimal("4300.00")
        assert payment.amount == booking.bed.rent_per_month
        assert payment.amount != room.rent


class TestDiscoveryIntegration:
    def test_discovery_filters_by_bed_rent(self):
        """10. Discovery search price filter respects annotated bed starting rents."""
        # PG A: starting bed rent = 3000
        pg_a = PGFactory(city="Pune", rent_per_month=None)
        room_a = RoomFactory(pg=pg_a, capacity=2)
        BedFactory(room=room_a, rent_per_month=Decimal("3000.00"), is_available=True)

        # PG B: starting bed rent = 7000
        pg_b = PGFactory(city="Pune", rent_per_month=None)
        room_b = RoomFactory(pg=pg_b, capacity=2)
        BedFactory(room=room_b, rent_per_month=Decimal("7000.00"), is_available=True)

        # Search for max price 5000 in Pune
        results = search_pgs({"city": "Pune", "max_price": "5000.00"})
        result_pks = [p.pk for p in results]

        assert pg_a.pk in result_pks
        assert pg_b.pk not in result_pks

        # Search for min price 5000 in Pune
        results_high = search_pgs({"city": "Pune", "min_price": "5000.00"})
        result_high_pks = [p.pk for p in results_high]

        assert pg_b.pk in result_high_pks
        assert pg_a.pk not in result_high_pks
