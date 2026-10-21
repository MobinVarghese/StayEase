from django.contrib import admin

from .models import Booking


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "tenant",
        "bed",
        "bed_rent_display",
        "status",
        "created_at",
        "approved_at",
        "rejected_at",
        "confirmed_at",
        "updated_at",
    ]
    list_filter = ["status", "created_at"]
    search_fields = ["tenant__email", "bed__label", "bed__room__pg__name"]

    @admin.display(description="Bed Rent")
    def bed_rent_display(self, obj):
        return f"₹{obj.bed.rent_per_month}" if obj.bed and obj.bed.rent_per_month is not None else "-"
    readonly_fields = [
        "created_at",
        "updated_at",
        "approved_at",
        "rejected_at",
        "confirmed_at",
    ]
    date_hierarchy = "created_at"
    raw_id_fields = ["tenant", "bed"]
