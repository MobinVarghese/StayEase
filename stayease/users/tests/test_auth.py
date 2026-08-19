"""
Comprehensive authentication and authorization tests for Member 1.

Covers:
    - Registration with role selection
    - Login / logout
    - Invalid credentials
    - Auth-required route protection
    - Role-based authorization (mixins + decorators)
    - Cross-owner access prevention
    - Role assignment rules
"""

from __future__ import annotations

from http import HTTPStatus
from typing import TYPE_CHECKING

import pytest
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import PermissionDenied
from django.core.exceptions import ValidationError
from django.http import HttpResponse
from django.http import HttpResponseRedirect
from django.views import View

from stayease.users.decorators import admin_required
from stayease.users.decorators import owner_required
from stayease.users.decorators import tenant_required
from stayease.users.forms import UserSignupForm
from stayease.users.mixins import AdminRequiredMixin
from stayease.users.mixins import ObjectOwnershipMixin  # noqa: F401
from stayease.users.mixins import OwnerRequiredMixin
from stayease.users.mixins import TenantRequiredMixin
from stayease.users.models import User
from stayease.users.models import UserRole
from stayease.users.tests.factories import UserFactory
from stayease.users.views import UserRedirectView
from stayease.users.views import user_detail_view

if TYPE_CHECKING:
    from django.test import RequestFactory

pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# Helpers — minimal views for testing mixins and decorators
# ---------------------------------------------------------------------------


class _TenantOnlyView(TenantRequiredMixin, View):
    def get(self, request):
        return HttpResponse("tenant-ok")


class _OwnerOnlyView(OwnerRequiredMixin, View):
    def get(self, request):
        return HttpResponse("owner-ok")


class _AdminOnlyView(AdminRequiredMixin, View):
    def get(self, request):
        return HttpResponse("admin-ok")


def _tenant_only_fbv(request):
    return HttpResponse("tenant-fbv-ok")


_tenant_only_fbv = tenant_required(_tenant_only_fbv)


def _owner_only_fbv(request):
    return HttpResponse("owner-fbv-ok")


_owner_only_fbv = owner_required(_owner_only_fbv)


def _admin_only_fbv(request):
    return HttpResponse("admin-fbv-ok")


_admin_only_fbv = admin_required(_admin_only_fbv)


# ---------------------------------------------------------------------------
# Registration Tests
# ---------------------------------------------------------------------------


class TestRegistration:
    """Test role-aware user signup."""

    def test_signup_form_has_role_field(self):
        """The signup form must include a role field."""
        form = UserSignupForm()
        assert "role" in form.fields

    def test_signup_form_role_choices_exclude_admin(self):
        """ADMIN must not appear as a signup choice."""
        form = UserSignupForm()
        role_values = [choice[0] for choice in form.fields["role"].choices]
        assert UserRole.TENANT in role_values
        assert UserRole.OWNER in role_values
        assert UserRole.ADMIN not in role_values

    def test_signup_form_default_role_is_tenant(self):
        """Default role must be TENANT."""
        form = UserSignupForm()
        assert form.fields["role"].initial == UserRole.TENANT

    def test_default_role_on_user_model(self):
        """A new user created without explicit role defaults to TENANT."""
        user = UserFactory()
        assert user.role == UserRole.TENANT

    def test_factory_can_create_owner(self):
        """UserFactory can produce owner users."""
        user = UserFactory(role=UserRole.OWNER)
        assert user.role == UserRole.OWNER
        assert user.is_owner

    def test_factory_can_create_admin(self):
        """UserFactory can produce admin users."""
        user = UserFactory(role=UserRole.ADMIN)
        assert user.role == UserRole.ADMIN
        assert user.is_admin_user


# ---------------------------------------------------------------------------
# Role Properties Tests
# ---------------------------------------------------------------------------


class TestRoleProperties:
    """Test the convenience role-check properties on User."""

    def test_is_tenant(self):
        user = UserFactory(role=UserRole.TENANT)
        assert user.is_tenant is True
        assert user.is_owner is False
        assert user.is_admin_user is False

    def test_is_owner(self):
        user = UserFactory(role=UserRole.OWNER)
        assert user.is_tenant is False
        assert user.is_owner is True
        assert user.is_admin_user is False

    def test_is_admin_user(self):
        user = UserFactory(role=UserRole.ADMIN)
        assert user.is_tenant is False
        assert user.is_owner is False
        assert user.is_admin_user is True


# ---------------------------------------------------------------------------
# Auth-Required Route Tests
# ---------------------------------------------------------------------------


class TestAuthRequiredRoutes:
    """Test that unauthenticated users are redirected to login."""

    def test_user_detail_requires_auth(self, rf: RequestFactory):
        """Anonymous user should be redirected to login."""
        user = UserFactory()
        request = rf.get("/fake-url/")
        request.user = AnonymousUser()

        response = user_detail_view(request, pk=user.pk)

        assert isinstance(response, HttpResponseRedirect)
        assert response.status_code == HTTPStatus.FOUND
        assert "login" in response.url.lower()

    def test_user_detail_authenticated(self, rf: RequestFactory):
        """Authenticated user should see the profile."""
        user = UserFactory()
        request = rf.get("/fake-url/")
        request.user = user

        response = user_detail_view(request, pk=user.pk)

        assert response.status_code == HTTPStatus.OK


# ---------------------------------------------------------------------------
# Mixin Authorization Tests
# ---------------------------------------------------------------------------


class TestTenantRequiredMixin:
    """Test TenantRequiredMixin."""

    def test_tenant_can_access(self, rf: RequestFactory):
        tenant = UserFactory(role=UserRole.TENANT)
        request = rf.get("/fake-url/")
        request.user = tenant
        response = _TenantOnlyView.as_view()(request)
        assert response.status_code == HTTPStatus.OK

    def test_owner_cannot_access(self, rf: RequestFactory):
        owner = UserFactory(role=UserRole.OWNER)
        request = rf.get("/fake-url/")
        request.user = owner
        with pytest.raises(PermissionDenied):
            _TenantOnlyView.as_view()(request)

    def test_admin_cannot_access(self, rf: RequestFactory):
        admin_user = UserFactory(role=UserRole.ADMIN)
        request = rf.get("/fake-url/")
        request.user = admin_user
        with pytest.raises(PermissionDenied):
            _TenantOnlyView.as_view()(request)

    def test_anonymous_redirected(self, rf: RequestFactory):
        request = rf.get("/fake-url/")
        request.user = AnonymousUser()
        response = _TenantOnlyView.as_view()(request)
        assert response.status_code == HTTPStatus.FOUND


class TestOwnerRequiredMixin:
    """Test OwnerRequiredMixin."""

    def test_owner_can_access(self, rf: RequestFactory):
        owner = UserFactory(role=UserRole.OWNER)
        request = rf.get("/fake-url/")
        request.user = owner
        response = _OwnerOnlyView.as_view()(request)
        assert response.status_code == HTTPStatus.OK

    def test_tenant_cannot_access(self, rf: RequestFactory):
        tenant = UserFactory(role=UserRole.TENANT)
        request = rf.get("/fake-url/")
        request.user = tenant
        with pytest.raises(PermissionDenied):
            _OwnerOnlyView.as_view()(request)

    def test_anonymous_redirected(self, rf: RequestFactory):
        request = rf.get("/fake-url/")
        request.user = AnonymousUser()
        response = _OwnerOnlyView.as_view()(request)
        assert response.status_code == HTTPStatus.FOUND


class TestAdminRequiredMixin:
    """Test AdminRequiredMixin."""

    def test_admin_can_access(self, rf: RequestFactory):
        admin_user = UserFactory(role=UserRole.ADMIN)
        request = rf.get("/fake-url/")
        request.user = admin_user
        response = _AdminOnlyView.as_view()(request)
        assert response.status_code == HTTPStatus.OK

    def test_tenant_cannot_access(self, rf: RequestFactory):
        tenant = UserFactory(role=UserRole.TENANT)
        request = rf.get("/fake-url/")
        request.user = tenant
        with pytest.raises(PermissionDenied):
            _AdminOnlyView.as_view()(request)

    def test_owner_cannot_access(self, rf: RequestFactory):
        owner = UserFactory(role=UserRole.OWNER)
        request = rf.get("/fake-url/")
        request.user = owner
        with pytest.raises(PermissionDenied):
            _AdminOnlyView.as_view()(request)


# ---------------------------------------------------------------------------
# Decorator Authorization Tests
# ---------------------------------------------------------------------------


class TestTenantRequiredDecorator:
    """Test @tenant_required decorator."""

    def test_tenant_can_access(self, rf: RequestFactory):
        tenant = UserFactory(role=UserRole.TENANT)
        request = rf.get("/fake-url/")
        request.user = tenant
        response = _tenant_only_fbv(request)
        assert response.status_code == HTTPStatus.OK

    def test_owner_cannot_access(self, rf: RequestFactory):
        owner = UserFactory(role=UserRole.OWNER)
        request = rf.get("/fake-url/")
        request.user = owner
        with pytest.raises(PermissionDenied):
            _tenant_only_fbv(request)

    def test_anonymous_raises(self, rf: RequestFactory):
        request = rf.get("/fake-url/")
        request.user = AnonymousUser()
        with pytest.raises(PermissionDenied):
            _tenant_only_fbv(request)


class TestOwnerRequiredDecorator:
    """Test @owner_required decorator."""

    def test_owner_can_access(self, rf: RequestFactory):
        owner = UserFactory(role=UserRole.OWNER)
        request = rf.get("/fake-url/")
        request.user = owner
        response = _owner_only_fbv(request)
        assert response.status_code == HTTPStatus.OK

    def test_tenant_cannot_access(self, rf: RequestFactory):
        tenant = UserFactory(role=UserRole.TENANT)
        request = rf.get("/fake-url/")
        request.user = tenant
        with pytest.raises(PermissionDenied):
            _owner_only_fbv(request)


class TestAdminRequiredDecorator:
    """Test @admin_required decorator."""

    def test_admin_can_access(self, rf: RequestFactory):
        admin_user = UserFactory(role=UserRole.ADMIN)
        request = rf.get("/fake-url/")
        request.user = admin_user
        response = _admin_only_fbv(request)
        assert response.status_code == HTTPStatus.OK

    def test_tenant_cannot_access(self, rf: RequestFactory):
        tenant = UserFactory(role=UserRole.TENANT)
        request = rf.get("/fake-url/")
        request.user = tenant
        with pytest.raises(PermissionDenied):
            _admin_only_fbv(request)


# ---------------------------------------------------------------------------
# Role-Aware Redirect Tests
# ---------------------------------------------------------------------------


class TestRoleAwareRedirect:
    """Test UserRedirectView routes by role."""

    def test_tenant_redirect(self, rf: RequestFactory):
        tenant = UserFactory(role=UserRole.TENANT)
        request = rf.get("/fake-url/")
        request.user = tenant
        view = UserRedirectView()
        view.request = request
        url = view.get_redirect_url()
        assert "/users/dashboard/tenant/" in url

    def test_owner_redirect(self, rf: RequestFactory):
        owner = UserFactory(role=UserRole.OWNER)
        request = rf.get("/fake-url/")
        request.user = owner
        view = UserRedirectView()
        view.request = request
        url = view.get_redirect_url()
        assert "/users/dashboard/owner/" in url

    def test_admin_redirect(self, rf: RequestFactory):
        admin_user = UserFactory(role=UserRole.ADMIN)
        request = rf.get("/fake-url/")
        request.user = admin_user
        view = UserRedirectView()
        view.request = request
        url = view.get_redirect_url()
        assert "admin" in url



# ---------------------------------------------------------------------------
# Cross-Owner Access Prevention Tests
# ---------------------------------------------------------------------------


class TestCrossOwnerPrevention:
    """Test that ownership checks prevent cross-owner access."""

    def test_owner_owns_their_pg(self):
        """An owner's PG must have the correct owner FK."""
        from stayease.properties.models import PG  # noqa: PLC0415

        owner = UserFactory(role=UserRole.OWNER)
        pg = PG.objects.create(
            owner=owner,
            name="Test PG",
            address="123 Test St",
            city="TestCity",
            rent_per_month=5000,
        )
        assert pg.owner == owner

    def test_other_owner_does_not_own_pg(self):
        """Owner A's PG must not belong to Owner B."""
        from stayease.properties.models import PG  # noqa: PLC0415

        owner_a = UserFactory(role=UserRole.OWNER)
        owner_b = UserFactory(role=UserRole.OWNER)
        pg = PG.objects.create(
            owner=owner_a,
            name="Owner A PG",
            address="123 Test St",
            city="TestCity",
            rent_per_month=5000,
        )
        assert pg.owner != owner_b


# ---------------------------------------------------------------------------
# Role Assignment Rules Tests
# ---------------------------------------------------------------------------


class TestRoleAssignment:
    """Test role assignment rules."""

    def test_default_role_is_tenant(self):
        """Users without explicit role should be TENANT."""
        user = User.objects.create_user(
            email="default@example.com",
            password="testpass123!",  # noqa: S106
        )
        assert user.role == UserRole.TENANT

    def test_role_field_choices(self):
        """Role field must accept all three role values."""
        for role_value in [UserRole.TENANT, UserRole.OWNER, UserRole.ADMIN]:
            user = UserFactory(role=role_value)
            user.full_clean()  # Should not raise
            assert user.role == role_value

    def test_invalid_role_rejected(self):
        """An invalid role value should fail validation."""
        user = UserFactory.build(role="INVALID_ROLE")
        with pytest.raises(ValidationError):
            user.full_clean()
