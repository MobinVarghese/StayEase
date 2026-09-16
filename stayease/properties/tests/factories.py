"""
Test factories for the properties app.

Used by test suites across the project (Member 3/4 can also import these).
"""

from __future__ import annotations

from decimal import Decimal

import factory
from factory.django import DjangoModelFactory

from stayease.properties.models import Bed
from stayease.properties.models import PG
from stayease.properties.models import Room
from stayease.users.models import UserRole
from stayease.users.tests.factories import UserFactory


class PGFactory(DjangoModelFactory):
    owner = factory.SubFactory(UserFactory, role=UserRole.OWNER)
    name = factory.Sequence(lambda n: f"Test PG {n}")
    description = factory.Faker("paragraph")
    address = factory.Faker("address")
    city = factory.Faker("city")
    rent_per_month = factory.LazyFunction(lambda: Decimal("5000.00"))
    amenities = "Wi-Fi, Laundry"
    is_active = True

    class Meta:
        model = PG


class RoomFactory(DjangoModelFactory):
    pg = factory.SubFactory(PGFactory)
    room_number = factory.Sequence(lambda n: f"{100 + n}")
    room_type = "Double"
    capacity = 2
    rent = factory.LazyFunction(lambda: Decimal("3000.00"))
    description = ""
    is_active = True

    class Meta:
        model = Room


class BedFactory(DjangoModelFactory):
    room = factory.SubFactory(RoomFactory)
    label = factory.Sequence(lambda n: f"Bed {chr(65 + n % 26)}{n // 26 or ''}")
    rent_per_month = factory.LazyFunction(lambda: Decimal("3000.00"))
    is_available = True
    is_active = True

    class Meta:
        model = Bed
