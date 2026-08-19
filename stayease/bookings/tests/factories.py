"""
Test factories for the bookings app.
"""

from __future__ import annotations

import factory
from factory.django import DjangoModelFactory

from stayease.bookings.models import Booking
from stayease.bookings.models import BookingStatus
from stayease.properties.tests.factories import BedFactory
from stayease.users.models import UserRole
from stayease.users.tests.factories import UserFactory


class BookingFactory(DjangoModelFactory):
    tenant = factory.SubFactory(UserFactory, role=UserRole.TENANT)
    bed = factory.SubFactory(BedFactory)
    status = BookingStatus.PENDING

    class Meta:
        model = Booking
