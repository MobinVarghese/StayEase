"""
Tests for discovery service layer.

These tests verify that search_pgs(), get_active_pgs_queryset(),
get_rooms_with_availability(), and helper functions work correctly
at the database level.

Business logic ownership: Member 3
Model ownership: Member 2 (PG/Room/Bed), Member 4 (Booking)
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from stayease.bookings.models import BookingStatus
from stayease.bookings.tests.factories import BookingFactory
from stayease.discovery.services import (
    _to_decimal,
    get_active_pgs_queryset,
    get_distinct_cities,
    get_rooms_with_availability,
    search_pgs,
)
from stayease.properties.tests.factories import BedFactory, PGFactory, RoomFactory


# ======================================================================
# get_active_pgs_queryset
# ======================================================================


@pytest.mark.django_db
class TestGetActivePgsQueryset:
    """Base queryset: only active PGs with available_bed_count annotation."""

    def test_only_active_pgs_returned(self):
        active_pg = PGFactory(is_active=True)
        PGFactory(is_active=False)  # inactive — should not appear
        qs = get_active_pgs_queryset()
        assert list(qs) == [active_pg]

    def test_available_bed_count_annotation(self):
        pg = PGFactory()
        room = RoomFactory(pg=pg, capacity=3)
        BedFactory(room=room, is_available=True, is_active=True)
        BedFactory(room=room, is_available=True, is_active=True)
        BedFactory(room=room, is_available=False, is_active=True)  # not available
        qs = get_active_pgs_queryset()
        result = qs.get(pk=pg.pk)
        assert result.available_bed_count == 2

    def test_bed_with_active_booking_not_counted(self):
        pg = PGFactory()
        room = RoomFactory(pg=pg, capacity=2)
        bed1 = BedFactory(room=room, is_available=True, is_active=True)
        BedFactory(room=room, is_available=True, is_active=True)
        # Bed1 has an active booking → should not count as available.
        BookingFactory(bed=bed1, status=BookingStatus.PENDING)
        qs = get_active_pgs_queryset()
        result = qs.get(pk=pg.pk)
        assert result.available_bed_count == 1

    def test_bed_with_rejected_booking_still_counted(self):
        pg = PGFactory()
        room = RoomFactory(pg=pg, capacity=1)
        bed = BedFactory(room=room, is_available=True, is_active=True)
        BookingFactory(bed=bed, status=BookingStatus.REJECTED)
        qs = get_active_pgs_queryset()
        result = qs.get(pk=pg.pk)
        assert result.available_bed_count == 1

    def test_inactive_room_beds_not_counted(self):
        pg = PGFactory()
        active_room = RoomFactory(pg=pg, capacity=1, is_active=True)
        inactive_room = RoomFactory(pg=pg, capacity=1, is_active=False)
        BedFactory(room=active_room, is_available=True, is_active=True)
        BedFactory(room=inactive_room, is_available=True, is_active=True)
        qs = get_active_pgs_queryset()
        result = qs.get(pk=pg.pk)
        assert result.available_bed_count == 1

    def test_inactive_bed_not_counted(self):
        pg = PGFactory()
        room = RoomFactory(pg=pg, capacity=2)
        BedFactory(room=room, is_available=True, is_active=True)
        BedFactory(room=room, is_available=True, is_active=False)  # inactive
        qs = get_active_pgs_queryset()
        result = qs.get(pk=pg.pk)
        assert result.available_bed_count == 1

    def test_pg_with_no_rooms_has_zero_count(self):
        pg = PGFactory()
        qs = get_active_pgs_queryset()
        result = qs.get(pk=pg.pk)
        assert result.available_bed_count == 0


# ======================================================================
# search_pgs
# ======================================================================


@pytest.mark.django_db
class TestSearchPgs:
    """Filtering and search via query parameters."""

    def test_empty_params_returns_all_active(self):
        pg1 = PGFactory(is_active=True)
        pg2 = PGFactory(is_active=True)
        PGFactory(is_active=False)
        result = list(search_pgs({}))
        assert pg1 in result
        assert pg2 in result
        assert len(result) == 2

    def test_keyword_search_by_name(self):
        pg = PGFactory(name="Green Valley PG")
        PGFactory(name="Blue Mountain PG")
        result = list(search_pgs({"q": "green"}))
        assert result == [pg]

    def test_keyword_search_by_description(self):
        pg = PGFactory(description="Spacious rooms with balcony")
        PGFactory(description="Budget accommodation")
        result = list(search_pgs({"q": "balcony"}))
        assert result == [pg]

    def test_keyword_search_by_city(self):
        pg = PGFactory(city="Bangalore")
        PGFactory(city="Mumbai")
        result = list(search_pgs({"q": "Bangalore"}))
        assert result == [pg]

    def test_keyword_search_by_amenities(self):
        pg = PGFactory(amenities="Wi-Fi, Gym, Parking")
        PGFactory(amenities="Wi-Fi, Laundry")
        result = list(search_pgs({"q": "Gym"}))
        assert result == [pg]

    def test_city_filter_exact(self):
        pg = PGFactory(city="Bangalore")
        PGFactory(city="Mumbai")
        result = list(search_pgs({"city": "Bangalore"}))
        assert result == [pg]

    def test_city_filter_case_insensitive(self):
        pg = PGFactory(city="Bangalore")
        result = list(search_pgs({"city": "bangalore"}))
        assert result == [pg]

    def test_min_price_filter(self):
        cheap = PGFactory(rent_per_month=Decimal("3000.00"))
        PGFactory(rent_per_month=Decimal("1000.00"))
        result = list(search_pgs({"min_price": "2000"}))
        assert result == [cheap]

    def test_max_price_filter(self):
        PGFactory(rent_per_month=Decimal("8000.00"))
        cheap = PGFactory(rent_per_month=Decimal("3000.00"))
        result = list(search_pgs({"max_price": "5000"}))
        assert result == [cheap]

    def test_price_range_filter(self):
        pg = PGFactory(rent_per_month=Decimal("5000.00"))
        PGFactory(rent_per_month=Decimal("1000.00"))
        PGFactory(rent_per_month=Decimal("10000.00"))
        result = list(search_pgs({"min_price": "4000", "max_price": "6000"}))
        assert result == [pg]

    def test_available_only_filter(self):
        pg_with_beds = PGFactory()
        room = RoomFactory(pg=pg_with_beds, capacity=1)
        BedFactory(room=room, is_available=True, is_active=True)
        pg_no_beds = PGFactory()  # no rooms/beds
        result = list(search_pgs({"available_only": "1"}))
        assert pg_with_beds in result
        assert pg_no_beds not in result

    def test_combined_filters(self):
        target = PGFactory(
            name="Target PG",
            city="Delhi",
            rent_per_month=Decimal("5000.00"),
        )
        room = RoomFactory(pg=target, capacity=1)
        BedFactory(room=room, is_available=True, is_active=True)
        PGFactory(city="Delhi", rent_per_month=Decimal("20000.00"))
        PGFactory(city="Mumbai", rent_per_month=Decimal("5000.00"))
        result = list(search_pgs({
            "q": "Target",
            "city": "Delhi",
            "max_price": "10000",
            "available_only": "1",
        }))
        assert result == [target]

    def test_empty_search_results(self):
        PGFactory(name="Something Else")
        result = list(search_pgs({"q": "nonexistent_xyz_term"}))
        assert result == []

    def test_invalid_price_ignored(self):
        pg = PGFactory()
        result = list(search_pgs({"min_price": "abc"}))
        assert pg in result

    def test_negative_price_ignored(self):
        pg = PGFactory()
        result = list(search_pgs({"min_price": "-100"}))
        assert pg in result


# ======================================================================
# get_rooms_with_availability
# ======================================================================


@pytest.mark.django_db
class TestGetRoomsWithAvailability:
    """Room/bed availability detail for the PG detail page."""

    def test_returns_rooms_with_beds(self):
        pg = PGFactory()
        room = RoomFactory(pg=pg, capacity=2)
        bed1 = BedFactory(room=room, is_available=True, is_active=True)
        bed2 = BedFactory(room=room, is_available=False, is_active=True)
        # Prefetch for the service to work
        pg = pg.__class__.objects.prefetch_related(
            "rooms__beds__bookings"
        ).get(pk=pg.pk)
        result = get_rooms_with_availability(pg)
        assert len(result) == 1
        assert result[0]["room"] == room
        assert len(result[0]["beds"]) == 2
        assert result[0]["available_count"] == 1
        assert result[0]["total_active_count"] == 2

    def test_bed_with_active_booking_not_bookable(self):
        pg = PGFactory()
        room = RoomFactory(pg=pg, capacity=1)
        bed = BedFactory(room=room, is_available=True, is_active=True)
        BookingFactory(bed=bed, status=BookingStatus.CONFIRMED)
        pg = pg.__class__.objects.prefetch_related(
            "rooms__beds__bookings"
        ).get(pk=pg.pk)
        result = get_rooms_with_availability(pg)
        assert result[0]["beds"][0]["is_bookable"] is False
        assert result[0]["available_count"] == 0

    def test_bed_with_rejected_booking_is_bookable(self):
        pg = PGFactory()
        room = RoomFactory(pg=pg, capacity=1)
        bed = BedFactory(room=room, is_available=True, is_active=True)
        BookingFactory(bed=bed, status=BookingStatus.REJECTED)
        pg = pg.__class__.objects.prefetch_related(
            "rooms__beds__bookings"
        ).get(pk=pg.pk)
        result = get_rooms_with_availability(pg)
        assert result[0]["beds"][0]["is_bookable"] is True

    def test_inactive_rooms_excluded(self):
        pg = PGFactory()
        RoomFactory(pg=pg, capacity=1, is_active=True)
        RoomFactory(pg=pg, capacity=1, is_active=False)
        pg = pg.__class__.objects.prefetch_related(
            "rooms__beds__bookings"
        ).get(pk=pg.pk)
        result = get_rooms_with_availability(pg)
        assert len(result) == 1

    def test_inactive_beds_excluded(self):
        pg = PGFactory()
        room = RoomFactory(pg=pg, capacity=2)
        BedFactory(room=room, is_active=True, is_available=True)
        BedFactory(room=room, is_active=False, is_available=True)
        pg = pg.__class__.objects.prefetch_related(
            "rooms__beds__bookings"
        ).get(pk=pg.pk)
        result = get_rooms_with_availability(pg)
        assert result[0]["total_active_count"] == 1

    def test_empty_pg(self):
        pg = PGFactory()
        pg = pg.__class__.objects.prefetch_related(
            "rooms__beds__bookings"
        ).get(pk=pg.pk)
        result = get_rooms_with_availability(pg)
        assert result == []


# ======================================================================
# get_distinct_cities
# ======================================================================


@pytest.mark.django_db
class TestGetDistinctCities:
    def test_returns_sorted_distinct_cities(self):
        PGFactory(city="Mumbai")
        PGFactory(city="Bangalore")
        PGFactory(city="Mumbai")  # duplicate
        PGFactory(city="Delhi", is_active=False)  # inactive
        result = get_distinct_cities()
        assert result == ["Bangalore", "Mumbai"]

    def test_empty_when_no_active_pgs(self):
        PGFactory(is_active=False)
        assert get_distinct_cities() == []


# ======================================================================
# _to_decimal (internal helper)
# ======================================================================


class TestToDecimal:
    def test_valid_number(self):
        assert _to_decimal("5000") == Decimal("5000")

    def test_empty_string(self):
        assert _to_decimal("") is None

    def test_none(self):
        assert _to_decimal(None) is None

    def test_negative(self):
        assert _to_decimal("-100") is None

    def test_invalid_string(self):
        assert _to_decimal("abc") is None

    def test_decimal_value(self):
        assert _to_decimal("3500.50") == Decimal("3500.50")
