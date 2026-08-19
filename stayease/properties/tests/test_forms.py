"""
Form tests for PG, Room, and Bed forms.

Covers: valid data, invalid data, validation rules, and capacity enforcement.
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
            "rent_per_month": "5000.00",
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

    def test_zero_rent_invalid(self):
        form = PGForm(data=self._valid_data(rent_per_month="0"))
        assert not form.is_valid()
        assert "rent_per_month" in form.errors

    def test_negative_rent_invalid(self):
        form = PGForm(data=self._valid_data(rent_per_month="-100"))
        assert not form.is_valid()
        assert "rent_per_month" in form.errors

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
            "rent": "3000.00",
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

    def test_rent_zero_invalid(self):
        form = RoomForm(data=self._valid_data(rent="0"))
        assert not form.is_valid()
        assert "rent" in form.errors

    def test_rent_negative_invalid(self):
        form = RoomForm(data=self._valid_data(rent="-500"))
        assert not form.is_valid()

    def test_blank_room_type_allowed(self):
        form = RoomForm(data=self._valid_data(room_type=""))
        assert form.is_valid(), form.errors


# ---------------------------------------------------------------------------
# BedForm
# ---------------------------------------------------------------------------


class TestBedForm:
    def test_valid_data(self):
        room = RoomFactory(capacity=3)
        form = BedForm(data={"label": "Bed A", "is_available": True}, room=room)
        assert form.is_valid(), form.errors

    def test_missing_label_invalid(self):
        room = RoomFactory(capacity=3)
        form = BedForm(data={"label": "", "is_available": True}, room=room)
        assert not form.is_valid()
        assert "label" in form.errors

    def test_capacity_exceeded(self):
        """Cannot add a bed when room is already at capacity."""
        room = RoomFactory(capacity=1)
        BedFactory(room=room, label="Bed A")
        form = BedForm(data={"label": "Bed B", "is_available": True}, room=room)
        assert not form.is_valid()

    def test_capacity_not_exceeded(self):
        """Can add a bed when room is below capacity."""
        room = RoomFactory(capacity=2)
        BedFactory(room=room, label="Bed A")
        form = BedForm(data={"label": "Bed B", "is_available": True}, room=room)
        assert form.is_valid(), form.errors

    def test_inactive_beds_not_counted_for_capacity(self):
        """Inactive beds don't count against capacity."""
        room = RoomFactory(capacity=1)
        BedFactory(room=room, label="Bed A", is_active=False)
        form = BedForm(data={"label": "Bed B", "is_available": True}, room=room)
        assert form.is_valid(), form.errors
