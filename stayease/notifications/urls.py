"""
URL configuration for the notifications app.

All URLs are namespaced under ``notifications:``.
"""

from django.urls import path

from stayease.notifications import views

app_name = "notifications"

urlpatterns = [
    # List all notifications for the authenticated user
    path(
        "",
        views.NotificationListView.as_view(),
        name="notification_list",
    ),
    # Mark a single notification as read (POST only)
    path(
        "<int:pk>/read/",
        views.MarkNotificationReadView.as_view(),
        name="mark_read",
    ),
    # Mark all notifications as read (POST only)
    path(
        "mark-all-read/",
        views.MarkAllReadView.as_view(),
        name="mark_all_read",
    ),
]
