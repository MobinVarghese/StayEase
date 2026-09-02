"""
Test factories for the payments app.
"""

from __future__ import annotations

from decimal import Decimal

import factory
from factory.django import DjangoModelFactory

from stayease.bookings.models import BookingStatus
from stayease.bookings.tests.factories import BookingFactory
from stayease.payments.models import Payment
from stayease.payments.models import PaymentStatus


class PaymentFactory(DjangoModelFactory):
    booking = factory.SubFactory(BookingFactory, status=BookingStatus.PAYMENT_PENDING)
    amount = factory.LazyFunction(lambda: Decimal("3000.00"))
    status = PaymentStatus.PENDING
    transaction_ref = factory.Sequence(lambda n: f"TXN-TEST{n:08d}")

    class Meta:
        model = Payment
