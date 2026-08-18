from django.contrib import admin

from .models import PG
from .models import Bed
from .models import Room


class RoomInline(admin.TabularInline):
    model = Room
    extra = 0
    show_change_link = True


class BedInline(admin.TabularInline):
    model = Bed
    extra = 0


@admin.register(PG)
class PGAdmin(admin.ModelAdmin):
    list_display = [
        "name",
        "owner",
        "city",
        "rent_per_month",
        "is_active",
        "created_at",
    ]
    list_filter = ["is_active", "city"]
    search_fields = ["name", "city", "address"]
    inlines = [RoomInline]


@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
    list_display = ["room_number", "pg", "room_type", "capacity", "rent", "is_active"]
    list_filter = ["is_active", "room_type"]
    search_fields = ["room_number"]
    inlines = [BedInline]


@admin.register(Bed)
class BedAdmin(admin.ModelAdmin):
    list_display = ["label", "room", "is_available", "is_active"]
    list_filter = ["is_available", "is_active"]
    search_fields = ["label"]
