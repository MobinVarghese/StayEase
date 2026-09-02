"""
Template context processors for the notifications app.

Registers the unread notification count so it is available in every
template without requiring explicit view-level injection.
"""

from __future__ import annotations

from stayease.notifications.services import get_unread_count


def unread_notification_count(request):
    """
    Add ``unread_notification_count`` to the template context.

    Returns 0 for anonymous users.
    """
    if request.user.is_authenticated:
        return {"unread_notification_count": get_unread_count(request.user)}
    return {"unread_notification_count": 0}
