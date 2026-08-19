from django.contrib import admin

from .models import Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ["id", "recipient", "is_read", "created_at"]
    list_filter = ["is_read"]
    search_fields = ["recipient__email", "message"]
    readonly_fields = ["created_at"]
