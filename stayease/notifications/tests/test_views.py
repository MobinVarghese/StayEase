"""
Tests for notification views.

Covers:
- Notification list view (authenticated / unauthenticated)
- Mark single notification read (owner / wrong user)
- Mark all notifications read
- Notification isolation between users
"""

from __future__ import annotations

import pytest
from django.test import Client
from django.urls import reverse

from stayease.notifications.models import Notification
from stayease.notifications.tests.factories import NotificationFactory
from stayease.users.tests.factories import UserFactory

pytestmark = pytest.mark.django_db


# ======================================================================
# NotificationListView
# ======================================================================


class TestNotificationListView:
    def test_requires_login(self):
        client = Client()
        url = reverse("notifications:notification_list")
        response = client.get(url)
        assert response.status_code == 302
        assert "account" in response.url or "login" in response.url

    def test_shows_own_notifications(self):
        user = UserFactory(password="testpass123")
        NotificationFactory(recipient=user, message="Your booking was approved")
        NotificationFactory(recipient=user, message="Your booking was rejected")

        client = Client()
        client.login(email=user.email, password="testpass123")
        response = client.get(reverse("notifications:notification_list"))
        assert response.status_code == 200
        assert b"Your booking was approved" in response.content
        assert b"Your booking was rejected" in response.content

    def test_does_not_show_other_users_notifications(self):
        user1 = UserFactory(password="testpass123")
        user2 = UserFactory(password="testpass123")
        NotificationFactory(recipient=user2, message="Secret notification")

        client = Client()
        client.login(email=user1.email, password="testpass123")
        response = client.get(reverse("notifications:notification_list"))
        assert response.status_code == 200
        assert b"Secret notification" not in response.content


# ======================================================================
# MarkNotificationReadView
# ======================================================================


class TestMarkNotificationReadView:
    def test_marks_own_notification_read(self):
        user = UserFactory(password="testpass123")
        n = NotificationFactory(recipient=user, is_read=False)

        client = Client()
        client.login(email=user.email, password="testpass123")
        url = reverse("notifications:mark_read", kwargs={"pk": n.pk})
        response = client.post(url)
        assert response.status_code == 302

        n.refresh_from_db()
        assert n.is_read is True

    def test_rejects_other_users_notification(self):
        user1 = UserFactory(password="testpass123")
        user2 = UserFactory(password="testpass123")
        n = NotificationFactory(recipient=user1, is_read=False)

        client = Client()
        client.login(email=user2.email, password="testpass123")
        url = reverse("notifications:mark_read", kwargs={"pk": n.pk})
        response = client.post(url)
        # Should redirect (with error message) but not mark as read
        assert response.status_code == 302
        n.refresh_from_db()
        assert n.is_read is False

    def test_requires_login(self):
        n = NotificationFactory(is_read=False)
        client = Client()
        url = reverse("notifications:mark_read", kwargs={"pk": n.pk})
        response = client.post(url)
        assert response.status_code == 302
        n.refresh_from_db()
        assert n.is_read is False

    def test_returns_404_for_nonexistent(self):
        user = UserFactory(password="testpass123")
        client = Client()
        client.login(email=user.email, password="testpass123")
        url = reverse("notifications:mark_read", kwargs={"pk": 99999})
        response = client.post(url)
        assert response.status_code == 404


# ======================================================================
# MarkAllReadView
# ======================================================================


class TestMarkAllReadView:
    def test_marks_all_as_read(self):
        user = UserFactory(password="testpass123")
        NotificationFactory(recipient=user, is_read=False)
        NotificationFactory(recipient=user, is_read=False)

        client = Client()
        client.login(email=user.email, password="testpass123")
        url = reverse("notifications:mark_all_read")
        response = client.post(url)
        assert response.status_code == 302

        assert Notification.objects.filter(
            recipient=user, is_read=False
        ).count() == 0

    def test_does_not_affect_other_users(self):
        user1 = UserFactory(password="testpass123")
        user2 = UserFactory()
        NotificationFactory(recipient=user2, is_read=False)

        client = Client()
        client.login(email=user1.email, password="testpass123")
        url = reverse("notifications:mark_all_read")
        client.post(url)

        assert Notification.objects.filter(
            recipient=user2, is_read=False
        ).count() == 1

    def test_requires_login(self):
        client = Client()
        url = reverse("notifications:mark_all_read")
        response = client.post(url)
        assert response.status_code == 302
