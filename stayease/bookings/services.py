"""
Booking service layer — core business logic.

All booking operations go through this module. Views and other consumers
call these functions rather than manipulating the Booking model directly.

Concurrency strategy:
    1. Database-level: ``unique_active_booking_per_bed`` partial unique
       constraint prevents two active bookings for the same bed.
    2. Application-level: ``select_for_update()`` on the Bed row inside
       ``transaction.atomic()`` serialises concurrent booking attempts
       so the constraint is never hit under normal flow.
    3. Duplicate-request guard: a tenant cannot create a second active
       booking for a bed they already have an active booking on.

Member 5 integration:
    Member 5 (notifications / payment) should call:
    - ``mark_payment_pending(booking)`` after approval acknowledgement.
    - ``confirm_booking(booking)`` after successful dummy payment.
    These are the stable integration points.
"""

from __future__ import annotations

from typing import Any
from typing import TYPE_CHECKING

from django.core.exceptions import PermissionDenied
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from stayease.bookings.models import ACTIVE_BOOKING_STATUSES
from stayease.bookings.models import BOOKING_TRANSITIONS
from stayease.bookings.models import Booking
from stayease.bookings.models import BookingStatus

if TYPE_CHECKING:
    from stayease.properties.models import Bed
    from stayease.users.models import User


# ======================================================================
# State machine helpers
# ======================================================================


def get_valid_transitions(status: str) -> set[str]:
    """Return the set of statuses reachable from *status*."""
    return BOOKING_TRANSITIONS.get(status, set())


def validate_state_transition(current: str, target: str) -> None:
    """
    Raise ``ValidationError`` if *current* → *target* is not a legal
    transition in the booking state machine.
    """
    allowed = get_valid_transitions(current)
    if target not in allowed:
        raise ValidationError(
            _(
                "Invalid booking state transition: %(current)s → %(target)s. "
                "Allowed transitions: %(allowed)s."
            ),
            params={
                "current": current,
                "target": target,
                "allowed": ", ".join(sorted(allowed)) or "none",
            },
            code="invalid_transition",
        )


# ======================================================================
# Booking creation
# ======================================================================


def create_booking_request(*, tenant: User, bed: Bed) -> Booking:
    """
    Create a new PENDING booking request for *tenant* on *bed*.

    Concurrency-safe: acquires a row-level lock on the Bed before
    checking availability, inside an atomic transaction.

    Raises
    ------
    ValidationError
        - Bed is inactive or unavailable.
        - Tenant already has an active booking for this bed.
        - Another active booking exists for this bed (race condition).
    PermissionDenied
        - User is not a tenant.

    Returns
    -------
    Booking
        The newly created booking in PENDING state.
    """
    from stayease.users.models import UserRole

    # ------------------------------------------------------------------
    # 1. Role check
    # ------------------------------------------------------------------
    if getattr(tenant, "role", None) != UserRole.TENANT:
        raise PermissionDenied(_("Only tenants can create booking requests."))

    # ------------------------------------------------------------------
    # 2. Atomic transaction with row lock on the bed
    # ------------------------------------------------------------------
    with transaction.atomic():
        # Lock the bed row to serialise concurrent booking attempts.
        locked_bed = (
            type(bed)
            .objects.select_for_update()
            .select_related("room", "room__pg")
            .get(pk=bed.pk)
        )

        # ----------------------------------------------------------
        # 3. Validate bed state
        # ----------------------------------------------------------
        if not locked_bed.is_active:
            raise ValidationError(
                _("This bed is not currently active."),
                code="bed_inactive",
            )
        if not locked_bed.is_available:
            raise ValidationError(
                _("This bed is not available for booking."),
                code="bed_unavailable",
            )

        # ----------------------------------------------------------
        # 4. Duplicate-request guard (same tenant, same bed)
        # ----------------------------------------------------------
        if Booking.objects.filter(
            tenant=tenant,
            bed=locked_bed,
            status__in=ACTIVE_BOOKING_STATUSES,
        ).exists():
            raise ValidationError(
                _("You already have an active booking for this bed."),
                code="duplicate_booking",
            )

        # ----------------------------------------------------------
        # 5. Check no other active booking exists for this bed
        # ----------------------------------------------------------
        if Booking.objects.filter(
            bed=locked_bed,
            status__in=ACTIVE_BOOKING_STATUSES,
        ).exists():
            raise ValidationError(
                _(
                    "This bed already has an active booking and is no "
                    "longer available."
                ),
                code="bed_already_booked",
            )

        # ----------------------------------------------------------
        # 6. Create the booking
        # ----------------------------------------------------------
        try:
            booking = Booking.objects.create(
                tenant=tenant,
                bed=locked_bed,
                status=BookingStatus.PENDING,
            )
        except IntegrityError:
            # The DB constraint fires if a concurrent transaction
            # slipped through between our check and the INSERT.
            raise ValidationError(
                _("This bed was booked by another user. Please try again."),
                code="concurrent_conflict",
            )

    return booking


# ======================================================================
# Owner approval / rejection
# ======================================================================


def _verify_booking_owner(booking: Booking, owner: User) -> None:
    """
    Raise ``PermissionDenied`` if *owner* does not own the PG
    associated with the booking's bed.
    """
    pg = booking.bed.room.pg
    if pg.owner_id != owner.pk:
        raise PermissionDenied(
            _("You do not have permission to manage this booking.")
        )


def approve_booking(*, booking: Booking, owner: User) -> Booking:
    """
    Approve a PENDING booking request.

    Only the owner of the PG that contains the bed may approve.

    Raises
    ------
    PermissionDenied
        Owner mismatch.
    ValidationError
        Invalid state transition (booking is not PENDING).
    """
    from stayease.users.models import UserRole

    if getattr(owner, "role", None) != UserRole.OWNER:
        raise PermissionDenied(_("Only owners can approve bookings."))

    _verify_booking_owner(booking, owner)
    validate_state_transition(booking.status, "APPROVED")

    booking.status = "APPROVED"
    booking.approved_at = timezone.now()
    booking.save(update_fields=["status", "approved_at", "updated_at"])
    return booking


def reject_booking(*, booking: Booking, owner: User) -> Booking:
    """
    Reject a PENDING booking request.

    Only the owner of the PG that contains the bed may reject.

    Raises
    ------
    PermissionDenied
        Owner mismatch.
    ValidationError
        Invalid state transition (booking is not PENDING).
    """
    from stayease.users.models import UserRole

    if getattr(owner, "role", None) != UserRole.OWNER:
        raise PermissionDenied(_("Only owners can reject bookings."))

    _verify_booking_owner(booking, owner)
    validate_state_transition(booking.status, "REJECTED")

    booking.status = "REJECTED"
    booking.rejected_at = timezone.now()
    booking.save(update_fields=["status", "rejected_at", "updated_at"])
    return booking


# ======================================================================
# Payment flow (consumed by Member 5)
# ======================================================================


def mark_payment_pending(booking: Booking) -> Booking:
    """
    Transition an APPROVED booking to PAYMENT_PENDING.

    Called after the tenant acknowledges approval and is ready to pay.
    Member 5 should call this function as part of the payment flow.

    Raises
    ------
    ValidationError
        Invalid state transition.
    """
    validate_state_transition(booking.status, "PAYMENT_PENDING")

    booking.status = "PAYMENT_PENDING"
    booking.save(update_fields=["status", "updated_at"])
    return booking


def confirm_booking(booking: Booking) -> Booking:
    """
    Transition a PAYMENT_PENDING booking to CONFIRMED.

    Called after the dummy payment succeeds.
    Member 5 should call this function to finalise the booking.

    Raises
    ------
    ValidationError
        Invalid state transition.
    """
    validate_state_transition(booking.status, "CONFIRMED")

    booking.status = "CONFIRMED"
    booking.confirmed_at = timezone.now()
    booking.save(update_fields=["status", "confirmed_at", "updated_at"])
    return booking


# ======================================================================
# Query helpers
# ======================================================================


def get_tenant_bookings(tenant: User):
    """
    Return the queryset of bookings belonging to *tenant*,
    with related bed/room/pg pre-fetched for display.
    """
    return (
        Booking.objects.filter(tenant=tenant)
        .select_related("bed__room__pg")
        .order_by("-created_at")
    )


def get_owner_bookings(owner: User):
    """
    Return the queryset of bookings for all PGs owned by *owner*,
    with related tenant/bed/room/pg pre-fetched for display.
    """
    return (
        Booking.objects.filter(bed__room__pg__owner=owner)
        .select_related("tenant", "bed__room__pg")
        .order_by("-created_at")
    )


# ======================================================================
# Contact visibility authorization & extraction
# ======================================================================


def can_view_booking_contact(booking: Booking, user: Any) -> bool:
    """
    Determine whether *user* is authorized to view contact information for *booking*.

    Contact details (phone numbers) are visible ONLY when:
    1. The booking status is CONFIRMED.
    2. The user is authenticated.
    3. The user is either the tenant who made the booking OR the owner
       of the property containing the booked bed.

    Returns False for all other states (PENDING, APPROVED, PAYMENT_PENDING,
    REJECTED, CANCELLED) and unauthorized users.
    """
    if not user or not getattr(user, "is_authenticated", False):
        return False

    if not booking or getattr(booking, "status", None) != BookingStatus.CONFIRMED:
        return False

    is_tenant = booking.tenant == user
    try:
        is_owner = booking.bed.room.pg.owner == user
    except AttributeError:
        is_owner = False

    return is_tenant or is_owner


def get_booking_contact_info(booking: Booking, user: Any) -> dict | None:
    """
    Return contact details of the counterpart for *booking* if *user* is
    authorized, otherwise None.

    If *user* is the tenant -> returns the PG owner's contact information.
    If *user* is the PG owner -> returns the tenant's contact information.
    """
    if not can_view_booking_contact(booking, user):
        return None

    if booking.tenant == user:
        counterpart = booking.bed.room.pg.owner
        role_label = _("Owner")
    else:
        counterpart = booking.tenant
        role_label = _("Tenant")

    name = getattr(counterpart, "name", "")
    if not name:
        name = getattr(counterpart, "email", "")

    phone_number = getattr(counterpart, "phone_number", "") or ""

    return {
        "counterpart": counterpart,
        "role_label": role_label,
        "name": name,
        "phone_number": phone_number,
        "email": getattr(counterpart, "email", ""),
    }

