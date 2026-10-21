"""
Property inventory service layer.

Business-logic helpers for PG/Room/Bed management.
These are used by forms and views to enforce domain rules
without duplicating logic.
"""

from __future__ import annotations

from typing import Any
from typing import TYPE_CHECKING

from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

if TYPE_CHECKING:
    from stayease.properties.models import Bed
    from stayease.properties.models import PG
    from stayease.properties.models import Room


def check_pg_ownership(pg: PG, user) -> None:
    """
    Raise PermissionDenied if *user* does not own *pg*.

    This is a service-level check for use outside class-based views
    (e.g. in form validation or function-based helpers).
    """
    from django.core.exceptions import PermissionDenied

    if pg.owner != user:
        raise PermissionDenied(_("You do not have permission to manage this property."))


def check_room_belongs_to_pg(room: Room, pg: PG) -> None:
    """Raise ValidationError if *room* does not belong to *pg*."""
    if room.pg_id != pg.pk:
        raise ValidationError(
            _("This room does not belong to the specified PG."),
        )


def check_bed_belongs_to_room(bed: Bed, room: Room) -> None:
    """Raise ValidationError if *bed* does not belong to *room*."""
    if bed.room_id != room.pk:
        raise ValidationError(
            _("This bed does not belong to the specified room."),
        )


def validate_bed_capacity(room: Room, *, exclude_bed_pk: int | None = None) -> None:
    """
    Raise ValidationError if the room already has as many active beds
    as its stated capacity.

    The capacity represents the physical limit of beds the room can hold.
    If the owner wants to add more beds, they must increase the room's
    capacity first.

    Parameters
    ----------
    room:
        The room to check.
    exclude_bed_pk:
        If updating an existing bed, pass its PK so it is not
        counted against the limit.
    """
    qs = room.beds.filter(is_active=True)
    if exclude_bed_pk is not None:
        qs = qs.exclude(pk=exclude_bed_pk)

    current_count = qs.count()

    # Enforce specific constraints based on room type
    if room.room_type:
        normalized_type = room.room_type.strip().lower()
        if normalized_type == "single" and current_count >= 1:
            raise ValidationError(
                _(
                    "A single room can only have 1 bed. This room already has "
                    "%(count)d active bed(s).",
                ),
                params={"count": current_count},
            )
        if normalized_type == "double" and current_count >= 2:
            raise ValidationError(
                _(
                    "A double room can only have 2 beds. This room already has "
                    "%(count)d active bed(s).",
                ),
                params={"count": current_count},
            )

    if current_count >= room.capacity:
        raise ValidationError(
            _(
                "This room already has %(count)d active bed(s), which is "
                "the maximum capacity (%(capacity)d). Update the room's "
                "capacity first if you need to add another bed.",
            ),
            params={"count": current_count, "capacity": room.capacity},
        )


def can_hard_delete_pg(pg: PG) -> bool:
    """
    Return True if the PG can be permanently deleted (no bookings exist).

    Business rule: a PG with any booking history (on any of its beds)
    must be deactivated rather than deleted, to preserve data integrity.
    """
    from stayease.bookings.models import Booking

    return not Booking.objects.filter(bed__room__pg=pg).exists()


def can_hard_delete_room(room: Room) -> bool:
    """Return True if no bookings reference any bed in this room."""
    from stayease.bookings.models import Booking

    return not Booking.objects.filter(bed__room=room).exists()


def can_hard_delete_bed(bed: Bed) -> bool:
    """Return True if no bookings reference this bed."""
    from stayease.bookings.models import Booking

    return not Booking.objects.filter(bed=bed).exists()


def create_review(
    *,
    booking: Any,
    tenant: Any,
    rating: int,
    comment: str,
) -> Any:
    """
    Create a verified review for a completed booking.

    Raises
    ------
    PermissionDenied
        If tenant is not the booking's tenant or not a TENANT role.
    ValidationError
        If booking is not COMPLETED, if a review already exists for this booking,
        or if rating is outside 1–5.
    """
    from django.core.exceptions import PermissionDenied
    from stayease.bookings.models import BookingStatus
    from stayease.properties.models import Review
    from stayease.users.models import UserRole

    if getattr(tenant, "role", None) != UserRole.TENANT:
        raise PermissionDenied(_("Only tenants can submit reviews."))

    if booking.tenant != tenant:
        raise PermissionDenied(_("You can only review your own bookings."))

    if booking.status != BookingStatus.COMPLETED:
        raise ValidationError(
            _("You can only review accommodations after completing your stay (checked out)."),
            code="stay_not_completed",
        )

    if hasattr(booking, "review") or Review.objects.filter(booking=booking).exists():
        raise ValidationError(
            _("You have already submitted a review for this stay."),
            code="duplicate_review",
        )

    if not (1 <= rating <= 5):
        raise ValidationError(
            _("Rating must be between 1 and 5 stars."),
            code="invalid_rating",
        )

    clean_comment = comment.strip()
    if not clean_comment:
        raise ValidationError(
            _("Please provide written feedback for your review."),
            code="empty_comment",
        )

    review = Review(
        booking=booking,
        room=booking.bed.room,
        tenant=tenant,
        rating=rating,
        comment=clean_comment,
    )
    review.full_clean()
    review.save()
    return review


def get_homepage_reviews(limit: int = 6):
    """
    Return recent, verified reviews for display on the homepage.
    Optimised with select_related to avoid N+1 queries.
    """
    from stayease.bookings.models import BookingStatus
    from stayease.properties.models import Review

    return (
        Review.objects.filter(booking__status=BookingStatus.COMPLETED)
        .select_related("tenant", "room__pg", "booking")
        .order_by("-created_at")[:limit]
    )

