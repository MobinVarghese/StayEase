from django.contrib import admin

from .models import PG
from .models import Bed
from .models import Room


class RoomInline(admin.TabularInline):
    model = Room
    extra = 0
    show_change_link = True
    fields = ["room_number", "room_type", "capacity", "is_active"]


class BedInline(admin.TabularInline):
    model = Bed
    extra = 0
    fields = ["label", "rent_per_month", "is_available", "is_active"]


@admin.register(PG)
class PGAdmin(admin.ModelAdmin):
    list_display = [
        "name",
        "owner",
        "city",
        "starting_rent_display",
        "is_active",
        "created_at",
    ]
    list_filter = ["is_active", "city"]
    search_fields = ["name", "city", "address"]
    inlines = [RoomInline]

    @admin.display(description="Starting Rent")
    def starting_rent_display(self, obj: PG) -> str:
        rent = obj.starting_rent
        return f"₹{rent}" if rent is not None else "—"


@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
    list_display = [
        "room_number",
        "pg",
        "room_type",
        "capacity",
        "starting_rent_display",
        "is_active",
    ]
    list_filter = ["is_active", "room_type"]
    search_fields = ["room_number", "pg__name"]
    inlines = [BedInline]

    @admin.display(description="Starting Rent")
    def starting_rent_display(self, obj: Room) -> str:
        rent = obj.starting_rent
        return f"₹{rent}" if rent is not None else "—"


@admin.register(Bed)
class BedAdmin(admin.ModelAdmin):
    list_display = ["label", "room", "get_pg", "rent_per_month", "is_available", "is_active"]
    list_filter = ["is_available", "is_active", "room__pg"]
    search_fields = ["label", "room__room_number", "room__pg__name"]

    @admin.display(description="PG")
    def get_pg(self, obj: Bed) -> str:
        return obj.room.pg.name
