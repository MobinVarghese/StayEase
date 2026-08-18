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
        help_text=_("Base / representative monthly rent for this PG."),
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
        help_text=_("Monthly rent for this room."),
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


class Bed(models.Model):
    """
    An individually bookable sleeping space within a room.

    The bed is the primary unit that a tenant requests to book.

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
        return f"{self.room} - {self.label}"
