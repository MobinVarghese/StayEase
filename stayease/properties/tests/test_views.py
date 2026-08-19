"""
View tests for PG, Room, and Bed CRUD.

Covers:
  - CRUD happy paths
  - Owner isolation (Owner A cannot access Owner B's resources)
  - Unauthenticated access → redirect to login
  - Tenant role → 403
  - Soft-delete / hard-delete business rules
"""

from __future__ import annotations

import pytest
from django.test import Client
from django.urls import reverse

from stayease.properties.models import Bed
from stayease.properties.models import PG
from stayease.properties.models import Room
from stayease.properties.tests.factories import BedFactory
from stayease.properties.tests.factories import PGFactory
from stayease.properties.tests.factories import RoomFactory
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
# PG List
# ===========================================================================


class TestPGListView:
    def test_unauthenticated_redirect(self, client):
        url = reverse("properties:pg_list")
        resp = client.get(url)
        assert resp.status_code == 302
        assert "account" in resp.url or "login" in resp.url

    def test_tenant_forbidden(self, client):
        _login(client, _tenant())
        resp = client.get(reverse("properties:pg_list"))
        assert resp.status_code == 403

    def test_owner_sees_own_pgs(self, client):
        owner = _owner()
        PGFactory(owner=owner, name="My PG")
        PGFactory(name="Other PG")  # different owner
        _login(client, owner)
        resp = client.get(reverse("properties:pg_list"))
        assert resp.status_code == 200
        assert b"My PG" in resp.content
        assert b"Other PG" not in resp.content


# ===========================================================================
# PG Create
# ===========================================================================


class TestPGCreateView:
    def test_create_pg(self, client):
        owner = _owner()
        _login(client, owner)
        url = reverse("properties:pg_create")
        data = {
            "name": "New PG",
            "description": "A nice PG",
            "address": "123 Main St",
            "city": "Bangalore",
            "rent_per_month": "5000.00",
            "amenities": "Wi-Fi",
        }
        resp = client.post(url, data)
        assert resp.status_code == 302
        pg = PG.objects.get(name="New PG")
        assert pg.owner == owner

    def test_tenant_cannot_create(self, client):
        _login(client, _tenant())
        resp = client.post(reverse("properties:pg_create"), {})
        assert resp.status_code == 403


# ===========================================================================
# PG Detail
# ===========================================================================


class TestPGDetailView:
    def test_owner_views_own_pg(self, client):
        owner = _owner()
        pg = PGFactory(owner=owner)
        _login(client, owner)
        resp = client.get(reverse("properties:pg_detail", kwargs={"pg_pk": pg.pk}))
        assert resp.status_code == 200

    def test_owner_cannot_view_other_owners_pg(self, client):
        owner_a = _owner()
        pg = PGFactory()  # different owner
        _login(client, owner_a)
        resp = client.get(reverse("properties:pg_detail", kwargs={"pg_pk": pg.pk}))
        assert resp.status_code == 403


# ===========================================================================
# PG Update
# ===========================================================================


class TestPGUpdateView:
    def test_owner_updates_own_pg(self, client):
        owner = _owner()
        pg = PGFactory(owner=owner, name="Old Name")
        _login(client, owner)
        url = reverse("properties:pg_edit", kwargs={"pg_pk": pg.pk})
        data = {
            "name": "New Name",
            "description": pg.description,
            "address": pg.address,
            "city": pg.city,
            "rent_per_month": str(pg.rent_per_month),
            "amenities": pg.amenities,
        }
        resp = client.post(url, data)
        assert resp.status_code == 302
        pg.refresh_from_db()
        assert pg.name == "New Name"

    def test_owner_cannot_update_other_owners_pg(self, client):
        owner_a = _owner()
        pg = PGFactory()  # different owner
        _login(client, owner_a)
        resp = client.post(
            reverse("properties:pg_edit", kwargs={"pg_pk": pg.pk}),
            {"name": "Hacked"},
        )
        assert resp.status_code == 403


# ===========================================================================
# PG Delete
# ===========================================================================


class TestPGDeleteView:
    def test_hard_delete_pg_without_bookings(self, client):
        owner = _owner()
        pg = PGFactory(owner=owner)
        _login(client, owner)
        url = reverse("properties:pg_delete", kwargs={"pg_pk": pg.pk})
        resp = client.post(url)
        assert resp.status_code == 302
        assert not PG.objects.filter(pk=pg.pk).exists()

    def test_soft_delete_pg_with_bookings(self, client):
        """PG with booking history should be deactivated, not deleted."""
        from stayease.bookings.models import Booking

        owner = _owner()
        pg = PGFactory(owner=owner)
        room = RoomFactory(pg=pg)
        bed = BedFactory(room=room)
        tenant = _tenant()
        Booking.objects.create(tenant=tenant, bed=bed)

        _login(client, owner)
        url = reverse("properties:pg_delete", kwargs={"pg_pk": pg.pk})
        resp = client.post(url)
        assert resp.status_code == 302
        pg.refresh_from_db()
        assert pg.is_active is False  # deactivated, not deleted

    def test_owner_cannot_delete_other_owners_pg(self, client):
        owner_a = _owner()
        pg = PGFactory()  # different owner
        _login(client, owner_a)
        resp = client.post(reverse("properties:pg_delete", kwargs={"pg_pk": pg.pk}))
        assert resp.status_code == 403


# ===========================================================================
# Room Create
# ===========================================================================


class TestRoomCreateView:
    def test_create_room(self, client):
        owner = _owner()
        pg = PGFactory(owner=owner)
        _login(client, owner)
        url = reverse("properties:room_create", kwargs={"pg_pk": pg.pk})
        data = {
            "room_number": "101",
            "room_type": "Double",
            "capacity": "2",
            "rent": "3000.00",
            "description": "",
        }
        resp = client.post(url, data)
        assert resp.status_code == 302
        assert Room.objects.filter(pg=pg, room_number="101").exists()

    def test_cannot_create_room_in_other_owners_pg(self, client):
        owner_a = _owner()
        pg = PGFactory()  # different owner
        _login(client, owner_a)
        resp = client.post(
            reverse("properties:room_create", kwargs={"pg_pk": pg.pk}),
            {"room_number": "101", "room_type": "Single", "capacity": "1", "rent": "2000", "description": ""},
        )
        assert resp.status_code == 403


# ===========================================================================
# Room Update
# ===========================================================================


class TestRoomUpdateView:
    def test_owner_updates_room(self, client):
        owner = _owner()
        pg = PGFactory(owner=owner)
        room = RoomFactory(pg=pg, room_type="Single")
        _login(client, owner)
        url = reverse("properties:room_edit", kwargs={"pg_pk": pg.pk, "room_pk": room.pk})
        data = {
            "room_number": room.room_number,
            "room_type": "Double",
            "capacity": str(room.capacity),
            "rent": str(room.rent),
            "description": "",
        }
        resp = client.post(url, data)
        assert resp.status_code == 302
        room.refresh_from_db()
        assert room.room_type == "Double"


# ===========================================================================
# Room Delete
# ===========================================================================


class TestRoomDeleteView:
    def test_hard_delete_room_without_bookings(self, client):
        owner = _owner()
        pg = PGFactory(owner=owner)
        room = RoomFactory(pg=pg)
        _login(client, owner)
        url = reverse("properties:room_delete", kwargs={"pg_pk": pg.pk, "room_pk": room.pk})
        resp = client.post(url)
        assert resp.status_code == 302
        assert not Room.objects.filter(pk=room.pk).exists()

    def test_soft_delete_room_with_bookings(self, client):
        from stayease.bookings.models import Booking

        owner = _owner()
        pg = PGFactory(owner=owner)
        room = RoomFactory(pg=pg)
        bed = BedFactory(room=room)
        tenant = _tenant()
        Booking.objects.create(tenant=tenant, bed=bed)

        _login(client, owner)
        url = reverse("properties:room_delete", kwargs={"pg_pk": pg.pk, "room_pk": room.pk})
        resp = client.post(url)
        assert resp.status_code == 302
        room.refresh_from_db()
        assert room.is_active is False


# ===========================================================================
# Bed Create
# ===========================================================================


class TestBedCreateView:
    def test_create_bed(self, client):
        owner = _owner()
        pg = PGFactory(owner=owner)
        room = RoomFactory(pg=pg, capacity=3)
        _login(client, owner)
        url = reverse("properties:bed_create", kwargs={"pg_pk": pg.pk, "room_pk": room.pk})
        data = {"label": "Bed A", "is_available": True}
        resp = client.post(url, data)
        assert resp.status_code == 302
        assert Bed.objects.filter(room=room, label="Bed A").exists()

    def test_cannot_exceed_capacity(self, client):
        owner = _owner()
        pg = PGFactory(owner=owner)
        room = RoomFactory(pg=pg, capacity=1)
        BedFactory(room=room, label="Bed A")
        _login(client, owner)
        url = reverse("properties:bed_create", kwargs={"pg_pk": pg.pk, "room_pk": room.pk})
        data = {"label": "Bed B", "is_available": True}
        resp = client.post(url, data)
        assert resp.status_code == 200  # re-renders form with error
        assert not Bed.objects.filter(room=room, label="Bed B").exists()


# ===========================================================================
# Bed Update
# ===========================================================================


class TestBedUpdateView:
    def test_owner_updates_bed(self, client):
        owner = _owner()
        pg = PGFactory(owner=owner)
        room = RoomFactory(pg=pg, capacity=2)
        bed = BedFactory(room=room, label="Bed A", is_available=True)
        _login(client, owner)
        url = reverse("properties:bed_edit", kwargs={
            "pg_pk": pg.pk, "room_pk": room.pk, "bed_pk": bed.pk,
        })
        data = {"label": "Bed A", "is_available": False}
        resp = client.post(url, data)
        assert resp.status_code == 302
        bed.refresh_from_db()
        assert bed.is_available is False


# ===========================================================================
# Bed Delete
# ===========================================================================


class TestBedDeleteView:
    def test_hard_delete_bed_without_bookings(self, client):
        owner = _owner()
        pg = PGFactory(owner=owner)
        room = RoomFactory(pg=pg)
        bed = BedFactory(room=room)
        _login(client, owner)
        url = reverse("properties:bed_delete", kwargs={
            "pg_pk": pg.pk, "room_pk": room.pk, "bed_pk": bed.pk,
        })
        resp = client.post(url)
        assert resp.status_code == 302
        assert not Bed.objects.filter(pk=bed.pk).exists()

    def test_soft_delete_bed_with_bookings(self, client):
        from stayease.bookings.models import Booking

        owner = _owner()
        pg = PGFactory(owner=owner)
        room = RoomFactory(pg=pg)
        bed = BedFactory(room=room)
        tenant = _tenant()
        Booking.objects.create(tenant=tenant, bed=bed)

        _login(client, owner)
        url = reverse("properties:bed_delete", kwargs={
            "pg_pk": pg.pk, "room_pk": room.pk, "bed_pk": bed.pk,
        })
        resp = client.post(url)
        assert resp.status_code == 302
        bed.refresh_from_db()
        assert bed.is_active is False

    def test_owner_cannot_delete_other_owners_bed(self, client):
        owner_a = _owner()
        pg = PGFactory()  # different owner
        room = RoomFactory(pg=pg)
        bed = BedFactory(room=room)
        _login(client, owner_a)
        url = reverse("properties:bed_delete", kwargs={
            "pg_pk": pg.pk, "room_pk": room.pk, "bed_pk": bed.pk,
        })
        resp = client.post(url)
        assert resp.status_code == 403
