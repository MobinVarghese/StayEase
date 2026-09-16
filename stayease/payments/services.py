"""
Payment service layer.

All payment operations go through this module. Views and other
consumers call these functions rather than manipulating the Payment
model directly.

This is a **dummy** payment system for the academic project.
No real payment credentials are collected or stored.

Business logic ownership: Member 5

Integration with Member 4:
    - ``mark_payment_pending(booking)`` — transitions APPROVED → PAYMENT_PENDING
    - ``confirm_booking(booking)`` — transitions PAYMENT_PENDING → CONFIRMED
    These are imported from ``stayease.bookings.services``.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from django.core.exceptions import PermissionDenied
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils.translation import gettext_lazy as _

from stayease.bookings.models import BookingStatus
from stayease.bookings.services import confirm_booking
from stayease.bookings.services import mark_payment_pending
from stayease.notifications.services import notify_payment_successful
from stayease.payments.models import Payment
from stayease.payments.models import PaymentStatus

if TYPE_CHECKING:
    from stayease.bookings.models import Booking
    from stayease.users.models import User


def _generate_transaction_ref() -> str:
    """Generate a dummy transaction reference."""
    return f"TXN-{uuid.uuid4().hex[:12].upper()}"


# ======================================================================
# Payment initiation
# ======================================================================


def initiate_payment(*, booking: Booking, user: User) -> Payment:
    """
    Initiate a dummy payment for an approved booking.

    This function:
    1. Validates the user is the booking's tenant.
    2. Validates the booking is in APPROVED state.
    3. Transitions the booking to PAYMENT_PENDING (via Member 4's service).
    4. Creates a Payment record in PENDING state.

    Raises
    ------
    PermissionDenied
        User is not the booking's tenant.
    ValidationError
        - Booking is not in APPROVED state.
        - A payment already exists for this booking.

    Returns
    -------
    Payment
        The newly created payment in PENDING state.
    """
    # ------------------------------------------------------------------
    # 1. Verify ownership — only the booking's tenant can pay
    # ------------------------------------------------------------------
    if booking.tenant != user:
        raise PermissionDenied(
            _("You do not have permission to pay for this booking.")
        )

    # ------------------------------------------------------------------
    # 2. Check for duplicate payment
    # ------------------------------------------------------------------
    if hasattr(booking, "payment"):
        raise ValidationError(
            _("A payment already exists for this booking."),
            code="duplicate_payment",
        )

    # ------------------------------------------------------------------
    # 3. Validate booking state and transition to PAYMENT_PENDING
    # ------------------------------------------------------------------
    if booking.status != BookingStatus.APPROVED:
        raise ValidationError(
            _("Payment can only be initiated for approved bookings."),
            code="invalid_booking_state",
        )

    with transaction.atomic():
        # Use Member 4's service to transition the state
        mark_payment_pending(booking)

        # ------------------------------------------------------------------
        # 4. Create the payment record
        # ------------------------------------------------------------------
        payment = Payment.objects.create(
            booking=booking,
            amount=booking.bed.rent_per_month,
            status=PaymentStatus.PENDING,
            transaction_ref=_generate_transaction_ref(),
        )

    return payment


# ======================================================================
# Payment processing
# ======================================================================


def process_dummy_payment(
    *,
    payment: Payment,
    user: User,
    simulate_success: bool = True,
) -> Payment:
    """
    Process a dummy payment.

    Parameters
    ----------
    payment
        The payment to process (must be in PENDING state).
    user
        The authenticated user — must be the booking's tenant.
    simulate_success
        If True, the payment succeeds. If False, it fails.

    Raises
    ------
    PermissionDenied
        User is not the booking's tenant.
    ValidationError
        Payment is not in PENDING state.

    Returns
    -------
    Payment
        The updated payment with SUCCESS or FAILED status.
    """
    # ------------------------------------------------------------------
    # 1. Verify ownership
    # ------------------------------------------------------------------
    if payment.booking.tenant != user:
        raise PermissionDenied(
            _("You do not have permission to process this payment.")
        )

    # ------------------------------------------------------------------
    # 2. Validate payment state
    # ------------------------------------------------------------------
    if payment.status != PaymentStatus.PENDING:
        raise ValidationError(
            _("This payment has already been processed."),
            code="payment_already_processed",
        )

    # ------------------------------------------------------------------
    # 3. Process the dummy payment
    # ------------------------------------------------------------------
    with transaction.atomic():
        if simulate_success:
            payment.status = PaymentStatus.SUCCESS
            payment.save(update_fields=["status", "updated_at"])

            # Use Member 4's service to confirm the booking
            confirm_booking(payment.booking)

            # Member 5: trigger confirmation notification
            notify_payment_successful(payment.booking)
        else:
            payment.status = PaymentStatus.FAILED
            payment.save(update_fields=["status", "updated_at"])

    return payment
