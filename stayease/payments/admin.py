from django.contrib import admin

from .models import Payment


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "booking",
        "amount",
        "status",
        "transaction_ref",
        "created_at",
    ]
    list_filter = ["status"]
    search_fields = ["transaction_ref"]
    readonly_fields = ["created_at", "updated_at"]
