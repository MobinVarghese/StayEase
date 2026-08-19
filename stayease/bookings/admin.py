from django.contrib import admin

from .models import Booking


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ["id", "tenant", "bed", "status", "created_at", "updated_at"]
    list_filter = ["status"]
    search_fields = ["tenant__email", "bed__label"]
    readonly_fields = ["created_at", "updated_at"]
