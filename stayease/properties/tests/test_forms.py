"""
Form tests for PG, Room, and Bed forms.

Covers: valid data, invalid data, validation rules, capacity enforcement, and bed rent validation.
"""

from decimal import Decimal

import pytest

from stayease.properties.forms import BedForm
from stayease.properties.forms import PGForm
from stayease.properties.forms import RoomForm
from stayease.properties.tests.factories import BedFactory
from stayease.properties.tests.factories import RoomFactory


pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# PGForm
# ---------------------------------------------------------------------------


class TestPGForm:
    def _valid_data(self, **overrides):
        defaults = {
            "name": "Test PG",
            "description": "A nice place",
            "address": "123 Street",
            "city": "Bangalore",
            "amenities": "Wi-Fi",
        }
        defaults.update(overrides)
        return defaults

    def test_valid_data(self):
        form = PGForm(data=self._valid_data())
        assert form.is_valid(), form.errors

    def test_missing_required_field(self):
        form = PGForm(data=self._valid_data(name=""))
        assert not form.is_valid()
        assert "name" in form.errors

    def test_missing_address(self):
        form = PGForm(data=self._valid_data(address=""))
        assert not form.is_valid()
        assert "address" in form.errors

    def test_blank_description_allowed(self):
        form = PGForm(data=self._valid_data(description=""))
        assert form.is_valid(), form.errors

    def test_blank_amenities_allowed(self):
        form = PGForm(data=self._valid_data(amenities=""))
        assert form.is_valid(), form.errors


# ---------------------------------------------------------------------------
# RoomForm
# ---------------------------------------------------------------------------


class TestRoomForm:
    def _valid_data(self, **overrides):
        defaults = {
            "room_number": "101",
            "room_type": "Double",
            "capacity": "2",
            "description": "",
        }
        defaults.update(overrides)
        return defaults

    def test_valid_data(self):
        form = RoomForm(data=self._valid_data())
        assert form.is_valid(), form.errors

    def test_capacity_zero_invalid(self):
        form = RoomForm(data=self._valid_data(capacity="0"))
        assert not form.is_valid()
        assert "capacity" in form.errors

    def test_capacity_negative_invalid(self):
        form = RoomForm(data=self._valid_data(capacity="-1"))
        assert not form.is_valid()

    def test_blank_room_type_allowed(self):
        form = RoomForm(data=self._valid_data(room_type=""))
        assert form.is_valid(), form.errors

    def test_single_room_valid_with_capacity_1(self):
        form = RoomForm(data=self._valid_data(room_type="Single", capacity="1"))
        assert form.is_valid(), form.errors

    def test_single_room_invalid_with_capacity_not_1(self):
        form = RoomForm(data=self._valid_data(room_type="Single", capacity="2"))
        assert not form.is_valid()
        assert "capacity" in form.errors
        assert any("1 bed" in str(err) for err in form.errors["capacity"])

    def test_double_room_valid_with_capacity_2(self):
        form = RoomForm(data=self._valid_data(room_type="Double", capacity="2"))
        assert form.is_valid(), form.errors

    def test_double_room_invalid_with_capacity_not_2(self):
        form = RoomForm(data=self._valid_data(room_type="Double", capacity="3"))
        assert not form.is_valid()
        assert "capacity" in form.errors
        assert any("2 beds" in str(err) for err in form.errors["capacity"])

    def test_cannot_change_existing_room_to_single_if_multiple_active_beds(self):
        room = RoomFactory(room_type="Double", capacity=2)
        BedFactory(room=room, label="Bed A")
        BedFactory(room=room, label="Bed B")
        form = RoomForm(
            instance=room,
            data=self._valid_data(room_type="Single", capacity="1"),
        )
        assert not form.is_valid()
        assert "room_type" in form.errors
        assert any("already has 2 active beds" in str(err) for err in form.errors["room_type"])

    def test_cannot_change_existing_room_to_double_if_more_than_two_active_beds(self):
        room = RoomFactory(room_type="Triple", capacity=3)
        BedFactory(room=room, label="Bed A")
        BedFactory(room=room, label="Bed B")
        BedFactory(room=room, label="Bed C")
        form = RoomForm(
            instance=room,
            data=self._valid_data(room_type="Double", capacity="2"),
        )
        assert not form.is_valid()
        assert "room_type" in form.errors
        assert any("already has 3 active beds" in str(err) for err in form.errors["room_type"])


# ---------------------------------------------------------------------------
# BedForm
# ---------------------------------------------------------------------------


class TestBedForm:
    def test_valid_data(self):
        room = RoomFactory(capacity=3)
        form = BedForm(
            data={"label": "Bed A", "rent_per_month": "3500.00", "is_available": True},
            room=room,
        )
        assert form.is_valid(), form.errors

    def test_missing_label_invalid(self):
        room = RoomFactory(capacity=3)
        form = BedForm(
            data={"label": "", "rent_per_month": "3500.00", "is_available": True},
            room=room,
        )
        assert not form.is_valid()
        assert "label" in form.errors

    def test_missing_rent_invalid(self):
        room = RoomFactory(capacity=3)
        form = BedForm(data={"label": "Bed A", "is_available": True}, room=room)
        assert not form.is_valid()
        assert "rent_per_month" in form.errors

    def test_zero_rent_invalid(self):
        room = RoomFactory(capacity=3)
        form = BedForm(
            data={"label": "Bed A", "rent_per_month": "0", "is_available": True},
            room=room,
        )
        assert not form.is_valid()
        assert "rent_per_month" in form.errors

    def test_negative_rent_invalid(self):
        room = RoomFactory(capacity=3)
        form = BedForm(
            data={"label": "Bed A", "rent_per_month": "-500", "is_available": True},
            room=room,
        )
        assert not form.is_valid()
        assert "rent_per_month" in form.errors

    def test_capacity_exceeded(self):
        """Cannot add a bed when room is already at capacity."""
        room = RoomFactory(capacity=1)
        BedFactory(room=room, label="Bed A", rent_per_month=Decimal("3000.00"))
        form = BedForm(
            data={"label": "Bed B", "rent_per_month": "3000.00", "is_available": True},
            room=room,
        )
        assert not form.is_valid()

    def test_capacity_not_exceeded(self):
        """Can add a bed when room is below capacity."""
        room = RoomFactory(capacity=2)
        BedFactory(room=room, label="Bed A", rent_per_month=Decimal("3000.00"))
        form = BedForm(
            data={"label": "Bed B", "rent_per_month": "3200.00", "is_available": True},
            room=room,
        )
        assert form.is_valid(), form.errors

    def test_inactive_beds_not_counted_for_capacity(self):
        """Inactive beds don't count against capacity."""
        room = RoomFactory(capacity=1)
        BedFactory(room=room, label="Bed A", rent_per_month=Decimal("3000.00"), is_active=False)
        form = BedForm(
            data={"label": "Bed B", "rent_per_month": "3000.00", "is_available": True},
            room=room,
        )
        assert form.is_valid(), form.errors

    def test_cannot_add_second_bed_to_single_room(self):
        """Single room strictly permits only 1 bed."""
        room = RoomFactory(room_type="Single", capacity=1)
        BedFactory(room=room, label="Bed 1", rent_per_month=Decimal("3000.00"))
        form = BedForm(
            data={"label": "Bed 2", "rent_per_month": "3000.00", "is_available": True},
            room=room,
        )
        assert not form.is_valid()
        assert any("single room can only have 1 bed" in str(err) for err in form.non_field_errors())

    def test_cannot_add_third_bed_to_double_room(self):
        """Double room strictly permits only 2 beds."""
        room = RoomFactory(room_type="Double", capacity=2)
        BedFactory(room=room, label="Bed 1", rent_per_month=Decimal("3000.00"))
        BedFactory(room=room, label="Bed 2", rent_per_month=Decimal("3000.00"))
        form = BedForm(
            data={"label": "Bed 3", "rent_per_month": "3000.00", "is_available": True},
            room=room,
        )
        assert not form.is_valid()
        assert any("double room can only have 2 beds" in str(err) for err in form.non_field_errors())

    def test_can_add_one_bed_to_single_room(self):
        room = RoomFactory(room_type="Single", capacity=1)
        form = BedForm(
            data={"label": "Bed 1", "rent_per_month": "3000.00", "is_available": True},
            room=room,
        )
        assert form.is_valid(), form.errors

    def test_can_add_two_beds_to_double_room(self):
        room = RoomFactory(room_type="Double", capacity=2)
        BedFactory(room=room, label="Bed 1", rent_per_month=Decimal("3000.00"))
        form = BedForm(
            data={"label": "Bed 2", "rent_per_month": "3000.00", "is_available": True},
            room=room,
        )
        assert form.is_valid(), form.errors
