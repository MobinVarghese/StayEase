"""
Model-level tests for PG, Room, and Bed.

Covers: relationships, unique constraints, __str__, and field defaults.
"""

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError

from stayease.properties.models import Bed, PG, Room
from stayease.properties.tests.factories import BedFactory
from stayease.properties.tests.factories import PGFactory
from stayease.properties.tests.factories import RoomFactory


pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# PG
# ---------------------------------------------------------------------------


class TestPGModel:
    def test_str(self):
        pg = PGFactory(name="Green Valley PG")
        assert str(pg) == "Green Valley PG"

    def test_owner_relationship(self):
        pg = PGFactory()
        assert pg.owner is not None
        assert pg.owner.is_owner

    def test_is_active_default_true(self):
        pg = PGFactory()
        assert pg.is_active is True

    def test_timestamps_populated(self):
        pg = PGFactory()
        assert pg.created_at is not None
        assert pg.updated_at is not None

    def test_owner_pgs_reverse_relation(self):
        pg = PGFactory()
        assert pg in pg.owner.pgs.all()


# ---------------------------------------------------------------------------
# Room
# ---------------------------------------------------------------------------


class TestRoomModel:
    def test_str(self):
        pg = PGFactory(name="Sunrise PG")
        room = RoomFactory(pg=pg, room_number="101")
        assert str(room) == "Sunrise PG - Room 101"

    def test_belongs_to_pg(self):
        room = RoomFactory()
        assert room.pg is not None

    def test_unique_room_number_per_pg(self):
        pg = PGFactory()
        RoomFactory(pg=pg, room_number="101")
        with pytest.raises(IntegrityError):
            RoomFactory(pg=pg, room_number="101")

    def test_same_room_number_different_pgs(self):
        """Room numbers can repeat across different PGs."""
        pg1 = PGFactory()
        pg2 = PGFactory()
        r1 = RoomFactory(pg=pg1, room_number="101")
        r2 = RoomFactory(pg=pg2, room_number="101")
        assert r1.pk != r2.pk

    def test_is_active_default_true(self):
        room = RoomFactory()
        assert room.is_active is True

    def test_clean_single_room_capacity_1_valid(self):
        pg = PGFactory()
        room = Room(pg=pg, room_number="101", room_type="Single", capacity=1)
        room.clean()  # Should not raise

    def test_clean_single_room_capacity_not_1_raises(self):
        pg = PGFactory()
        room = Room(pg=pg, room_number="101", room_type="Single", capacity=2)
        with pytest.raises(ValidationError) as exc_info:
            room.clean()
        assert "capacity" in exc_info.value.message_dict
        assert any("1 bed" in msg for msg in exc_info.value.message_dict["capacity"])

    def test_clean_double_room_capacity_2_valid(self):
        pg = PGFactory()
        room = Room(pg=pg, room_number="101", room_type="Double", capacity=2)
        room.clean()  # Should not raise

    def test_clean_double_room_capacity_not_2_raises(self):
        pg = PGFactory()
        room = Room(pg=pg, room_number="101", room_type="Double", capacity=3)
        with pytest.raises(ValidationError) as exc_info:
            room.clean()
        assert "capacity" in exc_info.value.message_dict
        assert any("2 beds" in msg for msg in exc_info.value.message_dict["capacity"])

    def test_clean_cannot_change_existing_room_to_single_if_multiple_beds(self):
        room = RoomFactory(room_type="Double", capacity=2)
        BedFactory(room=room, label="Bed 1")
        BedFactory(room=room, label="Bed 2")
        room.room_type = "Single"
        room.capacity = 1
        with pytest.raises(ValidationError) as exc_info:
            room.clean()
        assert "room_type" in exc_info.value.message_dict
        assert any("already has 2 active beds" in msg for msg in exc_info.value.message_dict["room_type"])


# ---------------------------------------------------------------------------
# Bed
# ---------------------------------------------------------------------------


class TestBedModel:
    def test_str(self):
        pg = PGFactory(name="Sunrise PG")
        room = RoomFactory(pg=pg, room_number="202")
        bed = BedFactory(room=room, label="Bed A")
        assert "Sunrise PG - Room 202 - Bed A" in str(bed)

    def test_belongs_to_room(self):
        bed = BedFactory()
        assert bed.room is not None

    def test_unique_label_per_room(self):
        room = RoomFactory()
        BedFactory(room=room, label="Bed A")
        with pytest.raises(IntegrityError):
            BedFactory(room=room, label="Bed A")

    def test_same_label_different_rooms(self):
        """Bed labels can repeat across different rooms."""
        room1 = RoomFactory()
        room2 = RoomFactory()
        b1 = BedFactory(room=room1, label="Bed A")
        b2 = BedFactory(room=room2, label="Bed A")
        assert b1.pk != b2.pk

    def test_is_available_default_true(self):
        bed = BedFactory()
        assert bed.is_available is True

    def test_is_active_default_true(self):
        bed = BedFactory()
        assert bed.is_active is True

    def test_clean_cannot_add_second_bed_to_single_room(self):
        room = RoomFactory(room_type="Single", capacity=1)
        BedFactory(room=room, label="Bed 1")
        bed2 = Bed(room=room, label="Bed 2", is_active=True)
        with pytest.raises(ValidationError) as exc_info:
            bed2.clean()
        assert any("single room can only have 1 bed" in err for err in exc_info.value.messages)

    def test_clean_cannot_add_third_bed_to_double_room(self):
        room = RoomFactory(room_type="Double", capacity=2)
        BedFactory(room=room, label="Bed 1")
        BedFactory(room=room, label="Bed 2")
        bed3 = Bed(room=room, label="Bed 3", is_active=True)
        with pytest.raises(ValidationError) as exc_info:
            bed3.clean()
        assert any("double room can only have 2 beds" in err for err in exc_info.value.messages)


# ---------------------------------------------------------------------------
# Cascade Deletion
# ---------------------------------------------------------------------------


class TestCascadeDeletion:
    def test_deleting_pg_deletes_rooms_and_beds(self):
        pg = PGFactory()
        room = RoomFactory(pg=pg)
        BedFactory(room=room)
        BedFactory(room=room)

        pg_pk = pg.pk
        pg.delete()

        from stayease.properties.models import Bed
        from stayease.properties.models import PG
        from stayease.properties.models import Room

        assert not PG.objects.filter(pk=pg_pk).exists()
        assert not Room.objects.filter(pg_id=pg_pk).exists()
        assert not Bed.objects.filter(room__pg_id=pg_pk).exists()

    def test_deleting_room_deletes_beds(self):
        room = RoomFactory()
        BedFactory(room=room)
        room_pk = room.pk
        room.delete()

        from stayease.properties.models import Bed

        assert not Bed.objects.filter(room_id=room_pk).exists()
