"""
Custom middleware for the StayEase platform.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.utils.cache import add_never_cache_headers

if TYPE_CHECKING:
    from collections.abc import Callable

    from django.http import HttpRequest
    from django.http import HttpResponse


class NoCacheOnAuthenticatedMiddleware:
    """
    Prevents client-side browser caching (bfcache) of pages for authenticated users.

    When a logged-in user visits authenticated pages, this middleware appends:
    - Cache-Control: max-age=0, no-cache, no-store, must-revalidate, private
    - Pragma: no-cache
    - Expires: <current GMT timestamp>

    This ensures that when a user logs out and then presses the browser's "Back"
    button, the browser will NOT restore a stale authenticated page snapshot from
    memory/disk cache, but instead re-requests the page from Django, which
    authenticates/intercepts the request and redirects to the login screen.
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]):
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        response = self.get_response(request)

        user = getattr(request, "user", None)
        if user and user.is_authenticated:
            add_never_cache_headers(response)
            response.headers["Pragma"] = "no-cache"

        return response
