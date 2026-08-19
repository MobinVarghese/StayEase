"""
Discovery service layer.

Provides database-level search, filtering, and availability logic for
tenant-facing PG discovery.  All filtering happens at the database level
to avoid loading large datasets into Python.

Business logic ownership: Member 3
Model ownership: Member 2 (PG/Room/Bed), Member 4 (Booking)
"""

from __future__ import annotations

from decimal import Decimal
from decimal import InvalidOperation
from typing import TYPE_CHECKING
from typing import Any

from django.db.models import Count
from django.db.models import Q

from stayease.bookings.models import ACTIVE_BOOKING_STATUSES
from stayease.properties.models import PG

if TYPE_CHECKING:
    from django.db.models import QuerySet


def get_active_pgs_queryset() -> QuerySet[PG]:
    """
    Return the base queryset for tenant-visible PGs.

    Only active PGs are shown.  The queryset is annotated with
    ``available_bed_count`` — the number of beds that are both
    inventory-available (``is_available=True``, ``is_active=True``),
    in an active room, AND do not have an active booking.

    This lets templates display an availability summary without
    additional queries.
    """

    return (
        PG.objects.filter(is_active=True)
        .annotate(
            available_bed_count=Count(
                "rooms__beds",
                filter=Q(
                    rooms__beds__is_active=True,
                    rooms__beds__is_available=True,
                    rooms__is_active=True,
                )
                & ~Q(
                    rooms__beds__bookings__status__in=ACTIVE_BOOKING_STATUSES,
                ),
                distinct=True,
            ),
        )
        .order_by("-created_at")
    )


def search_pgs(params: dict[str, Any]) -> QuerySet[PG]:
    """
    Apply search/filter criteria from query parameters to the PG queryset.

    Supported filters:

    * ``q`` — keyword search across PG name, description, city, amenities.
    * ``city`` — exact city match (case-insensitive).
    * ``min_price`` / ``max_price`` — ``rent_per_month`` range filter.
    * ``available_only`` — if truthy, exclude PGs with zero available beds.

    All filtering is pushed to the database.

    Parameters
    ----------
    params:
        Typically ``request.GET`` or a cleaned-form dict.

    Returns
    -------
    QuerySet[PG]
        Filtered, annotated queryset ready for pagination.
    """
    qs = get_active_pgs_queryset()

    # -- Keyword search ------------------------------------------------
    keyword = params.get("q", "").strip()
    if keyword:
        qs = qs.filter(
            Q(name__icontains=keyword)
            | Q(description__icontains=keyword)
            | Q(city__icontains=keyword)
            | Q(amenities__icontains=keyword),
        )

    # -- City filter ---------------------------------------------------
    city = params.get("city", "").strip()
    if city:
        qs = qs.filter(city__iexact=city)

    # -- Price range ---------------------------------------------------
    min_price = _to_decimal(params.get("min_price"))
    if min_price is not None:
        qs = qs.filter(rent_per_month__gte=min_price)

    max_price = _to_decimal(params.get("max_price"))
    if max_price is not None:
        qs = qs.filter(rent_per_month__lte=max_price)

    # -- Availability --------------------------------------------------
    if params.get("available_only"):
        qs = qs.filter(available_bed_count__gt=0)

    return qs


def get_pg_detail(pg_pk: int) -> PG | None:
    """
    Return a single active PG with rooms and beds prefetched,
    or ``None`` if it does not exist / is inactive.
    """
    try:
        return (
            PG.objects.filter(pk=pg_pk, is_active=True)
            .prefetch_related(
                "rooms__beds",
                "rooms__beds__bookings",
            )
            .first()
        )
    except (ValueError, TypeError):
        return None


def get_rooms_with_availability(pg: PG) -> list[dict]:
    """
    Build a list of room dicts with bed availability info for a PG.

    Each dict contains::

        {
            "room": Room instance,
            "beds": [
                {
                    "bed": Bed instance,
                    "is_bookable": bool,
                },
                ...
            ],
            "available_count": int,
            "total_active_count": int,
        }

    ``is_bookable`` means the bed is active, inventory-available, and
    has no active booking.  This is a **display** hint only — Member 4's
    booking service performs the authoritative availability check.
    """
    rooms_data = []
    for room in pg.rooms.filter(is_active=True).order_by("room_number"):
        beds_info = []
        available = 0
        total_active = 0
        for bed in room.beds.filter(is_active=True).order_by("label"):
            total_active += 1
            has_active_booking = any(
                b.status in ACTIVE_BOOKING_STATUSES
                for b in bed.bookings.all()
            )
            bookable = bed.is_available and not has_active_booking
            if bookable:
                available += 1
            beds_info.append({
                "bed": bed,
                "is_bookable": bookable,
            })
        rooms_data.append({
            "room": room,
            "beds": beds_info,
            "available_count": available,
            "total_active_count": total_active,
        })
    return rooms_data


def get_distinct_cities() -> list[str]:
    """Return a sorted list of distinct cities from active PGs."""
    return list(
        PG.objects.filter(is_active=True)
        .values_list("city", flat=True)
        .distinct()
        .order_by("city"),
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _to_decimal(value: Any) -> Decimal | None:
    """Safely convert a value to Decimal, returning None on failure."""
    if not value:
        return None
    try:
        d = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None
    else:
        if d < 0:
            return None
        return d
