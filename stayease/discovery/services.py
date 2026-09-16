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
from django.db.models import Min
from django.db.models import Q

from stayease.bookings.models import ACTIVE_BOOKING_STATUSES
from stayease.properties.models import PG

if TYPE_CHECKING:
    from django.db.models import QuerySet


def get_active_pgs_queryset() -> QuerySet[PG]:
    """
    Return the base queryset for tenant-visible PGs.

    Only active PGs are shown. The queryset is annotated with:
    - ``available_bed_count`` — count of active, available beds with no active booking
    - ``starting_rent_annotated`` — minimum rent among currently available beds
    - ``min_bed_rent`` — fallback minimum rent among all active beds in this PG
    """

    return (
        PG.objects.filter(is_active=True)  # type: ignore[attr-defined]
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
            starting_rent_annotated=Min(
                "rooms__beds__rent_per_month",
                filter=Q(
                    rooms__beds__is_active=True,
                    rooms__beds__is_available=True,
                    rooms__is_active=True,
                )
                & ~Q(
                    rooms__beds__bookings__status__in=ACTIVE_BOOKING_STATUSES,
                ),
            ),
            min_bed_rent=Min(
                "rooms__beds__rent_per_month",
                filter=Q(
                    rooms__beds__is_active=True,
                    rooms__is_active=True,
                ),
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
    * ``min_price`` / ``max_price`` — bed-level starting rent range filter.
    * ``available_only`` — if truthy, exclude PGs with zero available beds.

    All filtering is pushed to the database.
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

    # -- Price range (evaluated on starting available bed rent, with fallbacks) ---
    min_price = _to_decimal(params.get("min_price"))
    if min_price is not None:
        qs = qs.filter(
            Q(starting_rent_annotated__gte=min_price)
            | Q(starting_rent_annotated__isnull=True, min_bed_rent__gte=min_price)
            | Q(starting_rent_annotated__isnull=True, min_bed_rent__isnull=True, rent_per_month__gte=min_price)
        )

    max_price = _to_decimal(params.get("max_price"))
    if max_price is not None:
        qs = qs.filter(
            Q(starting_rent_annotated__lte=max_price)
            | Q(starting_rent_annotated__isnull=True, min_bed_rent__lte=max_price)
            | Q(starting_rent_annotated__isnull=True, min_bed_rent__isnull=True, rent_per_month__lte=max_price)
        )

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
            PG.objects.filter(pk=pg_pk, is_active=True)  # type: ignore[attr-defined]
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
    Build a list of room dicts with bed availability and pricing info for a PG.

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
            "starting_rent": Decimal | None,
        }
    """
    rooms_data = []
    # Use python filtering/sorting on .all() to leverage prefetched relation cache
    # and completely avoid N+1 queries.
    active_rooms = sorted(
        [r for r in pg.rooms.all() if r.is_active],  # type: ignore[attr-defined]
        key=lambda r: r.room_number,
    )
    for room in active_rooms:
        beds_info = []
        available = 0
        total_active = 0
        active_beds = sorted(
            [b for b in room.beds.all() if b.is_active],  # type: ignore[attr-defined]
            key=lambda b: b.label,
        )
        for bed in active_beds:
            total_active += 1
            has_active_booking = any(
                booking.status in ACTIVE_BOOKING_STATUSES
                for booking in bed.bookings.all()  # type: ignore[attr-defined]
            )
            bookable = bed.is_available and not has_active_booking
            if bookable:
                available += 1
            beds_info.append({
                "bed": bed,
                "is_bookable": bookable,
                "is_occupied": has_active_booking,
            })

        bookable_rents = [
            b.rent_per_month
            for b in active_beds
            if b.is_available and not any(
                booking.status in ACTIVE_BOOKING_STATUSES
                for booking in b.bookings.all()  # type: ignore[attr-defined]
            )
        ]
        active_rents = [b.rent_per_month for b in active_beds]
        room_starting_rent = (
            min(bookable_rents)
            if bookable_rents
            else (min(active_rents) if active_rents else room.rent)
        )

        rooms_data.append({
            "room": room,
            "beds": beds_info,
            "available_count": available,
            "total_active_count": total_active,
            "starting_rent": room_starting_rent,
        })
    return rooms_data


def get_distinct_cities() -> list[str]:
    """Return a sorted list of distinct cities from active PGs."""
    return list(
        PG.objects.filter(is_active=True)  # type: ignore[attr-defined]
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
