from decimal import Decimal
from typing import Any

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


class PG(models.Model):
    """
    A Paying Guest (PG) accommodation property listed by an owner.

    Relationship: Owner (User with role=OWNER) 1──N PG
    Business logic ownership: Member 2
    """

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="pgs",
        verbose_name=_("owner"),
        help_text=_("The owner who manages this PG property."),
    )
    name = models.CharField(_("name"), max_length=255)
    description = models.TextField(_("description"), blank=True)
    address = models.TextField(_("address"))
    city = models.CharField(_("city"), max_length=100)
    rent_per_month = models.DecimalField(
        _("rent per month"),
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text=_("Base / representative monthly rent for this PG (legacy)."),
    )
    amenities = models.TextField(
        _("amenities"),
        blank=True,
        help_text=_("Amenities offered by this PG (free-form text)."),
    )
    is_active = models.BooleanField(
        _("active"),
        default=True,
        help_text=_("Whether this PG is currently listed and visible."),
    )
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)
    updated_at = models.DateTimeField(_("updated at"), auto_now=True)

    class Meta:
        verbose_name = _("PG")
        verbose_name_plural = _("PGs")
        ordering = ["-created_at"]

    def __str__(self):
        return self.name

    @property
    def starting_rent(self) -> Decimal | None:
        """
        Minimum rent among available active beds across active rooms.
        Falls back to minimum rent among active beds, then legacy rent_per_month.
        """
        annotated = getattr(self, "starting_rent_annotated", None)
        if annotated is not None:
            return annotated

        from stayease.bookings.models import ACTIVE_BOOKING_STATUSES

        all_beds = []
        for room in self.rooms.all():
            if room.is_active:
                for bed in room.beds.all():
                    if bed.is_active:
                        all_beds.append(bed)

        # Check for bookable beds (available and no active booking)
        bookable_beds = []
        for b in all_beds:
            if not b.is_available:
                continue
            bookings_mgr = getattr(b, "bookings", None)
            has_active = False
            if bookings_mgr is not None:
                has_active = any(
                    booking.status in ACTIVE_BOOKING_STATUSES
                    for booking in bookings_mgr.all()
                )
            if not has_active:
                bookable_beds.append(b)

        if bookable_beds:
            return min(b.rent_per_month for b in bookable_beds)

        # Fallback to any inventory-available beds
        available_beds = [b for b in all_beds if b.is_available]
        if available_beds:
            return min(b.rent_per_month for b in available_beds)

        # Fallback to any active bed
        if all_beds:
            return min(b.rent_per_month for b in all_beds)

        return self.rent_per_month


class Room(models.Model):
    """
    An individual room inside a PG.

    Relationship: PG 1──N Room
    Business logic ownership: Member 2
    """

    pg = models.ForeignKey(
        PG,
        on_delete=models.CASCADE,
        related_name="rooms",
        verbose_name=_("PG"),
    )
    room_number = models.CharField(_("room number"), max_length=50)
    room_type = models.CharField(
        _("room type"),
        max_length=50,
        blank=True,
        help_text=_("e.g. Single, Double, Dormitory"),
    )
    capacity = models.PositiveIntegerField(
        _("capacity"),
        help_text=_("Maximum number of beds this room can hold."),
    )
    rent = models.DecimalField(
        _("rent"),
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text=_("Legacy / reference monthly rent for this room."),
    )
    description = models.TextField(_("description"), blank=True)
    is_active = models.BooleanField(
        _("active"),
        default=True,
        help_text=_("Whether this room is currently available for listing."),
    )
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)
    updated_at = models.DateTimeField(_("updated at"), auto_now=True)

    class Meta:
        verbose_name = _("Room")
        verbose_name_plural = _("Rooms")
        ordering = ["room_number"]
        constraints = [
            models.UniqueConstraint(
                fields=["pg", "room_number"],
                name="unique_room_number_per_pg",
            ),
        ]

    def __str__(self):
        return f"{self.pg.name} - Room {self.room_number}"

    def get_availability_stats(self) -> dict[str, Any]:
        """
        Derive room availability dynamically from its beds and their booking states.
        Uses prefetched caches when available to avoid N+1 queries.
        """
        from stayease.bookings.models import ACTIVE_BOOKING_STATUSES

        if hasattr(self, "_prefetched_objects_cache") and "beds" in self._prefetched_objects_cache:
            active_beds = [b for b in self.beds.all() if b.is_active]
            total = len(active_beds)
            occupied = 0
            available = 0
            for b in active_beds:
                if hasattr(b, "_prefetched_objects_cache") and "bookings" in b._prefetched_objects_cache:
                    has_active = any(bk.status in ACTIVE_BOOKING_STATUSES for bk in b.bookings.all())  # type: ignore[attr-defined]
                else:
                    has_active = b.bookings.filter(status__in=ACTIVE_BOOKING_STATUSES).exists()  # type: ignore[attr-defined]

                if has_active:
                    occupied += 1
                elif b.is_available:
                    available += 1
        else:
            active_beds_qs = self.beds.filter(is_active=True)
            total = active_beds_qs.count()
            occupied = active_beds_qs.filter(
                bookings__status__in=ACTIVE_BOOKING_STATUSES,
            ).distinct().count()
            available = active_beds_qs.filter(
                is_available=True,
            ).exclude(
                bookings__status__in=ACTIVE_BOOKING_STATUSES,
            ).count()

        if not self.is_active:
            status = "Inactive"
            status_code = "INACTIVE"
        elif total == 0:
            status = "No Beds"
            status_code = "NO_BEDS"
        elif available == 0:
            status = "Full / Unavailable"
            status_code = "FULL"
        elif occupied > 0:
            status = "Active / Partially occupied"
            status_code = "PARTIALLY_OCCUPIED"
        else:
            status = "Active / Available"
            status_code = "AVAILABLE"

        return {
            "total": total,
            "occupied": occupied,
            "available": available,
            "status": status,
            "status_code": status_code,
            "is_bookable": self.is_active and available > 0,
        }

    @property
    def availability_status(self) -> str:
        """Dynamic room status derived from bed bookings."""
        return self.get_availability_stats()["status"]

    @property
    def availability_status_code(self) -> str:
        return self.get_availability_stats()["status_code"]

    @property
    def total_beds_count(self) -> int:
        return self.get_availability_stats()["total"]

    @property
    def occupied_beds_count(self) -> int:
        return self.get_availability_stats()["occupied"]

    @property
    def available_beds_count(self) -> int:
        return self.get_availability_stats()["available"]

    @property
    def is_bookable(self) -> bool:
        return self.get_availability_stats()["is_bookable"]

    @property
    def starting_rent(self) -> Decimal | None:
        """Minimum rent of available active beds in this room."""
        from stayease.bookings.models import ACTIVE_BOOKING_STATUSES

        bookable_beds = []
        active_beds = []
        for b in self.beds.all():
            if b.is_active:
                active_beds.append(b)
                if b.is_available:
                    if hasattr(b, "_prefetched_objects_cache") and "bookings" in b._prefetched_objects_cache:
                        has_active = any(bk.status in ACTIVE_BOOKING_STATUSES for bk in b.bookings.all())  # type: ignore[attr-defined]
                    else:
                        has_active = b.bookings.filter(status__in=ACTIVE_BOOKING_STATUSES).exists()  # type: ignore[attr-defined]
                    if not has_active:
                        bookable_beds.append(b)

        if bookable_beds:
            return min(b.rent_per_month for b in bookable_beds)
        if active_beds:
            return min(b.rent_per_month for b in active_beds)
        return self.rent


class Bed(models.Model):
    """
    An individually bookable sleeping space within a room.

    The bed is the primary unit that a tenant requests to book.
    Pricing is configured on the bed and is authoritative for bookings.

    Relationship: Room 1──N Bed
    Business logic ownership: Member 2 (inventory), Member 4 (booking)
    """

    room = models.ForeignKey(
        Room,
        on_delete=models.CASCADE,
        related_name="beds",
        verbose_name=_("room"),
    )
    label = models.CharField(
        _("label"),
        max_length=50,
        help_text=_('e.g. "Bed A", "Bed B"'),
    )
    rent_per_month = models.DecimalField(
        _("rent per month"),
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text=_("Monthly rent for this bed."),
    )
    is_available = models.BooleanField(
        _("available"),
        default=True,
        help_text=_("Inventory-level availability managed by the owner."),
    )
    is_active = models.BooleanField(
        _("active"),
        default=True,
        help_text=_("Whether this bed is currently active in the system."),
    )
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)
    updated_at = models.DateTimeField(_("updated at"), auto_now=True)

    class Meta:
        verbose_name = _("Bed")
        verbose_name_plural = _("Beds")
        ordering = ["label"]
        constraints = [
            models.UniqueConstraint(
                fields=["room", "label"],
                name="unique_bed_label_per_room",
            ),
        ]

    def __str__(self):
        return f"{self.room} - {self.label} (₹{self.rent_per_month}/mo)"

    @property
    def is_occupied(self) -> bool:
        """Return True if this bed has an active booking."""
        from stayease.bookings.models import ACTIVE_BOOKING_STATUSES

        if hasattr(self, "_prefetched_objects_cache") and "bookings" in self._prefetched_objects_cache:
            return any(b.status in ACTIVE_BOOKING_STATUSES for b in self.bookings.all())  # type: ignore[attr-defined]
        return self.bookings.filter(status__in=ACTIVE_BOOKING_STATUSES).exists()  # type: ignore[attr-defined]

    @property
    def is_bookable(self) -> bool:
        """Return True if this bed is active, owner-enabled, and not occupied."""
        return self.is_active and self.is_available and not self.is_occupied

    @property
    def status_display(self) -> str:
        """Human-readable status for owner management and dashboards."""
        if not self.is_active:
            return "Inactive"
        if not self.is_available:
            return "Unavailable"
        if self.is_occupied:
            return "Occupied"
        return "Available"
