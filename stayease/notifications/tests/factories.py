"""
Test factories for the notifications app.
"""

from __future__ import annotations

import factory
from factory.django import DjangoModelFactory

from stayease.bookings.tests.factories import BookingFactory
from stayease.notifications.models import Notification
from stayease.users.tests.factories import UserFactory


class NotificationFactory(DjangoModelFactory):
    recipient = factory.SubFactory(UserFactory)
    booking = factory.SubFactory(BookingFactory)
    message = factory.Faker("sentence")
    is_read = False

    class Meta:
        model = Notification
