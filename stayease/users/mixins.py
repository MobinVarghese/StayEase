"""
Reusable authorization mixins for class-based views.

All members should use these mixins rather than writing ad-hoc
role-checking logic in their views.

Usage examples::

    # Only owners can access this view
    class PGCreateView(OwnerRequiredMixin, CreateView):
        ...

    # Only this PG's owner can edit it
    class PGUpdateView(OwnerRequiredMixin, ObjectOwnershipMixin, UpdateView):
        ownership_field = "owner"
        ...

    # Only tenants can access this view
    class BookingCreateView(TenantRequiredMixin, CreateView):
        ...
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied

from stayease.users.models import UserRole

if TYPE_CHECKING:
    from django.http import HttpRequest

_MSG_ROLE_DENIED = "You do not have the required role to access this page."
_MSG_OWNERSHIP_DENIED = "You do not have permission to access this resource."


class RoleRequiredMixin(LoginRequiredMixin):
    """
    Mixin that verifies the authenticated user has the expected role.

    Subclasses must set ``required_role`` to a :class:`UserRole` value.
    If the user is not authenticated, they are redirected to login
    (inherited from ``LoginRequiredMixin``).  If authenticated but the
    wrong role, a ``PermissionDenied`` (403) is raised.
    """

    required_role: str | None = None
    raise_exception = True  # 403 instead of redirect for role mismatch

    def dispatch(self, request: HttpRequest, *args, **kwargs):
        # Let LoginRequiredMixin handle unauthenticated users first
        response = super().dispatch(request, *args, **kwargs)

        # If super() already returned a redirect (unauthenticated), use it
        if hasattr(response, "status_code") and response.status_code in (
            301,
            302,
        ):
            return response

        # Now check role
        if (
            self.required_role is not None
            and getattr(request.user, "role", None) != self.required_role
        ):
            raise PermissionDenied(_MSG_ROLE_DENIED)
        return response


class TenantRequiredMixin(RoleRequiredMixin):
    """Only users with role=TENANT may access this view."""

    required_role = UserRole.TENANT


class OwnerRequiredMixin(RoleRequiredMixin):
    """Only users with role=OWNER may access this view."""

    required_role = UserRole.OWNER


class AdminRequiredMixin(RoleRequiredMixin):
    """Only users with role=ADMIN may access this view."""

    required_role = UserRole.ADMIN


class ObjectOwnershipMixin:
    """
    Mixin that verifies the current user owns the object being accessed.

    Combine with a role mixin and a ``SingleObjectMixin``-based view
    (DetailView, UpdateView, DeleteView).

    Set ``ownership_field`` to the name of the FK field on the model
    that points to the owning user.  Defaults to ``"owner"``.

    Usage::

        class PGUpdateView(OwnerRequiredMixin, ObjectOwnershipMixin, UpdateView):
            model = PG
            ownership_field = "owner"  # PG.owner must == request.user
    """

    ownership_field: str = "owner"

    def get_object(self, queryset=None):
        obj = super().get_object(queryset)  # type: ignore[misc]
        owner = getattr(obj, self.ownership_field, None)
        if owner != self.request.user:  # type: ignore[attr-defined]
            raise PermissionDenied(_MSG_OWNERSHIP_DENIED)
        return obj
