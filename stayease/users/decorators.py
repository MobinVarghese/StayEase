"""
Function-based view decorators for role-based authorization.

These are the function-view equivalents of the class-based mixins
in :mod:`stayease.users.mixins`.

Usage::

    @login_required
    @owner_required
    def pg_create_view(request):
        ...
"""

from __future__ import annotations

import functools
from typing import TYPE_CHECKING

from django.core.exceptions import PermissionDenied

from stayease.users.models import UserRole

if TYPE_CHECKING:
    from collections.abc import Callable

    from django.http import HttpRequest
    from django.http import HttpResponse

_MSG_ROLE_DENIED = "You do not have the required role to access this page."


def _role_required(required_role: str):
    """
    Factory that returns a decorator enforcing a specific user role.

    The decorated view must already be behind ``@login_required``
    (or the view must otherwise guarantee ``request.user`` is
    authenticated).  If the user's role does not match, a
    ``PermissionDenied`` (403) is raised.
    """

    def decorator(
        view_func: Callable,
    ) -> Callable:
        @functools.wraps(view_func)
        def _wrapped(
            request: HttpRequest,
            *args,
            **kwargs,
        ) -> HttpResponse:
            if (
                not request.user.is_authenticated
                or getattr(request.user, "role", None) != required_role
            ):
                raise PermissionDenied(_MSG_ROLE_DENIED)
            return view_func(request, *args, **kwargs)

        return _wrapped

    return decorator


tenant_required = _role_required(UserRole.TENANT)
tenant_required.__doc__ = "Decorator: 403 if the user is not a TENANT."

owner_required = _role_required(UserRole.OWNER)
owner_required.__doc__ = "Decorator: 403 if the user is not an OWNER."

admin_required = _role_required(UserRole.ADMIN)
admin_required.__doc__ = "Decorator: 403 if the user is not an ADMIN."
