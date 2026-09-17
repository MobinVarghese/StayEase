"""
Property inventory service layer.

Business-logic helpers for PG/Room/Bed management.
These are used by forms and views to enforce domain rules
without duplicating logic.
"""

from __future__ import annotations

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
