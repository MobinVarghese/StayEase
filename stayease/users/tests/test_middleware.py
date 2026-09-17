"""
Tests for custom middleware in the users app.
"""

from __future__ import annotations

import pytest
from django.http import HttpResponse
from django.test import RequestFactory
from django.urls import reverse

from stayease.users.middleware import NoCacheOnAuthenticatedMiddleware
from stayease.users.models import UserRole
from stayease.users.tests.factories import UserFactory

pytestmark = pytest.mark.django_db


class TestNoCacheOnAuthenticatedMiddleware:
    """Test browser caching prevention headers for authenticated sessions."""

    def test_authenticated_user_response_has_no_cache_headers(self, rf: RequestFactory):
        user = UserFactory(role=UserRole.TENANT)
        request = rf.get("/some-page/")
        request.user = user

        def dummy_view(req):
            return HttpResponse("Authenticated content")

        middleware = NoCacheOnAuthenticatedMiddleware(dummy_view)
        response = middleware(request)

        cache_control = response.headers.get("Cache-Control", "")
        assert "no-cache" in cache_control
        assert "no-store" in cache_control
        assert "must-revalidate" in cache_control
        assert "private" in cache_control
        assert response.headers.get("Pragma") == "no-cache"

    def test_anonymous_user_response_does_not_force_no_store(self, rf: RequestFactory):
        from django.contrib.auth.models import AnonymousUser

        request = rf.get("/")
        request.user = AnonymousUser()

        def dummy_view(req):
            return HttpResponse("Public content")

        middleware = NoCacheOnAuthenticatedMiddleware(dummy_view)
        response = middleware(request)

        cache_control = response.headers.get("Cache-Control", "")
        assert "no-store" not in cache_control
        assert "Pragma" not in response.headers

    def test_full_request_cycle_authenticated_page_has_no_cache(self, client):
        user = UserFactory(role=UserRole.TENANT)
        client.force_login(user)

        response = client.get(reverse("users:profile"))
        assert response.status_code == 200

        cache_control = response.headers.get("Cache-Control", "")
        assert "no-cache" in cache_control
        assert "no-store" in cache_control
        assert "must-revalidate" in cache_control
        assert response.headers.get("Pragma") == "no-cache"

    def test_back_button_behavior_after_logout(self, client):
        """
        Simulate user logging out: subsequent visit to authenticated view
        must be rejected by Django and redirect to login, because no-store
        instructs the browser never to restore from bfcache.
        """
        user = UserFactory(role=UserRole.TENANT)
        client.force_login(user)

        # 1. User visits profile while logged in -> served with no-cache headers
        res1 = client.get(reverse("users:profile"))
        assert res1.status_code == 200
        assert "no-store" in res1.headers.get("Cache-Control", "")

        # 2. User logs out
        client.logout()

        # 3. Requesting the page again must be blocked with redirect to login
        res2 = client.get(reverse("users:profile"))
        assert res2.status_code == 302
        assert "/accounts/login/" in res2.url
