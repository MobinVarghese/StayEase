"""
Notification views.

All views enforce server-side authorization using Member 1's mixins.
Business logic is delegated to ``services.py``.
"""

from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.utils.translation import gettext_lazy as _
from django.views import View
from django.views.generic import ListView

from stayease.notifications.models import Notification
from stayease.notifications.services import mark_all_read
from stayease.notifications.services import mark_notification_read


class NotificationListView(LoginRequiredMixin, ListView):
    """
    List the authenticated user's notifications (newest first).

    All roles (tenant, owner, admin) can view their own notifications.
    """

    model = Notification
    template_name = "notifications/notification_list.html"
    context_object_name = "notifications"
    paginate_by = 20

    def get_queryset(self):
        return (
            Notification.objects.filter(recipient=self.request.user)
            .select_related("booking")
            .order_by("-created_at")
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["unread_count"] = (
            Notification.objects.filter(
                recipient=self.request.user,
                is_read=False,
            ).count()
        )
        return ctx


class MarkNotificationReadView(LoginRequiredMixin, View):
    """POST-only: mark a single notification as read."""

    def post(self, request, pk):
        notification = get_object_or_404(Notification, pk=pk)
        try:
            mark_notification_read(notification, request.user)
        except PermissionError:
            messages.error(
                request,
                _("You do not have permission to modify this notification."),
            )
        return redirect("notifications:notification_list")


class MarkAllReadView(LoginRequiredMixin, View):
    """POST-only: mark all of the user's notifications as read."""

    def post(self, request):
        count = mark_all_read(request.user)
        if count:
            messages.success(
                request,
                _("%(count)d notification(s) marked as read.") % {"count": count},
            )
        return redirect("notifications:notification_list")
